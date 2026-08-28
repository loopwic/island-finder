import Foundation

final class ServiceCoordinator {
    private let serialBridge: PABotBase2SerialBridge

    init(serialBridge: PABotBase2SerialBridge = PABotBase2SerialBridge()) {
        self.serialBridge = serialBridge
    }

    var status: ControllerServiceStatus {
        onMain {
            serialBridge.refresh()
            return ControllerServiceStatus(
                pairingActive: serialBridge.active,
                consoleConnected: serialBridge.consoleConnected,
                readyForInput: serialBridge.readyForInput,
                diagnostic: serialBridge.diagnostic,
                serialPort: serialBridge.portPath
            )
        }
    }

    func handle(_ request: HTTPRequest) -> HTTPResponse {
        if request.method == "OPTIONS" {
            return .json(["ok": true])
        }

        do {
            switch (request.method, request.path) {
            case ("GET", "/v1/status"):
                return try encodedStatus()
            case ("POST", "/v1/pairing/start"):
                try onMain { try serialBridge.start() }
                return try encodedStatus()
            case ("POST", "/v1/pairing/stop"):
                onMain { serialBridge.stop() }
                return try encodedStatus()
            case ("POST", "/v1/release-all"):
                onMain { serialBridge.releaseAll() }
                return .json(["ok": true])
            case ("POST", "/v1/press"):
                let command = try JSONDecoder().decode(PressCommand.self, from: request.body)
                guard command.type == "press" else {
                    throw ServiceError.badRequest("仅支持 press 命令")
                }
                try onMain {
                    try serialBridge.press(
                        command.button,
                        holdMilliseconds: command.holdMilliseconds
                    )
                }
                return .json(["ok": true])
            default:
                return .json(status: 404, ["error": "接口不存在"])
            }
        } catch let error as ServiceError {
            return .json(status: error.httpStatus, ["error": error.localizedDescription])
        } catch {
            return .json(status: 400, ["error": error.localizedDescription])
        }
    }

    func shutdown() {
        onMain { serialBridge.stop() }
    }

    private func encodedStatus() throws -> HTTPResponse {
        let data = try JSONEncoder().encode(status)
        let object = try JSONSerialization.jsonObject(with: data)
        return .json(object)
    }

    private func onMain<T>(_ work: () throws -> T) rethrows -> T {
        if Thread.isMainThread {
            return try work()
        }
        return try DispatchQueue.main.sync(execute: work)
    }
}

private struct PressCommand: Decodable {
    let type: String
    let button: ControllerButton
    let holdMilliseconds: Int

    private enum CodingKeys: String, CodingKey {
        case type
        case button
        case holdMilliseconds = "hold_ms"
    }
}
