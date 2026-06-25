# Release Notes Draft — fl-mcp 0.1.0 (Tier B)

**Status:** Draft — requires HUMAN-T-911 sign-off before publication.

## Summary

First production-oriented release of the FL MCP compact surface: 12 visible MCP
tools backed by a 216-operation typed catalog across 16 domains.

## Live coverage (honest claims)

- **Mock catalog:** 216 operations via `provider="mock"` (full CI and agent dev)
- **Verified live:** 8 operations confirmed on the bundled host-file bridge
- **Attemptable live:** 208 additional operations return structured live errors
  when unsupported — no silent mock fallback in `flapi-live` mode

Do **not** claim "216 live DAW operations" or full live catalog success.

## Platform readiness (automated)

- pytest: 3422 tests pass
- coverage: 82.52% (gate ≥80%)
- surface probe: 55/55
- docs check: pass
- resource auth, HTTP token policy, safety_mode enforcement, batch limits

## Operator prerequisites (live)

1. Install/sync bundled `FL MCP Bridge` controller script
2. Select **FL MCP Bridge** in FL Studio MIDI Settings
3. Run `fl-mcp doctor --format json` until process + heartbeat checks pass
4. Complete scratch-project live evidence per Tier B runbook

## Human sign-off required

- [x] HUMAN-T-160 — Bridge selected + host read smoke (2026-06-25)
- [ ] HUMAN-T-310 — Disposable scratch project confirmed
- [x] HUMAN-T-311 — Live writes with readback (`transport.set_tempo`, 2026-06-25)
- [ ] HUMAN-T-312 — Destructive ops policy reviewed
- [ ] HUMAN-T-911 — Approve live claims in this document

## Tag policy

GATE-A/B/C automated and live gates pass. `v0.1.0` tag awaits operator
sign-off on HUMAN-T-310, HUMAN-T-312, and HUMAN-T-911.