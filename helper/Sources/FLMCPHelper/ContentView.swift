import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var viewModel: HelperViewModel

    var body: some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 12) {
                Text("FL MCP Helper")
                    .font(.title)
                Text("Status: \(viewModel.statusText)")
                    .foregroundStyle(.secondary)
                if let errorText = viewModel.lastErrorText {
                    Text("Error: \(errorText)")
                        .foregroundStyle(.red)
                        .font(.footnote)
                }

                HStack {
                    Button("Check Status") {
                        viewModel.fetchStatus()
                    }
                    .keyboardShortcut("i", modifiers: [.command])
                    .disabled(viewModel.isRunning)

                    Button("Run Diagnostics") {
                        viewModel.runDiagnostics()
                    }
                    .keyboardShortcut("d", modifiers: [.command])
                    .disabled(viewModel.isRunning)
                }

                Spacer()
            }
            .frame(maxWidth: 260, maxHeight: .infinity, alignment: .topLeading)

            VStack(alignment: .leading, spacing: 8) {
                Text("Log")
                    .font(.headline)
                List(viewModel.logLines, id: \.self) { line in
                    Text(line)
                        .font(.system(.body, design: .monospaced))
                }
            }
        }
        .padding(20)
    }
}
