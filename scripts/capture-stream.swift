import AVFoundation
import Foundation
import VideoToolbox

struct Arguments {
    var deviceID = ""
    var deviceName = ""
    var width: Int32 = 1920
    var height: Int32 = 1080
    var sourceFPS = 30.0
    var outputFPS = 8.0
    var jpegQuality = 0.76
}

func parseArguments() -> Arguments {
    var result = Arguments()
    let values = Array(CommandLine.arguments.dropFirst())
    var index = 0
    while index + 1 < values.count {
        let key = values[index]
        let value = values[index + 1]
        switch key {
        case "--device-id": result.deviceID = value
        case "--device-name": result.deviceName = value
        case "--width": result.width = Int32(value) ?? result.width
        case "--height": result.height = Int32(value) ?? result.height
        case "--source-fps": result.sourceFPS = Double(value) ?? result.sourceFPS
        case "--output-fps": result.outputFPS = Double(value) ?? result.outputFPS
        case "--jpeg-quality": result.jpegQuality = Double(value) ?? result.jpegQuality
        default: break
        }
        index += 2
    }
    return result
}

private func jpegCompressionCallback(
    outputCallbackRefCon: UnsafeMutableRawPointer?,
    sourceFrameRefCon: UnsafeMutableRawPointer?,
    status: OSStatus,
    infoFlags: VTEncodeInfoFlags,
    sampleBuffer: CMSampleBuffer?
) {
    guard status == noErr,
          let outputCallbackRefCon,
          let sampleBuffer,
          CMSampleBufferDataIsReady(sampleBuffer)
    else { return }
    let writer = Unmanaged<JPEGStreamWriter>
        .fromOpaque(outputCallbackRefCon)
        .takeUnretainedValue()
    writer.write(sampleBuffer: sampleBuffer)
}

final class JPEGStreamWriter: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    private let output = FileHandle.standardOutput
    private let outputLock = NSLock()
    private let minimumInterval: Double
    private let quality: Double
    private var lastWrittenAt = -Double.infinity
    private var compressionSession: VTCompressionSession?

    init(outputFPS: Double, quality: Double) {
        // UVC's advertised "30 fps" duration is commonly 1000000/30000030,
        // not an exact 1/30. A strict floating-point comparison therefore
        // drops every other frame. The tolerance still caps faster sources
        // while allowing every frame from a nominal 30 fps mode through.
        minimumInterval = 0.9 / max(1, outputFPS)
        self.quality = max(0.35, min(0.95, quality))
    }

    func configure(width: Int32, height: Int32, fps: Double) -> Bool {
        var session: VTCompressionSession?
        let status = VTCompressionSessionCreate(
            allocator: kCFAllocatorDefault,
            width: width,
            height: height,
            codecType: kCMVideoCodecType_JPEG,
            encoderSpecification: nil,
            imageBufferAttributes: nil,
            compressedDataAllocator: nil,
            outputCallback: jpegCompressionCallback,
            refcon: Unmanaged.passUnretained(self).toOpaque(),
            compressionSessionOut: &session
        )
        guard status == noErr, let session else {
            fputs("ERROR jpeg-encoder-create status=\(status)\n", stderr)
            return false
        }
        VTSessionSetProperty(session, key: kVTCompressionPropertyKey_RealTime, value: kCFBooleanTrue)
        VTSessionSetProperty(
            session,
            key: kVTCompressionPropertyKey_Quality,
            value: NSNumber(value: quality)
        )
        VTSessionSetProperty(
            session,
            key: kVTCompressionPropertyKey_ExpectedFrameRate,
            value: NSNumber(value: fps)
        )
        guard VTCompressionSessionPrepareToEncodeFrames(session) == noErr else {
            VTCompressionSessionInvalidate(session)
            fputs("ERROR jpeg-encoder-prepare\n", stderr)
            return false
        }
        compressionSession = session
        return true
    }

    func write(sampleBuffer: CMSampleBuffer) {
        guard let blockBuffer = CMSampleBufferGetDataBuffer(sampleBuffer) else { return }
        let payloadLength = CMBlockBufferGetDataLength(blockBuffer)
        guard payloadLength > 0, payloadLength <= Int(UInt32.max) else { return }
        var payload = Data(count: payloadLength)
        let copyStatus = payload.withUnsafeMutableBytes { bytes in
            guard let destination = bytes.baseAddress else { return kCMBlockBufferBadPointerParameterErr }
            return CMBlockBufferCopyDataBytes(
                blockBuffer,
                atOffset: 0,
                dataLength: payloadLength,
                destination: destination
            )
        }
        guard copyStatus == kCMBlockBufferNoErr else { return }

        var length = UInt32(payloadLength).bigEndian
        let header = withUnsafeBytes(of: &length) { Data($0) }
        outputLock.lock()
        output.write(header)
        output.write(payload)
        outputLock.unlock()
    }

    func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        let timestamp = CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(sampleBuffer))
        guard timestamp.isFinite, timestamp - lastWrittenAt >= minimumInterval else { return }
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        lastWrittenAt = timestamp
        guard let compressionSession else { return }
        var flags = VTEncodeInfoFlags()
        VTCompressionSessionEncodeFrame(
            compressionSession,
            imageBuffer: pixelBuffer,
            presentationTimeStamp: CMSampleBufferGetPresentationTimeStamp(sampleBuffer),
            duration: CMSampleBufferGetDuration(sampleBuffer),
            frameProperties: nil,
            sourceFrameRefcon: nil,
            infoFlagsOut: &flags
        )
    }

    deinit {
        if let compressionSession {
            VTCompressionSessionCompleteFrames(
                compressionSession,
                untilPresentationTimeStamp: .invalid
            )
            VTCompressionSessionInvalidate(compressionSession)
        }
    }
}

