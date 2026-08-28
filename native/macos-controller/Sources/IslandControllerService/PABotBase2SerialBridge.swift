import Darwin
import Foundation
import SerialPortShim

/// Reliable, binary serial transport for PokemonAutomation's PABotBase2
/// ESP32-S3 firmware. The UART/COM port remains connected to the Mac while the
/// board's separate USB/OTG port enumerates as an NS2 wired controller.
final class PABotBase2SerialBridge {
    private enum ConnectionOpcode {
        static let reset: UInt8 = 0x01
        static let resetReply: UInt8 = 0x41
        static let stream: UInt8 = 0x12
        static let streamReply: UInt8 = 0x52
    }

    private enum MessageOpcode {
        static let returnUInt32: UInt8 = 0x12
        static let returnUInt32Data: UInt8 = 0x14
        static let requestStatus: UInt8 = 0x31
        static let readControllerMode: UInt8 = 0x32
        static let changeControllerMode: UInt8 = 0x33
        static let commandDropped: UInt8 = 0x40
        static let cancelQueue: UInt8 = 0x41
        static let commandFinished: UInt8 = 0x43
        static let wiredControllerState: UInt8 = 0x90
    }

    private static let magic: UInt8 = 0x81
    private static let ns2WiredControllerID: UInt32 = 0x1010
    private static let serialBaud: UInt = 921_600

    private var descriptor: Int32 = -1
    private(set) var portPath: String?
    private(set) var diagnostic = "尚未连接 PABotBase2 开发板"
    private(set) var controllerMode: UInt32 = 0

    private var sessionID: UInt32 = 0
    private var transmitSequence: UInt8 = 0
    private var transmitStreamOffset: UInt16 = 0
    private var receiveStreamOffset: UInt16 = 0
    private var requestID: UInt8 = 1
    private var commandID: UInt8 = 1
    private var receiveBuffer: [UInt8] = []
    private var messageBuffer: [UInt8] = []
    private var resetReplies: Set<UInt8> = []
    private var streamReplies: Set<UInt8> = []
    private var uint32Responses: [UInt8: UInt32] = [:]
    private var uint32DataResponses: [UInt8: (UInt32, [UInt8])] = [:]
    private var finishedCommands: Set<UInt8> = []
    private var droppedCommands: Set<UInt8> = []
    private(set) var consoleConnected = false

    var active: Bool { descriptor >= 0 }
    var readyForInput: Bool {
        active && controllerMode == Self.ns2WiredControllerID
    }
    var hasCandidatePort: Bool { !candidatePorts().isEmpty }

    func start() throws {
        if readyForInput { return }
        stopWithoutSending()

        let candidates = candidatePorts()
        guard !candidates.isEmpty else {
            throw ServiceError.notReady(
                "未发现开发板 UART/COM 串口；请把 Mac 数据线接到开发板的另一个 Type-C 口"
            )
        }

        var failures: [String] = []
        for path in candidates {
            do {
                try open(path)
                try beginSession()
                try changeControllerMode(to: Self.ns2WiredControllerID)
                Thread.sleep(forTimeInterval: 0.20)
                let mode = try queryControllerMode()
                guard mode == Self.ns2WiredControllerID else {
                    throw SerialBridgeError(
                        "模式读回为 0x\(String(mode, radix: 16))，期望 0x1010"
                    )
                }
                controllerMode = mode
                consoleConnected = (try? queryControllerStatus()) ?? false
                diagnostic = consoleConnected
                    ? "PABotBase2 已连接：NS2 有线手柄可接收按键（\(path)）"
                    : "PABotBase2 已就绪：请发送任意按键连接 NS2（\(path)）"
                return
            } catch {
                failures.append("\(path): \(error.localizedDescription)")
                stopWithoutSending()
            }
        }

        throw ServiceError.notReady(
            "发现串口但 PABotBase2 握手失败：\(failures.joined(separator: "；"))"
        )
    }

    func refresh() {
        guard active else { return }
        pumpPackets()
        if let portPath, !FileManager.default.fileExists(atPath: portPath) {
            diagnostic = "开发板 UART/COM 串口已断开"
            stopWithoutSending()
        }
    }

