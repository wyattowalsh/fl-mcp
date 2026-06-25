# Security Policy

## Supported Versions

| Version   | Supported          |
| --------- | ------------------ |
| 0.1.x     | Yes                |

Only the latest pre-release or stable release receives security fixes.

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

Please report vulnerabilities through
[GitHub Security Advisories](https://github.com/wyattowalsh/fl-mcp/security/advisories/new).

When reporting, include:

- A description of the vulnerability and its impact.
- Steps to reproduce or a proof of concept.
- The version(s) affected.
- Any suggested mitigation or fix.

## Disclosure Policy

- We will acknowledge receipt within **3 business days**.
- We aim to provide an initial assessment within **10 business days**.
- We will coordinate disclosure timing with the reporter. We ask that reporters
  allow a reasonable window (typically 90 days) for a fix before public
  disclosure.
- Credit will be given to reporters in the release notes unless they prefer to
  remain anonymous.

## Scope

This policy applies to the `fl-mcp` Python package and its first-party
dependencies hosted in this repository. Third-party dependencies (e.g.,
FastMCP, Pydantic) should be reported to their respective maintainers.

## Deployment Modes

FL MCP supports two primary transports. Security expectations differ by mode.

### Stdio (default, recommended)

- The MCP server runs as a child process of the AI client.
- No network listener is opened by default.
- Authentication is optional and is typically enforced by the parent client
  process boundary rather than remote callers.
- This is the recommended mode for local FL Studio agent workflows.

### Streamable HTTP

- Enabled with `fl-mcp server run --mode streamable-http` (or `--mode http`).
- Defaults bind to loopback (`FL_MCP_HTTP_HOST=127.0.0.1`,
  `FL_MCP_HTTP_PORT=8765`, path `/mcp`).
- **Fail-closed default:** when `FL_MCP_AUTH_TOKEN` is unset, the server
  refuses to start HTTP mode unless you explicitly opt in with
  `FL_MCP_HTTP_ALLOW_UNAUTHENTICATED=true` for local development.
- **Loopback-only opt-out:** unauthenticated HTTP is permitted only when the
  bound host is loopback (`127.0.0.1`, `::1`, or equivalent). Binding to a
  non-loopback host without `FL_MCP_AUTH_TOKEN` exits with an error even when
  the opt-out flag is set.
- **Baseline expectation:** treat any non-loopback HTTP deployment as
  production-facing and require `FL_MCP_AUTH_TOKEN`.
- Tools and prompts enforce auth context when a token is configured. Resource
  auth parity is tracked in contract tests; verify behavior before advertising
  guarded HTTP deployments.

| Mode | Network exposure | Token required | Typical use |
| --- | --- | --- | --- |
| stdio | None (parent process) | Optional | Local agents, IDE clients |
| streamable HTTP (loopback, unauth opt-in) | Localhost only | Opt-out via `FL_MCP_HTTP_ALLOW_UNAUTHENTICATED` | Local HTTP dev only |
| streamable HTTP (loopback, token set) | Localhost only | **Required** (`FL_MCP_AUTH_TOKEN`) | Local guarded HTTP clients |
| streamable HTTP (LAN/WAN) | Remote reachable | **Required** | Not recommended without hardening |

## Bridge Trust Boundary

Live FL Studio execution crosses a subprocess and filesystem boundary:

1. MCP server invokes `FL_MCP_FL_STUDIO_BRIDGE_CMD` (default:
   `python -m fl_mcp.bridge.host_client`).
2. `host_client` writes typed JSON request files into a private bridge
   directory (`FL_MCP_FL_STUDIO_BRIDGE_DIR`). On POSIX, `host_client`
   enforces user ownership, rejects symlinks, and requires mode `0700`. On
   Windows, directory creation is **best-effort**: ownership and `0700` mode
   checks are skipped because POSIX metadata is unavailable.
3. The FL Studio MIDI script (`device_FL_MCP_Bridge.py`) polls that directory
   and executes allowed FL Python API calls inside the DAW host.

**Trust assumptions:**

- The bridge command is trusted configuration. Replacing it with an arbitrary
  subprocess grants that command the same authority as the MCP server process.
- The bridge directory must remain private to the current user. Symlinks and
  world-readable directories are rejected.
- Request and response JSON are treated as trusted only after schema
  validation. Do not point the bridge at shared or attacker-writable paths.
- The bundled controller script is part of the first-party trust boundary.
  Third-party bridge replacements must implement the same typed contracts
  documented in [bridge protocol](docs/content/docs/architecture/bridge-protocol.mdx).

**Optional idempotency:** bridge requests may include `idempotency_key`. When
provided, `host_client` (and the selected-controller adapter) sanitize the key,
derive a stable `request_id`, and bind retries to a **fingerprint**—a SHA-256
hash of the canonical `domain`, `operation`, and `payload` JSON.

- **In-flight deduplication:** while `request-{id}.json` or
  `response-{id}.json` still exists, duplicate submissions with the same key and
  matching fingerprint return the existing response instead of enqueueing a
  second DAW mutation.
- **Completed cache:** after cleanup, successful roundtrips may leave
  `completed-{id}.json` entries keyed by fingerprint. Retries within the TTL
  window (`FL_MCP_BRIDGE_IDEMPOTENCY_TTL_SECONDS`, default `3600`) replay the
  cached response without re-submitting to FL Studio.
- **Mismatch protection:** reusing an idempotency key with a different
  domain/operation/payload returns `error_code="idempotency_mismatch"` instead
  of silently executing the new request.
- **Invalid keys:** keys that normalize to empty (for example `###`) return
  `error_code="invalid_idempotency_key"` before any bridge I/O.

## FL Studio and Agent Safety

- Live mode advertises the full catalog as forced-live attempts. Only a small
  verified subset is smoke-safe; remaining operations are attemptable and may
  fail closed with structured errors.
- **Server-enforced `safety_mode`:** set `FL_MCP_SAFETY_MODE` to `standard`
  (default) or `strict`. The compact surface enforces this setting on
  **`fl_execute`** and **`fl_batch_execute`** for every non-read-only operation
  before bridge dispatch. In `strict` mode, destructive operations and unknown
  operation ids are rejected with `SafetyModeError`.
- **Transaction envelope `safety_mode`:** `fl_plan` and `fl_apply` envelopes may
  also carry `safety_mode`. For those transaction tools only, the effective
  policy is the **stricter** of the envelope value and `FL_MCP_SAFETY_MODE`
  (`strict` wins over `standard`). Envelope-only `relaxed` is rejected.
- Rollback class metadata and transaction checkpoints remain **advisory** for
  undo unless a specific workflow documents stronger guarantees. Do not assume
  rollback metadata implies automatic reversal in live FL Studio.
- Agents can mutate real project state through verified and attemptable live
  operations. Require explicit user intent before live Execute workflows.
- Browser, preset, sample, and path-oriented operations must respect validated
  filesystem paths. Do not pass unvalidated user paths into bridge payloads.

## HTTP Security Baseline

Before exposing streamable HTTP beyond a single trusted operator machine:

1. Set a strong `FL_MCP_AUTH_TOKEN` and store it only in client-side secret
   configuration. Do not rely on `FL_MCP_HTTP_ALLOW_UNAUTHENTICATED` outside
   single-operator loopback development.
2. Keep `FL_MCP_HTTP_HOST` on loopback unless a reverse proxy terminates TLS
   and enforces authentication. The server refuses unauthenticated non-loopback
   binds even when the opt-out flag is set.
3. Run `fl-mcp doctor --format json` after configuration changes.
4. Review contract tests under `tests/contract/` and HTTP auth matrix tests
   before claiming a guarded deployment.
5. Prefer stdio transport when the MCP client supports it.

## Dependency and Supply Chain

- Pin runtime dependencies through `uv.lock` for reproducible CI builds.
- Review bridge installer output from `fl-mcp install --dry-run` before copying
  controller scripts into FL Studio hardware directories.
- Report vulnerable third-party packages through their upstream maintainers;
  include affected `fl-mcp` versions when filing advisories here.