let arguments = parseArguments()
let devices = AVCaptureDevice.DiscoverySession(
    deviceTypes: [.external],
    mediaType: .video,
    position: .unspecified
).devices
let device = devices.first(where: { !arguments.deviceID.isEmpty && $0.uniqueID == arguments.deviceID })
    ?? devices.first(where: { !arguments.deviceName.isEmpty && $0.localizedName == arguments.deviceName })

guard let device else {
    fputs("ERROR device-not-found name=\(arguments.deviceName) id=\(arguments.deviceID)\n", stderr)
    exit(2)
}

var authorization = AVCaptureDevice.authorizationStatus(for: .video)
if authorization == .notDetermined {
    let semaphore = DispatchSemaphore(value: 0)
    AVCaptureDevice.requestAccess(for: .video) { _ in semaphore.signal() }
    _ = semaphore.wait(timeout: .now() + 30)
    authorization = AVCaptureDevice.authorizationStatus(for: .video)
}
guard authorization == .authorized else {
    fputs("ERROR camera-permission status=\(authorization.rawValue)\n", stderr)
    exit(3)
}

guard let format = device.formats.first(where: { format in
    let dimensions = CMVideoFormatDescriptionGetDimensions(format.formatDescription)
    return dimensions.width == arguments.width
        && dimensions.height == arguments.height
        && format.videoSupportedFrameRateRanges.contains(where: {
            $0.minFrameRate - 0.1 <= arguments.sourceFPS && arguments.sourceFPS <= $0.maxFrameRate + 0.1
        })
}) else {
    fputs("ERROR unsupported-format \(arguments.width)x\(arguments.height)@\(arguments.sourceFPS)\n", stderr)
    exit(4)
}

let frameRate = format.videoSupportedFrameRateRanges.first(where: {
    $0.minFrameRate - 0.1 <= arguments.sourceFPS && arguments.sourceFPS <= $0.maxFrameRate + 0.1
})!

let session = AVCaptureSession()
session.beginConfiguration()
let input = try AVCaptureDeviceInput(device: device)
guard session.canAddInput(input) else {
    fputs("ERROR cannot-add-input\n", stderr)
    exit(5)
}
session.addInput(input)

let videoOutput = AVCaptureVideoDataOutput()
videoOutput.alwaysDiscardsLateVideoFrames = true
videoOutput.videoSettings = [
    // Keep the camera path in bi-planar YUV. Expanding 1080p to BGRA moves
    // about 8 MB per frame and is unnecessary for VideoToolbox JPEG encoding.
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange,
]
let writer = JPEGStreamWriter(outputFPS: arguments.outputFPS, quality: arguments.jpegQuality)
guard writer.configure(width: arguments.width, height: arguments.height, fps: arguments.outputFPS) else {
    exit(7)
}
let queue = DispatchQueue(label: "island-finder.capture.mjpeg")
videoOutput.setSampleBufferDelegate(writer, queue: queue)
guard session.canAddOutput(videoOutput) else {
    fputs("ERROR cannot-add-output\n", stderr)
    exit(6)
}
session.addOutput(videoOutput)

// Adding an output can make AVFoundation renegotiate an external camera back
// to 15 fps. Apply the chosen UVC format last so 1080p30 is the final device
// configuration committed by the session.
try device.lockForConfiguration()
device.activeFormat = format
// UVC devices may expose non-integer NTSC-style durations such as
// 1000000/30000030. Reuse the device-advertised duration exactly instead of
// constructing a nominal 1/30 CMTime that AVFoundation rejects.
device.activeVideoMinFrameDuration = frameRate.minFrameDuration
device.activeVideoMaxFrameDuration = frameRate.maxFrameDuration
device.unlockForConfiguration()

session.commitConfiguration()
session.startRunning()
// macOS may still choose its 15 fps default while starting an external UVC
// session. Reassert the advertised fixed 30 fps duration once the graph is
// running; AVCaptureDevice supports live frame-duration changes.
try device.lockForConfiguration()
device.activeFormat = format
device.activeVideoMinFrameDuration = frameRate.minFrameDuration
device.activeVideoMaxFrameDuration = frameRate.maxFrameDuration
device.unlockForConfiguration()
let activeDuration = device.activeVideoMinFrameDuration
let activeFPS = activeDuration.isValid && activeDuration.seconds > 0
    ? 1 / activeDuration.seconds
    : 0
fputs(
    "READY device=\(device.localizedName) id=\(device.uniqueID) "
        + "format=\(arguments.width)x\(arguments.height)@\(activeFPS) "
        + "selected-range=\(frameRate.minFrameRate)-\(frameRate.maxFrameRate) "
        + "protocol=length-prefixed-jpeg output-fps=\(arguments.outputFPS)\n",
    stderr
)
RunLoop.current.run()