    func press(_ button: ControllerButton, holdMilliseconds: Int) throws {
        guard readyForInput else {
            throw ServiceError.notReady("PABotBase2 尚未进入 NS2 有线手柄模式")
        }
        guard (20...2_000).contains(holdMilliseconds) else {
            throw ServiceError.badRequest("hold_ms 必须在 20–2000 之间")
        }

        pumpPackets()
        let pressID = try sendControllerState(
            Self.state(for: button),
            milliseconds: UInt16(holdMilliseconds)
        )
        // Queue the release on the microcontroller itself. It will still run if
        // the browser pauses or the local HTTP request is interrupted.
        let releaseID = try sendControllerState(Self.neutralState, milliseconds: 40)
        try waitForCommand(pressID, timeout: 0.80 + Double(holdMilliseconds) / 1_000)
        try waitForCommand(releaseID, timeout: 0.80)
        consoleConnected = (try? queryControllerStatus()) ?? consoleConnected
        diagnostic = consoleConnected
            ? "已通过 PABotBase2 发送 \(button.rawValue)（NS2 已接收）"
            : "已发送 \(button.rawValue)，等待 NS2 建立有线手柄连接"
    }

    func releaseAll() {
        guard readyForInput else { return }
        do {
            // Cancel queued work before sending a neutral report, preventing a
            // previously queued press from becoming active after an abort.
            try sendStream(message: [0x04, 0x00, MessageOpcode.cancelQueue, 0x00])
            let releaseID = try sendControllerState(Self.neutralState, milliseconds: 40)
            try waitForCommand(releaseID, timeout: 0.80)
            diagnostic = "PABotBase2 已释放全部按键"
        } catch {
            diagnostic = "释放 PABotBase2 按键失败：\(error.localizedDescription)"
            stopWithoutSending()
        }
    }

    func stop() {
        if readyForInput {
            releaseAll()
            try? changeControllerMode(to: 0)
        }
        stopWithoutSending()
        diagnostic = "PABotBase2 已停止并回到安全模式"
    }

    // MARK: - Serial lifecycle

    private func candidatePorts() -> [String] {
        var candidates: [String] = []
        if let preferred = ProcessInfo.processInfo.environment["ISLAND_CONTROLLER_SERIAL_PORT"],
           !preferred.isEmpty
        {
            candidates.append(preferred)
        }

        let names = (try? FileManager.default.contentsOfDirectory(atPath: "/dev")) ?? []
        let discovered = names
            .filter {
                $0.hasPrefix("cu.usbmodem") ||
                $0.hasPrefix("cu.usbserial") ||
                $0.hasPrefix("cu.SLAB_USBtoUART") ||
                $0.hasPrefix("cu.wchusbserial")
            }
            .map { "/dev/\($0)" }
            .sorted {
                // External UART bridges tend to have a longer unique suffix;
                // prefer them over ESP32-S3's four-digit native USB boot port.
                if $0.count != $1.count { return $0.count > $1.count }
                return $0 < $1
            }
        for path in discovered where !candidates.contains(path) {
            candidates.append(path)
        }
        return candidates
    }

    private func open(_ path: String) throws {
        let opened = Darwin.open(path, O_RDWR | O_NOCTTY | O_NONBLOCK)
        guard opened >= 0 else { throw POSIXSerialError("open \(path)") }

        let result = AFConfigureRawSerialPort(opened, Self.serialBaud)
        guard result == 0 else {
            Darwin.close(opened)
            throw POSIXSerialError("configure \(path)", code: result)
        }

        descriptor = opened
        portPath = path
        // Opening the UART bridge can pulse EN. Let the firmware finish its
        // 115200-baud ROM log and switch to its 921600-baud protocol first.
        Thread.sleep(forTimeInterval: 1.40)
        _ = tcflush(opened, TCIOFLUSH)
    }

    private func stopWithoutSending() {
        if descriptor >= 0 {
            Darwin.close(descriptor)
        }
        descriptor = -1
        portPath = nil
        controllerMode = 0
        receiveBuffer.removeAll(keepingCapacity: true)
        messageBuffer.removeAll(keepingCapacity: true)
        resetReplies.removeAll()
        streamReplies.removeAll()
        uint32Responses.removeAll()
        uint32DataResponses.removeAll()
        finishedCommands.removeAll()
        droppedCommands.removeAll()
        consoleConnected = false
    }

    // MARK: - PABotBase2 connection layer

