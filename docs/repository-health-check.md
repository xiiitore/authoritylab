# Repository health check

`scripts/repository_health_check.py` is a fast, dependency-free preflight for the repository's minimum documentation/CI surface and capability-inventory invariants.

Run from the repository root:

```bash
python scripts/repository_health_check.py
python -m unittest -v tests.test_repository_health_check
```

The checker verifies that required governance, architecture, verification, CI, schema, and test artifacts exist. It also checks the capability registry's schema-version marker, inventory-only status, entry count, unique nonempty tool IDs, provider counts, and explicit `execution_verified: false` declarations.

## Interpretation

- Exit code `0`: the checked repository contract is internally consistent.
- Exit code `1`: one or more required artifacts or invariants failed.
- The output deliberately avoids dumping registry contents or exception messages.

This is an inexpensive structural preflight. It does **not** validate the full JSON Schema, import every module, execute tools, assess permissions, prove provenance, or replace CI, unit tests, CodeQL, threat modeling, or deployment-specific security review. The full registry schema remains checked by `tests/test_capability_registry.py`.
