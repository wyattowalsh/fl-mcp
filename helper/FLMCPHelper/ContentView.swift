import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("FL MCP Helper")
                .font(.headline)
            Text("Status: Runtime reachable")
            Text("Quick Actions: Install, Doctor, Open Logs")
        }
        .padding()
    }
}
