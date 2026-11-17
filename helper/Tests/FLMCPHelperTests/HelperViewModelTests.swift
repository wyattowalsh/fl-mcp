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
        XCTAssertEqual(model.lastErrorText, "fl-mcp doctor produced no JSON output")
        XCTAssertFalse(model.isRunning)
    }

    @MainActor
    func testDecodePayloadRejectsEmptyData() {
        XCTAssertThrowsError(try HelperViewModel.decodePayload(from: Data()))
    }

    func testDoctorCommandArguments() {
        XCTAssertEqual(
            HelperViewModel.doctorCommandArguments(),
            ["uv", "run", "fl-mcp", "doctor", "--format", "json"]
        )
    }

    func testCommandResultDataKeepsPayloadWhenDoctorExitsNonZero() throws {
        let stdout = Data(doctorErrorJSON.utf8)
        let data = try HelperViewModel.commandResultData(stdout: stdout, exitCode: 1, stderr: "")
        let payload = try HelperViewModel.decodePayload(from: data)

        XCTAssertEqual(data, stdout)
        XCTAssertEqual(payload.health, "error")
        XCTAssertEqual(payload.checks.first?.name, "controller-byte-match")
        XCTAssertEqual(payload.checks.first?.state, "error")
    }

    @MainActor
    func testCommandResultDataShowsDoctorErrorPayload() throws {
        let model = HelperViewModel(commandRunner: { _ in Data() })
        let data = try HelperViewModel.commandResultData(
            stdout: Data(doctorErrorJSON.utf8),
            exitCode: 1,
            stderr: "health error"
        )
        try model.processPayloadData(data, sourceEndpoint: "diagnostics")

        XCTAssertEqual(model.statusText, "ERROR • /v1/helper/status")
        XCTAssertEqual(model.lastErrorText, "controller missing")
        XCTAssertTrue(model.logLines.contains(where: { $0.contains("controller-byte-match=error") }))
        XCTAssertFalse(model.isRunning)
    }

    func testCommandResultDataRecordsFailedCheckWhenStdoutIsNotPayload() throws {
        let data = try HelperViewModel.commandResultData(
            stdout: Data("not json".utf8),
            exitCode: 2,
            stderr: "boom"
        )
        let payload = try HelperViewModel.decodePayload(from: data)

        XCTAssertEqual(payload.health, "error")
        XCTAssertEqual(payload.endpoint, "fl-mcp doctor --format json")
        XCTAssertEqual(payload.checks.count, 1)
        XCTAssertEqual(payload.checks[0].name, "doctor")
        XCTAssertEqual(payload.checks[0].state, "error")
        XCTAssertTrue(payload.checks[0].details.contains("2"))
        XCTAssertTrue(payload.checks[0].details.contains("boom"))
        XCTAssertEqual(payload.errors, payload.checks.map(\.details))
    }

    func testCommandResultDataDoesNotTreatArbitraryJsonAsDoctorPayload() throws {
        let data = try HelperViewModel.commandResultData(
            stdout: Data(#"{"error":"nope"}"#.utf8),
            exitCode: 1,
            stderr: ""
        )
        let payload = try HelperViewModel.decodePayload(from: data)

        XCTAssertEqual(payload.checks.first?.name, "doctor")
        XCTAssertEqual(payload.checks.first?.state, "error")
        XCTAssertTrue(payload.checks.first?.details.contains("1") == true)
    }

    func testCommandResultDataThrowsWhenSuccessfulExitIsNotJson() {
        XCTAssertThrowsError(
            try HelperViewModel.commandResultData(stdout: Data("nope".utf8), exitCode: 0, stderr: "")
        )
    }

    func testCommandResultDataRejectsEmptySuccessOutput() {
        XCTAssertThrowsError(
            try HelperViewModel.commandResultData(stdout: Data(), exitCode: 0, stderr: "")
        ) { error in
            XCTAssertEqual(error as? HelperViewModel.CommandExecutionError, .emptyOutput)
        }
    }
}

private let doctorErrorJSON = """
{
  "service": "fl-mcp",
  "health": "error",
  "timestamp": "2026-03-10T00:00:00Z",
  "endpoint": "/v1/helper/status",
  "checks": [{"name": "controller-byte-match", "state": "error", "details": "missing"}],
  "logs": ["doctor"],
  "errors": ["controller missing"]
}
"""
