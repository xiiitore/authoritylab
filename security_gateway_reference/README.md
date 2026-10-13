# Security Gateway Reference (test-only)

This module is an isolated reference prototype for testing authorization and idempotency boundaries. It is **not production-ready** and must not be connected to real sensitive operations.

## Run

From the repository root after adding this directory:

```sh
python -m unittest -v security_gateway_reference.test_gateway
```

## Contracts and limitations

- `StaticVerifier` is a test double. It does not implement JWT/JWS verification, trusted `kid` resolution, algorithm restrictions, or KMS rotation.
- A production verifier must validate the exact signed token and return claims from that same verified payload. Do not accept caller-supplied metadata separately from the token.
- Revocation, trusted time, subject permissions, issuer, audience, token lifetime, operation allow-list, and signed target scope are checked before reservation.
- The critic may veto but cannot authorize. Only the execution core commits after the critic returns exactly `VALIDATION_PASS`.
- Request reservation, nonce consumption, and the example effect are coordinated with SQLite transactions and unique constraints. The example effect is an audit row, not a real business operation.
- A `PENDING` request yields `UNKNOWN` and requires reconciliation; it is never blindly retried.
- SQLite tests do not prove correctness of a distributed database or a production business transaction. The real effect and idempotency record must share one transaction boundary or use an equivalent proven protocol.
- Context isolation is not implemented or certified by this module.

## Current verification

The unit tests exercise invalid audience/issuer/scope, revoked tokens, revocation outage, temporal boundaries, unverified signatures, critic overreach, idempotent retries, nonce replay, request fingerprint conflicts, pending reconciliation, and two SQLite connections. Passing these tests is evidence only for these test paths, not a production security certification.
