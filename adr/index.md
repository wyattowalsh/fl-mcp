# ADR Index

This index tracks architecture decision records (ADRs) for major lock-ins.

## Initial Lock-In ADRs

1. **ADR-0001: Resources-First Architecture**  
   Status: Proposed  
   Summary: Prioritize resources as the primary integration and composition mechanism.

2. **ADR-0002: Canonical Graph Model**  
   Status: Proposed  
   Summary: Standardize on a canonical graph representation for entity and relationship interoperability.

3. **ADR-0003: Canonical Transaction Envelope**  
   Status: Proposed  
   Summary: Enforce a canonical envelope for transaction metadata, payload, and lifecycle state.

4. **ADR-0004: Small Public Tool Surface**  
   Status: Proposed  
   Summary: Keep the externally exposed tool surface intentionally small and review-gated.

## Conventions

- ADR IDs are zero-padded and monotonically increasing.
- Any architecture lock-in must have an ADR before broad adoption.
- Superseding an ADR must reference both old and new ADR IDs.
