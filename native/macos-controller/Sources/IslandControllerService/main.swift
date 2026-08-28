import Darwin
import Foundation

let coordinator = ServiceCoordinator()

if CommandLine.arguments.contains("--self-test") {
    exit(ProtocolSelfTest.run() ? EXIT_SUCCESS : EXIT_FAILURE)
}

if CommandLine.arguments.contains("--diagnose") {
    let data = try JSONEncoder().encode(coordinator.status)
    print(String(decoding: data, as: UTF8.self))
    exit(EXIT_SUCCESS)
}

let server = LocalHTTPServer(port: 32_145, handler: coordinator.handle)
do {
    try server.start()
} catch {
    fputs("无法启动本地控制接口：\(error.localizedDescription)\n", stderr)
    exit(EXIT_FAILURE)
}

signal(SIGINT, SIG_IGN)
signal(SIGTERM, SIG_IGN)
let signals = [SIGINT, SIGTERM].map { signalNumber -> DispatchSourceSignal in
    let source = DispatchSource.makeSignalSource(signal: signalNumber, queue: .main)
    source.setEventHandler {
        server.stop()
        coordinator.shutdown()
        exit(EXIT_SUCCESS)
    }
    source.resume()
    return source
}

print("Island Controller Service 已启动：http://127.0.0.1:32145")
print("连接 PABotBase2 后，在 Island Finder 中点击“启动配对”启用 NS2 有线手柄。")
withExtendedLifetime(signals) {
    RunLoop.main.run()
}
