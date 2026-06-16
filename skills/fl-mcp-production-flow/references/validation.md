# Validation

Use this checklist for final workflow reports and setup audits.

## Required Evidence

| Workflow | Evidence |
| --- | --- |
| Setup | setup-check JSON, missing steps, client config |
| Rehearse | provider `mock`, operation ids, payloads, readback or task result |
| Execute | setup status, provider, bridge mode, operation id, request id, readback |
| Render | render task id, provider, output path, task status |
| Analyze | analysis id, input artifact, task status, result summary |
| Audit | distinction between mock and live evidence |

## Report Shape

```markdown
## Setup
- status:
- source:
- mode:
- safe_to_execute_mock:
- safe_to_attempt_live:
- missing_steps:

## Workflow Evidence
- operation_id:
- request_id:
- provider:
- bridge_mode:
- task_id:
- readback:

## Result
- completed:
- blocked_by:
- next_step:
```

## Final Checks

- Did Setup Gate run?
- Was schema lookup performed before execution?
- Is provider evidence present?
- Is live evidence separate from mock evidence?
- Is readback, snapshot, task, or analysis evidence present?
- Are missing steps concrete commands or client configuration actions?
