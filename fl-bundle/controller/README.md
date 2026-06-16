# Controller Bundle

This bundle exposes the repo-owned FL Studio bridge command used by
`FL_MCP_FL_STUDIO_BRIDGE_CMD`.

- `device_FL_MCP_Bridge.py` is the FL Studio MIDI-script host. Install it under
  `Settings/Hardware/FL MCP Bridge/` and select `FL MCP Bridge` in MIDI
  Settings. It polls the request directory and runs safe FL API calls from
  inside the DAW Python host.
- Close FL Studio's Welcome window before expecting the MIDI script to
  initialize. The script writes `status.json` to its script-local `bridge/`
  directory when ready, and refreshes it with rate-limited polling heartbeat
  metadata while the script is actively selected.
- `python -m fl_mcp.bridge.host_client` is the MCP-side bridge command. It
  accepts the MCP JSON request as `argv[1]`, writes a request file, waits for the
  MIDI script response file, and prints one JSON response to stdout.
- The MCP-side client owns final request/response cleanup. Some FL Studio macOS
  hosts reject `rename`, `replace`, and `remove` from embedded Python even while
  normal direct file writes succeed.
- The MIDI script keeps persistent `fl_mcp_bridge.log` logging disabled by
  default. Set `FL_MCP_FL_STUDIO_BRIDGE_LOG=1` only for diagnostics; `status.json`
  remains the normal readiness and liveness signal.
- `fl_mcp_bridge_runner.py` remains a thin wrapper around the packaged
  `fl_mcp.bridge.runner` module for direct host diagnostics.
- Use `python -m fl_mcp.bridge.runner --mode harness` for deterministic
  live-harness validation outside FL Studio.
- Use `python -m fl_mcp.bridge.runner --mode live` from an FL Studio Python
  scripting host only for direct diagnostics. Normal live MCP use should go
  through `fl_mcp.bridge.host_client` plus `device_FL_MCP_Bridge.py`.
