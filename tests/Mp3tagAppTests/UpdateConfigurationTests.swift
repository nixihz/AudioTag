import XCTest
@testable import Mp3tagApp

final class UpdateConfigurationTests: XCTestCase {
    private var configuration: [String: Any] {
        ["SUFeedURL": "https://mp3tag.xiezhixin.com/updates/appcast.xml",
         "SUPublicEDKey": Data(repeating: 7, count: 32).base64EncodedString(),
         "CFBundleVersion": "1"]
    }

    func testAcceptsHTTPSFeedWithPublicKey() {
        XCTAssertNotNil(UpdateConfiguration(info: configuration))
    }

    func testRejectsUnsafeOrIncompleteReleaseConfiguration() {
        for feed in ["http://mp3tag.xiezhixin.com/updates/appcast.xml",
                     "https://user:password@mp3tag.xiezhixin.com/feed",
                     "https://mp3tag.xiezhixin.com/feed?token=temporary",
                     "https://mp3tag.xiezhixin.com/feed#fragment"] {
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