    private func beginSession() throws {
        sessionID = arc4random()
        if sessionID == 0xffff_ffff { sessionID = 0x4946_4e44 }
        transmitSequence = 0
        transmitStreamOffset = 0
        receiveStreamOffset = 0
        requestID = 1
        // The firmware command queue expects a monotonically increasing
        // sequence beginning at zero for each freshly selected controller.
        commandID = 0
        receiveBuffer.removeAll(keepingCapacity: true)
        messageBuffer.removeAll(keepingCapacity: true)
        resetReplies.removeAll()
        streamReplies.removeAll()
        uint32Responses.removeAll()
        uint32DataResponses.removeAll()
        finishedCommands.removeAll()
        droppedCommands.removeAll()

        let resetPayload = Self.littleEndianBytes(sessionID)
        let resetPacket = Self.makePacket(
            sequence: 0,
            opcode: ConnectionOpcode.reset,
            payload: resetPayload,
            crcSeed: 0xffff_ffff
        )
        try writeAll(resetPacket)
        guard wait(until: { self.resetReplies.contains(0) }, timeout: 1.0) else {
            throw SerialBridgeError("固件未回复 PABotBase2 session reset")
        }
        transmitSequence = 1
    }

    private func sendStream(message: [UInt8]) throws {
        guard message.count <= 14 else {
            throw SerialBridgeError("单条 PABotBase2 消息过长：\(message.count) bytes")
        }
        let sequence = transmitSequence
        var payload = Self.littleEndianBytes(transmitStreamOffset)
        payload.append(contentsOf: message)
        let packet = Self.makePacket(
            sequence: sequence,
            opcode: ConnectionOpcode.stream,
            payload: payload,
            crcSeed: sessionID
        )
        streamReplies.remove(sequence)

        var acknowledged = false
        for _ in 0..<3 {
            try writeAll(packet)
            if wait(until: { self.streamReplies.contains(sequence) }, timeout: 0.30) {
                acknowledged = true
                break
            }
        }
        guard acknowledged else {
            throw SerialBridgeError("固件未确认串口包 seq=\(sequence)")
        }

        streamReplies.remove(sequence)
        transmitSequence &+= 1
        transmitStreamOffset &+= UInt16(message.count)
    }

    private func pumpPackets() {
        guard descriptor >= 0 else { return }
        var chunk = [UInt8](repeating: 0, count: 1_024)
        while true {
            let count = Darwin.read(descriptor, &chunk, chunk.count)
            if count > 0 {
                receiveBuffer.append(contentsOf: chunk.prefix(Int(count)))
                continue
            }
            if count < 0, errno != EAGAIN, errno != EWOULDBLOCK, errno != EINTR {
                diagnostic = "读取开发板串口失败：\(String(cString: strerror(errno)))"
            }
            break
        }

        while let packet = pullPacket() {
            process(packet)
        }
    }

    private struct Packet {
        let sequence: UInt8
        let opcode: UInt8
        let payload: [UInt8]
    }

    private func pullPacket() -> Packet? {
        while true {
            guard let magicIndex = receiveBuffer.firstIndex(of: Self.magic) else {
                receiveBuffer.removeAll(keepingCapacity: true)
                return nil
            }
            if magicIndex > 0 { receiveBuffer.removeFirst(magicIndex) }
            guard receiveBuffer.count >= 4 else { return nil }

            let encodedLength = Int(receiveBuffer[2])
            let length = encodedLength == 0 ? 256 : encodedLength
            guard length >= 8 else {
                receiveBuffer.removeFirst()
                continue
            }
            guard receiveBuffer.count >= length else { return nil }

            let bytes = Array(receiveBuffer.prefix(length))
            receiveBuffer.removeFirst(length)
            let expectedCRC = Self.readUInt32(bytes, at: length - 4)
            let actualCRC = Self.crc32c(Array(bytes.dropLast(4)), seed: sessionID)
            guard expectedCRC == actualCRC else { continue }
            return Packet(
                sequence: bytes[1],
                opcode: bytes[3] & 0x7f,
                payload: Array(bytes[4..<(length - 4)])
            )
        }
    }

