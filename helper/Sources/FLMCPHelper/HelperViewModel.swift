import Combine
import Foundation

@MainActor
final class HelperViewModel: ObservableObject {
    struct DiagnosticCheckPayload: Decodable, Equatable {
        let name: String
        let state: String
        let details: String
    }

    struct HelperStatusPayload: Decodable, Equatable {
        let service: String
        let health: String
        let timestamp: String
        let endpoint: String
        let checks: [DiagnosticCheckPayload]
        let logs: [String]
        let errors: [String]

        private enum CodingKeys: String, CodingKey {
            case service
            case health
            case timestamp
            case endpoint
            case checks
            case logs
            case errors
        }

        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            service = try container.decodeIfPresent(String.self, forKey: .service) ?? "fl-mcp"
            health = try container.decodeIfPresent(String.self, forKey: .health) ?? "error"
            timestamp = try container.decodeIfPresent(String.self, forKey: .timestamp) ?? ""
            endpoint = try container.decodeIfPresent(String.self, forKey: .endpoint) ?? "/v1/helper/status"
            checks = try container.decodeIfPresent([DiagnosticCheckPayload].self, forKey: .checks) ?? []
            logs = try container.decodeIfPresent([String].self, forKey: .logs) ?? []
            errors = try container.decodeIfPresent([String].self, forKey: .errors) ?? []
        }
    }

    enum CommandExecutionError: Error, LocalizedError, Equatable {
        case executionFailed(status: Int, stderr: String)
        case emptyOutput

        var errorDescription: String? {
            switch self {
            case .executionFailed(let status, let stderr):
                if stderr.isEmpty {
                    return "fl-mcp doctor failed with exit code \(status)"
                }
                return "fl-mcp doctor failed with exit code \(status): \(stderr)"
            case .emptyOutput:
                return "fl-mcp doctor produced no JSON output"
            }
        }
    }

    typealias CommandRunner = (_ endpoint: String) throws -> Data

    @Published var statusText: String = "Idle"
    @Published var logLines: [String] = ["Helper started"]
    @Published var lastErrorText: String?
    @Published var isRunning: Bool = false

    private let commandRunner: CommandRunner

    init(commandRunner: @escaping CommandRunner = defaultCommandRunner) {
        self.commandRunner = commandRunner
    }

    nonisolated static func doctorCommandArguments() -> [String] {
        ["uv", "run", "fl-mcp", "doctor", "--format", "json"]
    }

    func fetchStatus() {
        runDoctor(endpoint: "status")
    }

    func runDiagnostics() {
        runDoctor(endpoint: "diagnostics")
    }

    func processPayloadData(_ data: Data, sourceEndpoint: String) throws {
        let payload = try Self.decodePayload(from: data)
        applyPayload(payload, sourceEndpoint: sourceEndpoint)
    }

    func processFailure(_ error: Error, sourceEndpoint: String) {
        isRunning = false
        let message = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        statusText = "Error"
        lastErrorText = message
        logLines.append("Command failed for \(sourceEndpoint): \(message)")
    }

    nonisolated static func decodePayload(from data: Data) throws -> HelperStatusPayload {
        if data.isEmpty {
            throw CommandExecutionError.emptyOutput
        }
        return try JSONDecoder().decode(HelperStatusPayload.self, from: data)
    }

    /// Returns doctor stdout when it matches the status payload, including after a non-zero exit.
    /// A non-zero exit whose stdout is not that payload is rewritten as a failed `doctor` check.
    nonisolated static func commandResultData(
        stdout: Data,
        exitCode: Int,
        stderr: String
    ) throws -> Data {
        if isStatusPayload(stdout) {
            return stdout
        }
        if exitCode != 0 {
            return try failedDoctorCheckData(exitCode: exitCode, stderr: stderr)
        }
        if stdout.isEmpty {
            throw CommandExecutionError.emptyOutput
        }
        _ = try decodePayload(from: stdout)
        return stdout
    }

    private func runDoctor(endpoint: String) {
        isRunning = true
        lastErrorText = nil
        statusText = "Running \(endpoint)..."
        logLines.append("Invoking: \(Self.doctorCommandArguments().joined(separator: " "))")

        let runner = commandRunner
        Task {
            do {
                let data = try await Self.executeCommand(endpoint: endpoint, runner: runner)
                try processPayloadData(data, sourceEndpoint: endpoint)
            } catch {
                processFailure(error, sourceEndpoint: endpoint)
            }
        }
    }

    private func applyPayload(_ payload: HelperStatusPayload, sourceEndpoint: String) {
        isRunning = false
        statusText = "\(payload.health.uppercased()) • \(payload.endpoint)"

        if payload.logs.isEmpty {
            logLines.append("No logs returned for \(sourceEndpoint)")
        } else {
            logLines.append(contentsOf: payload.logs)
        }

        if payload.checks.isEmpty {
            logLines.append("No checks returned for \(sourceEndpoint)")
        } else {
            let summary = payload.checks.map { "\($0.name)=\($0.state)" }.joined(separator: ", ")
            logLines.append("Checks: \(summary)")
        }

        if payload.errors.isEmpty {
            lastErrorText = nil
        } else {
            let errorSummary = payload.errors.joined(separator: " | ")
            lastErrorText = errorSummary
            logLines.append("Errors: \(errorSummary)")
        }
    }

    private nonisolated static func executeCommand(
        endpoint: String,
        runner: @escaping CommandRunner
    ) async throws -> Data {
        try await Task.detached(priority: .userInitiated) {
            try runner(endpoint)
        }.value
    }

    private nonisolated static func isStatusPayload(_ data: Data) -> Bool {
        guard !data.isEmpty else {
            return false
        }
        return (try? JSONDecoder().decode(StrictHelperStatusPayload.self, from: data)) != nil
    }

    private nonisolated static func failedDoctorCheckData(exitCode: Int, stderr: String) throws -> Data {
        let detail: String
        if stderr.isEmpty {
            detail = "fl-mcp doctor exited with code \(exitCode) and did not return a status payload"
        } else {
            detail = "fl-mcp doctor exited with code \(exitCode) and did not return a status payload: \(stderr)"
        }
        let payload = FailedDoctorCheckPayload(
            service: "fl-mcp",
            health: "error",
            timestamp: ISO8601DateFormatter().string(from: Date()),
            endpoint: "fl-mcp doctor --format json",
            checks: [
                FailedDoctorCheckPayload.Check(name: "doctor", state: "error", details: detail)
            ],
            logs: [detail],
            errors: [detail]
        )
        do {
            return try JSONEncoder().encode(payload)
        } catch {
            throw CommandExecutionError.executionFailed(status: exitCode, stderr: stderr)
        }
    }

    private nonisolated static func defaultCommandRunner(_: String) throws -> Data {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.currentDirectoryURL = repositoryRootURL()
        process.arguments = doctorCommandArguments()

        let outputPipe = Pipe()
        let errorPipe = Pipe()
        process.standardOutput = outputPipe
        process.standardError = errorPipe

        try process.run()
        process.waitUntilExit()

        let stdoutData = outputPipe.fileHandleForReading.readDataToEndOfFile()
        let stderrData = errorPipe.fileHandleForReading.readDataToEndOfFile()
        let stderrText = String(decoding: stderrData, as: UTF8.self).trimmingCharacters(
            in: .whitespacesAndNewlines
        )

        return try commandResultData(
            stdout: stdoutData,
            exitCode: Int(process.terminationStatus),
            stderr: stderrText
        )
    }

    private nonisolated static func repositoryRootURL() -> URL {
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent() // FLMCPHelper
            .deletingLastPathComponent() // Sources
            .deletingLastPathComponent() // helper
    }
}

private struct StrictHelperStatusPayload: Decodable {
    struct Check: Decodable {
        let name: String
        let state: String
        let details: String
    }

    let service: String
    let health: String
    let timestamp: String
    let endpoint: String
    let checks: [Check]
    let logs: [String]
    let errors: [String]
}

private struct FailedDoctorCheckPayload: Encodable {
    struct Check: Encodable {
        let name: String
        let state: String
        let details: String
    }

    let service: String
    let health: String
    let timestamp: String
    let endpoint: String
    let checks: [Check]
    let logs: [String]
    let errors: [String]
}
