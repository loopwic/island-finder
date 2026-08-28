// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "IslandControllerService",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "island-controller-service", targets: ["IslandControllerService"]),
    ],
    targets: [
        .target(
            name: "SerialPortShim",
            path: "Sources/SerialPortShim",
            publicHeadersPath: "include"
        ),
        .executableTarget(
            name: "IslandControllerService",
            dependencies: ["SerialPortShim"],
            path: "Sources/IslandControllerService"
        ),
    ],
    swiftLanguageVersions: [.v5]
)
