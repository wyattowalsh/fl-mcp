import XCTest
@testable import FLMCPHelper

final class HelperViewModelTests: XCTestCase {
    @MainActor
    func testProcessPayloadDataUpdatesStatusAndLogs() throws {
        let model = HelperViewModel(commandRunner: { _ in Data() })
        let json = """
        {
          "service": "fl-mcp",
          "health": "ok",
          "timestamp": "2026-03-10T00:00:00Z",
          "endpoint": "/v1/helper/status",
          "checks": [{"name": "cli", "state": "ok", "details": "ready"}],
          "logs": ["line-a", "line-b"],
          "errors": []
        }
        """
        try model.processPayloadData(Data(json.utf8), sourceEndpoint: "status")

        XCTAssertEqual(model.statusText, "OK • /v1/helper/status")
        XCTAssertNil(model.lastErrorText)
        XCTAssertTrue(model.logLines.contains("line-a"))
        XCTAssertTrue(model.logLines.contains(where: { $0.contains("Checks:") }))
    }

    @MainActor
    func testProcessFailureSetsErrorState() {
        let model = HelperViewModel(commandRunner: { _ in Data() })
        model.processFailure(HelperViewModel.CommandExecutionError.emptyOutput, sourceEndpoint: "status")

        XCTAssertEqual(model.statusText, "Error")
        XCTAssertNotNil(model.lastErrorText)
        XCTAssertFalse(model.isRunning)
    }

    @MainActor
    func testDecodePayloadRejectsEmptyData() {
        XCTAssertThrowsError(try HelperViewModel.decodePayload(from: Data()))
    }
}