    private func process(_ packet: Packet) {
        switch packet.opcode {
        case ConnectionOpcode.resetReply:
            resetReplies.insert(packet.sequence)
        case ConnectionOpcode.streamReply:
            streamReplies.insert(packet.sequence)
        case ConnectionOpcode.stream:
            guard packet.payload.count >= 2 else { return }
            let offset = Self.readUInt16(packet.payload, at: 0)
            let bytes = Array(packet.payload.dropFirst(2))
            if offset == receiveStreamOffset {
                messageBuffer.append(contentsOf: bytes)
                receiveStreamOffset &+= UInt16(bytes.count)
                processMessages()
            }
            let acknowledgement = Self.makePacket(
                sequence: packet.sequence,
                opcode: ConnectionOpcode.streamReply,
                payload: Self.littleEndianBytes(UInt32(4_096)),
                crcSeed: sessionID
            )
            try? writeAll(acknowledgement)
        default:
            break
        }
    }

    private func processMessages() {
        while messageBuffer.count >= 4 {
            let length = Int(Self.readUInt16(messageBuffer, at: 0))
            guard length >= 4, length <= 256 else {
                messageBuffer.removeFirst()
                continue
            }
            guard messageBuffer.count >= length else { return }
            let message = Array(messageBuffer.prefix(length))
            messageBuffer.removeFirst(length)
            let opcode = message[2]
            let id = message[3]
            if opcode == MessageOpcode.returnUInt32, message.count >= 8 {
                uint32Responses[id] = Self.readUInt32(message, at: 4)
            } else if opcode == MessageOpcode.returnUInt32Data, message.count >= 8 {
                uint32DataResponses[id] = (
                    Self.readUInt32(message, at: 4),
                    Array(message.dropFirst(8))
                )
            } else if opcode == MessageOpcode.commandFinished {
                finishedCommands.insert(id)
            } else if opcode == MessageOpcode.commandDropped {
                droppedCommands.insert(id)
            }
        }
    }

