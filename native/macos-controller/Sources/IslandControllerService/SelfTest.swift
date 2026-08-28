import Foundation

enum ProtocolSelfTest {
    static func run() -> Bool {
        var failures: [String] = []
        func check(_ condition: @autoclosure () -> Bool, _ message: String) {
            if !condition() { failures.append(message) }
        }

        let resetPacket = PABotBase2SerialBridge.makePacket(
            sequence: 0,
            opcode: 0x01,
            payload: [0x44, 0x4e, 0x46, 0x49],
            crcSeed: 0xffff_ffff
        )
        check(
            resetPacket == [
                0x81, 0x00, 0x0c, 0x01, 0x44, 0x4e, 0x46, 0x49,
                0xab, 0x91, 0x18, 0xb5,
            ],
            "PABotBase2 CRC32C reset packet"
        )
        check(
            PABotBase2SerialBridge.state(for: .a) == [
                0x04, 0x00, 0x08, 0x80, 0x80, 0x80, 0x80,
            ],
            "PABotBase2 A button state"
        )
        check(
            PABotBase2SerialBridge.state(for: .left) == [
                0x00, 0x00, 0x06, 0x80, 0x80, 0x80, 0x80,
            ],
            "PABotBase2 left dpad state"
        )
        check(
            PABotBase2SerialBridge.state(for: .home) == [
                0x00, 0x10, 0x08, 0x80, 0x80, 0x80, 0x80,
            ],
            "PABotBase2 HOME button state"
        )
        check(
            Set(ControllerButton.allCases.map(\.rawValue)).count == ControllerButton.allCases.count,
            "controller button wire values are unique"
        )

        if failures.isEmpty {
            print("PABotBase2 protocol self-test: PASS")
            return true
        }
        for failure in failures {
            fputs("PABotBase2 protocol self-test failed: \(failure)\n", stderr)
        }
        return false
    }
}
