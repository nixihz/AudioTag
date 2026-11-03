import XCTest
@testable import AudioTagApp

final class UpdateConfigurationTests: XCTestCase {
    private var configuration: [String: Any] {
        ["SUFeedURL": "https://audiotag.xiezhixin.com/updates/appcast.xml",
         "SUPublicEDKey": Data(repeating: 7, count: 32).base64EncodedString(),
         "CFBundleVersion": "1"]
    }

    func testAcceptsHTTPSFeedWithPublicKey() {
        XCTAssertNotNil(UpdateConfiguration(info: configuration))
    }

    func testRejectsUnsafeOrIncompleteReleaseConfiguration() {
        for feed in ["http://audiotag.xiezhixin.com/updates/appcast.xml",
                     "https://user:password@audiotag.xiezhixin.com/feed",
                     "https://audiotag.xiezhixin.com/feed?token=temporary",
                     "https://audiotag.xiezhixin.com/feed#fragment"] {
            var info = configuration
            info["SUFeedURL"] = feed
            XCTAssertNil(UpdateConfiguration(info: info), feed)
        }
        var info = configuration
        info["SUPublicEDKey"] = Data(repeating: 7, count: 31).base64EncodedString()
        XCTAssertNil(UpdateConfiguration(info: info))
        info = configuration
        info.removeValue(forKey: "CFBundleVersion")
        XCTAssertNil(UpdateConfiguration(info: info))
    }
}
