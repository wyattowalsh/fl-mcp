import SwiftUI

@main
struct FLMCPHelperApp: App {
    @StateObject private var viewModel = HelperViewModel()

    var body: some Scene {
        WindowGroup("FL MCP Helper") {
            ContentView()
                .environmentObject(viewModel)
                .frame(minWidth: 700, minHeight: 420)
        }
    }
}
