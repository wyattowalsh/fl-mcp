import Foundation

@MainActor
final class HelperViewModel: ObservableObject {
    @Published var statusText: String = "Idle"
    @Published var logLines: [String] = ["Helper started"]

    func runInstallPlaceholder() {
        statusText = "Install placeholder triggered"
        logLines.append("TODO: invoke CLI install endpoint")
    }

    func runDiagnosticsPlaceholder() {
        statusText = "Diagnostics placeholder triggered"
        logLines.append("TODO: invoke CLI diagnostics endpoint")
    }
}