    private func wait(until condition: () -> Bool, timeout: TimeInterval) -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        repeat {
            pumpPackets()
            if condition() { return true }
            usleep(5_000)
        } while Date() < deadline
        pumpPackets()
        return condition()
    }

    private func writeAll(_ bytes: [UInt8]) throws {
        guard descriptor >= 0 else { throw SerialBridgeError("串口尚未打开") }
        var written = 0
        while written < bytes.count {
            let result = bytes.withUnsafeBytes { rawBuffer -> Int in
                guard let base = rawBuffer.baseAddress else { return -1 }
                return Darwin.write(
                    descriptor,
                    base.advanced(by: written),
                    bytes.count - written
                )
            }
            if result > 0 {
                written += result
                continue
            }
            if result < 0, errno == EINTR { continue }
            if result < 0, errno == EAGAIN || errno == EWOULDBLOCK {
                usleep(2_000)
                continue
            }
            throw POSIXSerialError("write \(portPath ?? "serial port")")
        }
    }

    // MARK: - PABotBase2 message layer

    private func changeControllerMode(to mode: UInt32) throws {
        var message: [UInt8] = [0x08, 0x00, MessageOpcode.changeControllerMode, 0x00]
        message.append(contentsOf: Self.littleEndianBytes(mode))
        try sendStream(message: message)
        controllerMode = mode
    }

    private func queryControllerMode() throws -> UInt32 {
        let id = requestID
        requestID &+= 1
        uint32Responses.removeValue(forKey: id)
        try sendStream(message: [0x04, 0x00, MessageOpcode.readControllerMode, id])
        guard wait(until: { self.uint32Responses[id] != nil }, timeout: 0.80),
              let response = uint32Responses.removeValue(forKey: id)
        else {
            throw SerialBridgeError("读取 NS2 控制器模式超时")
        }
        return response
    }

    private func queryControllerStatus() throws -> Bool {
        let id = requestID
        requestID &+= 1
        uint32DataResponses.removeValue(forKey: id)
        try sendStream(message: [0x04, 0x00, MessageOpcode.requestStatus, id])
        guard wait(until: { self.uint32DataResponses[id] != nil }, timeout: 0.80),
              let response = uint32DataResponses.removeValue(forKey: id)
        else {
            throw SerialBridgeError("读取 NS2 有线手柄状态超时")
        }
        guard response.0 == Self.ns2WiredControllerID,
              let status = response.1.first
        else {
            return false
        }
        return status & 0x01 != 0
    }

    @discardableResult
    private func sendControllerState(_ state: [UInt8], milliseconds: UInt16) throws -> UInt8 {
        let id = commandID
        finishedCommands.remove(id)
        droppedCommands.remove(id)
        var message: [UInt8] = [0x0d, 0x00, MessageOpcode.wiredControllerState, commandID]
        commandID &+= 1
        message.append(contentsOf: Self.littleEndianBytes(milliseconds))
        message.append(contentsOf: state)
        try sendStream(message: message)
        return id
    }

    private func waitForCommand(_ id: UInt8, timeout: TimeInterval) throws {
        guard wait(
            until: {
                self.finishedCommands.contains(id) || self.droppedCommands.contains(id)
            },
            timeout: timeout
        ) else {
            throw SerialBridgeError("按键命令 \(id) 执行超时")
        }
        if droppedCommands.remove(id) != nil {
            throw SerialBridgeError("固件拒绝了按键命令 \(id)")
        }
        finishedCommands.remove(id)
    }

    private static let neutralState: [UInt8] = [
        0x00, 0x00, 0x08,
        0x80, 0x80, 0x80, 0x80,
    ]

    static func state(for button: ControllerButton) -> [UInt8] {
        var state = neutralState
        switch button {
        case .y: state[0] |= 1 << 0
        case .b: state[0] |= 1 << 1
        case .a: state[0] |= 1 << 2
        case .x: state[0] |= 1 << 3
        case .l: state[0] |= 1 << 4
        case .r: state[0] |= 1 << 5
        case .minus: state[1] |= 1 << 0
        case .plus: state[1] |= 1 << 1
        case .home: state[1] |= 1 << 4
        case .up: state[2] = 0
        case .right: state[2] = 2
        case .down: state[2] = 4
        case .left: state[2] = 6
        }
        return state
    }

    // MARK: - Encoding helpers

    static func makePacket(
        sequence: UInt8,
        opcode: UInt8,
        payload: [UInt8],
        crcSeed: UInt32
    ) -> [UInt8] {
        let fullLength = 4 + payload.count + 4
        precondition(fullLength <= 256)
        var packet: [UInt8] = [
            magic,
            sequence,
            UInt8(truncatingIfNeeded: fullLength),
            opcode,
        ]
        packet.append(contentsOf: payload)
        packet.append(contentsOf: littleEndianBytes(crc32c(packet, seed: crcSeed)))
        return packet
    }

    static func crc32c(_ bytes: [UInt8], seed: UInt32) -> UInt32 {
        var crc = seed
        for byte in bytes {
            crc ^= UInt32(byte)
            for _ in 0..<8 {
                crc = (crc >> 1) ^ ((crc & 1) == 1 ? 0x82f6_3b78 : 0)
            }
        }
        return crc
    }

    private static func littleEndianBytes(_ value: UInt16) -> [UInt8] {
        [UInt8(truncatingIfNeeded: value), UInt8(truncatingIfNeeded: value >> 8)]
    }

    private static func littleEndianBytes(_ value: UInt32) -> [UInt8] {
        [
            UInt8(truncatingIfNeeded: value),
            UInt8(truncatingIfNeeded: value >> 8),
            UInt8(truncatingIfNeeded: value >> 16),
            UInt8(truncatingIfNeeded: value >> 24),
        ]
    }

    private static func readUInt16(_ bytes: [UInt8], at offset: Int) -> UInt16 {
        UInt16(bytes[offset]) | UInt16(bytes[offset + 1]) << 8
    }

    private static func readUInt32(_ bytes: [UInt8], at offset: Int) -> UInt32 {
        UInt32(bytes[offset]) |
        UInt32(bytes[offset + 1]) << 8 |
        UInt32(bytes[offset + 2]) << 16 |
        UInt32(bytes[offset + 3]) << 24
    }
}

private struct SerialBridgeError: LocalizedError {
    let message: String
    init(_ message: String) { self.message = message }
    var errorDescription: String? { message }
}

private struct POSIXSerialError: LocalizedError {
    let operation: String
    let code: Int32

    init(_ operation: String, code: Int32 = errno) {
        self.operation = operation
        self.code = code
    }

    var errorDescription: String? {
        "\(operation) 失败：\(String(cString: strerror(code)))"
    }
}
