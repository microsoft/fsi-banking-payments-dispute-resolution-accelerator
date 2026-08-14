# Tests — Disputes API

End-to-end / integration test suite for the Story #21 analyst-review vertical slice.

## Quick start

```bash
cd src/api
pip install -r requirements-dev.txt
pytest
```

## What is tested

| File | Scope |
|------|-------|
| `test_contract_conformance.py` | Every synthetic case validates against `case.schema.json`; Python dataclasses round-trip; `CaseSummary` projection shape |
| `test_case_store.py` | Loader parses all 10 fixtures; `list_cases()` count & shape; `?status=pending_review` filter; `get_case()` 200 / 404; live `daysRemaining` |
| `test_orchestrator.py` | Orchestrator branching (approve→submitted, deny→denied, escalate→escalated, timeout→expired); action trigger helpers (`_parse_body`, `_require_analyst_id`, `_raise_analyst_decision`) |
| `test_compliance.py` | SLA/near-expiry detection; evidence-gap completeness; checklist alignment; Visa 13.1 specific checks |
| `test_spa_build.py` | `npm run build` in `src/web` exits 0 (skipped if npm unavailable) |

## Running a subset

```bash
# Schema conformance only
pytest tests/test_contract_conformance.py -v

# Orchestrator only
pytest tests/test_orchestrator.py -v

# Compliance only
pytest tests/test_compliance.py -v

# SPA build check
pytest tests/test_spa_build.py -v -s
```

## Notes

- **Durable Functions mocking:** `conftest.py` patches `azure.functions.Blueprint` with
  no-op stubs for `orchestration_trigger`, `activity_trigger`, and `durable_client_input`
  so production modules import without a live Functions host.
- **LRU cache isolation:** `conftest.py` clears `case_store._load_all` cache before and
  after each test.
- **Async tests:** `pytest-asyncio` is configured in `auto` mode (`pytest.ini`).
