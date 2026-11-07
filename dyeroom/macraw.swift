// Decode a camera raw with Apple's RAW engine (Core Image), for cameras LibRaw does not know yet.
// usage: macraw INPUT LINEAR_TIFF PREVIEW_PNG MAX_EDGE
// Writes scene-linear Rec.2020 float TIFF (no tone curve), a small default rendering for
// metering, and prints the as-shot white balance as JSON.
import CoreImage
import Foundation

let args = CommandLine.arguments
guard args.count == 5, let filter = CIRAWFilter(imageURL: URL(fileURLWithPath: args[1])) else {
    FileHandle.standardError.write("cannot decode\n".data(using: .utf8)!)
    exit(2)
}
let maxEdge = Double(args[4]) ?? 0
let native = filter.nativeSize
if maxEdge > 0 && max(native.width, native.height) > maxEdge {
    filter.scaleFactor = Float(maxEdge / max(native.width, native.height))
}
let temperature = filter.neutralTemperature
let tint = filter.neutralTint
let linear = CGColorSpace(name: CGColorSpace.extendedLinearITUR_2020)!
let context = CIContext(options: [.workingColorSpace: linear, .workingFormat: CIFormat.RGBAf])

// The camera-like rendering for metering, before switching the tone curve off.
if let preview = filter.outputImage {
    let small = preview.transformed(by: CGAffineTransform(scaleX: 0.25, y: 0.25))
    try context.writePNGRepresentation(of: small, to: URL(fileURLWithPath: args[3]), format: .RGBA8,
                                       colorSpace: CGColorSpace(name: CGColorSpace.sRGB)!)
}

filter.boostAmount = 0          // linear response, no film-like tone curve
filter.boostShadowAmount = 0
filter.isGamutMappingEnabled = false
guard let image = filter.outputImage else { exit(3) }
try context.writeTIFFRepresentation(of: image, to: URL(fileURLWithPath: args[2]), format: .RGBAf,
                                    colorSpace: linear)
print("{\"temperature\": \(temperature), \"tint\": \(tint), \"width\": \(Int(image.extent.width)), \"height\": \(Int(image.extent.height))}")
