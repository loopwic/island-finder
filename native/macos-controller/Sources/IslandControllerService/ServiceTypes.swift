import Foundation

struct ControllerServiceStatus: Codable {
    var service = "island-controller-service"
    var version = "0.4.0"
    var platform = "macOS"
    var bluetoothPowered = false
    var privateAPIAvailable = false
    var pairingActive: Bool
    var consoleConnected: Bool
    var readyForInput: Bool
    var pairingRecordStored = false
    var diagnostic: String
    var transport = "pabotbase2"
    var serialPort: String?
}

enum ServiceError: Error, LocalizedError {
    case badRequest(String)
    case notReady(String)

    var errorDescription: String? {
        switch self {
        case let .badRequest(message), let .notReady(message):
            return message
        }
    }

    var httpStatus: Int {
        switch self {
        case .badRequest: return 400
        case .notReady: return 409
        }
    }
}
