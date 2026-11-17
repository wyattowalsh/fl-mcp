# Facts

- The supported server remains the 12-tool compact FastMCP surface. This closeout does not add public tools.
- `spec.name` values such as `channels_list` stay stable. Capability checks must also accept `domain_operation`.
- Automatic rollback is not implemented. Messages and policy metadata must not claim a revert occurred.
- The installed controller polls `<hardware script dir>/bridge`. That directory is the shared default.
- Operator sign-off for a disposable scratch project, destructive-ops policy, and live-claim approval is outside this closeout.
- PyPI publishing and the `v0.1.0` tag are outside this closeout.
