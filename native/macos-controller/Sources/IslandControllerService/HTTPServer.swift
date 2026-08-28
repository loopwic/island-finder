import Darwin
import Foundation

struct HTTPRequest {
    let method: String
    let path: String
    let body: Data
}

struct HTTPResponse {
    let status: Int
    let body: Data

    static func json(status: Int = 200, _ object: Any) -> HTTPResponse {
        let data = (try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]))
            ?? Data("{\"error\":\"JSON encoding failed\"}".utf8)
        return HTTPResponse(status: status, body: data)
    }
}

final class LocalHTTPServer {
    typealias Handler = (HTTPRequest) -> HTTPResponse

    private let port: UInt16
    private let handler: Handler
    private let acceptQueue = DispatchQueue(label: "island-controller.http.accept")
    private let connectionQueue = DispatchQueue(
        label: "island-controller.http.connections",
        qos: .utility,
        attributes: .concurrent
    )
    private var listeningSocket: Int32 = -1
    private var acceptSource: DispatchSourceRead?

    init(port: UInt16, handler: @escaping Handler) {
        self.port = port
        self.handler = handler
    }

    func start() throws {
        let descriptor = socket(AF_INET, SOCK_STREAM, 0)
        guard descriptor >= 0 else { throw POSIXServerError("socket") }

        var reuse: Int32 = 1
        guard setsockopt(descriptor, SOL_SOCKET, SO_REUSEADDR, &reuse, socklen_t(MemoryLayout.size(ofValue: reuse))) == 0 else {
            Darwin.close(descriptor)
            throw POSIXServerError("setsockopt")
        }

        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = port.bigEndian
        address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))
        let bindResult = withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                bind(descriptor, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        guard bindResult == 0 else {
            Darwin.close(descriptor)
            throw POSIXServerError("bind 127.0.0.1:\(port)")
        }
        guard listen(descriptor, 16) == 0 else {
            Darwin.close(descriptor)
            throw POSIXServerError("listen")
        }

        let currentFlags = fcntl(descriptor, F_GETFL, 0)
        _ = fcntl(descriptor, F_SETFL, currentFlags | O_NONBLOCK)
        listeningSocket = descriptor

        let source = DispatchSource.makeReadSource(fileDescriptor: descriptor, queue: acceptQueue)
        source.setEventHandler { [weak self] in self?.acceptConnections() }
        source.setCancelHandler { Darwin.close(descriptor) }
        source.resume()
        acceptSource = source
    }

    func stop() {
        acceptSource?.cancel()
        acceptSource = nil
        listeningSocket = -1
    }

    private func acceptConnections() {
        while listeningSocket >= 0 {
            let client = accept(listeningSocket, nil, nil)
            if client < 0 {
                if errno == EAGAIN || errno == EWOULDBLOCK { return }
                return
            }
            guard prepareClient(client) else {
                Darwin.close(client)
                continue
            }
            connectionQueue.async { [weak self] in
                guard let self else {
                    Darwin.close(client)
                    return
                }
                self.serve(client)
            }
        }
    }

    private func prepareClient(_ client: Int32) -> Bool {
        // The listening descriptor must be non-blocking for DispatchSource, but
        // accepted descriptors can inherit O_NONBLOCK on macOS. Chrome commonly
        // delivers its HTTP headers in more than one packet, so a second recv()
        // can otherwise return EAGAIN and be mistaken for a disconnected client.
        let flags = fcntl(client, F_GETFL, 0)
        guard flags >= 0,
              fcntl(client, F_SETFL, flags & ~O_NONBLOCK) == 0
        else { return false }

        var noSigPipe: Int32 = 1
        _ = setsockopt(
            client,
            SOL_SOCKET,
            SO_NOSIGPIPE,
            &noSigPipe,
            socklen_t(MemoryLayout.size(ofValue: noSigPipe))
        )

        var timeout = timeval(tv_sec: 2, tv_usec: 0)
        _ = setsockopt(
            client,
            SOL_SOCKET,
            SO_RCVTIMEO,
            &timeout,
            socklen_t(MemoryLayout.size(ofValue: timeout))
        )
        _ = setsockopt(
            client,
            SOL_SOCKET,
            SO_SNDTIMEO,
            &timeout,
            socklen_t(MemoryLayout.size(ofValue: timeout))
        )
        return true
    }

    private func serve(_ client: Int32) {
        defer {
            _ = shutdown(client, SHUT_RDWR)
            Darwin.close(client)
        }

        var requestData = Data()
        var buffer = [UInt8](repeating: 0, count: 8_192)
        while requestData.count < 65_536 {
            let readCount = recv(client, &buffer, buffer.count, 0)
            if readCount < 0, errno == EINTR { continue }
            if readCount <= 0 { return }
            requestData.append(buffer, count: readCount)
            if let request = parseRequest(requestData) {
                write(responsePacket(handler(request)), to: client)
                return
            }
        }
        write(responsePacket(.json(status: 400, ["error": "无效或过大的 HTTP 请求"])), to: client)
    }

    private func parseRequest(_ data: Data) -> HTTPRequest? {
        let marker = Data("\r\n\r\n".utf8)
        guard let headerRange = data.range(of: marker),
              let headerText = String(data: data[..<headerRange.lowerBound], encoding: .utf8)
        else { return nil }

        let lines = headerText.components(separatedBy: "\r\n")
        guard let requestLine = lines.first else { return nil }
        let parts = requestLine.split(separator: " ")
        guard parts.count >= 2 else { return nil }

        let contentLength = lines.dropFirst().compactMap { line -> Int? in
            let pair = line.split(separator: ":", maxSplits: 1)
            guard pair.count == 2,
                  pair[0].trimmingCharacters(in: .whitespaces).lowercased() == "content-length"
            else { return nil }
            return Int(pair[1].trimmingCharacters(in: .whitespaces))
        }.first ?? 0

        let bodyStart = headerRange.upperBound
        guard data.count >= bodyStart + contentLength else { return nil }
        let body = contentLength == 0
            ? Data()
            : data.subdata(in: bodyStart..<(bodyStart + contentLength))
        return HTTPRequest(method: String(parts[0]), path: String(parts[1]), body: body)
    }

    private func responsePacket(_ response: HTTPResponse) -> Data {
        let reason: String
        switch response.status {
        case 200: reason = "OK"
        case 204: reason = "No Content"
        case 400: reason = "Bad Request"
        case 404: reason = "Not Found"
        case 409: reason = "Conflict"
        default: reason = "Service Unavailable"
        }
        let headers = [
            "HTTP/1.1 \(response.status) \(reason)",
            "Content-Type: application/json; charset=utf-8",
            "Content-Length: \(response.body.count)",
            "Access-Control-Allow-Origin: *",
            "Access-Control-Allow-Headers: Content-Type",
            "Access-Control-Allow-Methods: GET, POST, OPTIONS",
            "Access-Control-Allow-Private-Network: true",
            "Connection: close",
            "",
            "",
        ].joined(separator: "\r\n")
        var packet = Data(headers.utf8)
        packet.append(response.body)
        return packet
    }

    private func write(_ packet: Data, to client: Int32) {
        packet.withUnsafeBytes { rawBuffer in
            guard let base = rawBuffer.baseAddress else { return }
            var sent = 0
            while sent < packet.count {
                let result = Darwin.send(client, base.advanced(by: sent), packet.count - sent, 0)
                if result <= 0 { return }
                sent += result
            }
        }
    }
}

private struct POSIXServerError: LocalizedError {
    let operation: String
    let code: Int32

    init(_ operation: String) {
        self.operation = operation
        code = errno
    }

    var errorDescription: String? {
        "\(operation) 失败：\(String(cString: strerror(code)))"
    }
}
