# Kobayashi — History & Learnings

## Project Context
- **Project:** Payments Dispute Resolution (agentic evidence-assembly accelerator)
- **Lead developer:** Jorge Balderas
- **Stack:** Python · pytest · Azure Functions · Azure AI Foundry agents
- **Repo:** https://github.com/yortch/payment-disputes
- **Key compliance rules:** Reg E (10 business days) · Reg Z · Visa ~30d · MC 20-45d

## Learnings

### Sub-issue #44 — Re-verification Pass 2 (2026-07-06)

**Context:** Fenster applied the final kwarg fix (`context_name` / `client_name`).
Guard tests in `test_blueprint_types.py` now PASS. The `@bp.orchestration_trigger`
decorator now wraps `dispute_orchestrator` in a `FunctionBuilder` (not the raw generator),
so `_run_orchestrator()` was broken.

**Root cause identified (test harness, not production):**
`@bp.orchestration_trigger` wraps the user function via `Orchestrator.create()` which
produces a `FunctionBuilder`.  The FunctionBuilder is NOT the raw generator.

**Unwrap path (SDK source inspection):**
```
FunctionBuilder
  → .build(None).get_user_function()   # returns Orchestrator.create() handle
  → .orchestrator_function             # raw user-defined generator ✓
```

**Fix applied (test_orchestrator.py only):**
```python
from orchestrator.dispute_orchestrator import dispute_orchestrator as _fb
_dispute_orchestrator_raw = _fb.build(None).get_user_function().orchestrator_function
# _run_orchestrator now calls _dispute_orchestrator_raw(ctx) instead of dispute_orchestrator(ctx)
```

**Final state:** 210 tests, 210 passed, 0 failed, 0 skipped.
Only test files touched: `tests/test_orchestrator.py`. No production code modified.

**Context:** McManus fixed Bugs 1–3 (all three files now use `df.Blueprint()`).
The `func.Blueprint` monkeypatch in conftest.py was removed so the suite exercises
real blueprints as the Functions host would.

**Two new bugs surfaced immediately:**

- **Bug 4 (`dispute_orchestrator.py:34`):** `@bp.orchestration_trigger(context_parameter="context")`
  — `context_parameter` is not a valid kwarg for `df.Blueprint.orchestration_trigger`.
  Correct kwarg: `context_name`.  Causes `TypeError` at module import time.

- **Bug 5 (`case_actions.py:99,144,169,193`):** `@bp.durable_client_input(client_parameter="client")`
  — `client_parameter` is not a valid kwarg for `df.Blueprint.durable_client_input`.
  Correct kwarg: `client_name`.  4 occurrences, same TypeError.

**Guard test added:** `test_blueprint_types.py` — 3 test classes:
  - `TestBlueprintTypes`: imports each module's `bp` and asserts `isinstance(bp, df.Blueprint)`
  - `TestDecoratorSignatures`: verifies `context_name`/`input_name`/`client_name` are valid kwargs
    (prevents regression to wrong kwarg names without requiring a module import)
  - `TestModuleImports`: full module import smoke test

**Orchestrator tests restructured:** `test_orchestrator.py` wraps broken imports in try/except;
affected test classes use `@_skip_orch` / `@_skip_actions` marks with clear messages, so they show
as SKIPPED (not opaque collection ERROR) and auto-resolve once bugs are fixed.

**Final state (with monkeypatch removed):**
  - 4 FAILED (test_blueprint_types — the two bugs above)
  - 28 SKIPPED (orchestrator/action trigger tests awaiting bug fixes)
  - 178 PASSED

**Lesson:** No-op monkeypatches on Blueprint can mask wrong-class AND wrong-kwarg bugs simultaneously.
Guard tests must import the real module (not mock it) to be effective regression fences.

**What was tested:** Contract conformance, case_store read API, HITL orchestrator branching,
compliance/SLA checks, Visa 13.1 alignment, SPA build (tsc + Vite).

**Test structure:**
- `pytest.ini` + `conftest.py` in `src/api/` — `testpaths = tests`, `pythonpath = .`, `asyncio_mode = auto`
- `conftest.py` patches `azure.functions.Blueprint` with no-op stubs for durable decorators
  (`orchestration_trigger`, `activity_trigger`, `durable_client_input`) at module level so
  production code imports cleanly without a live Functions host.
- `case_store._load_all` LRU cache cleared via `autouse` fixture to isolate tests.

**Orchestrator mocking approach:**
- `dispute_orchestrator` is a Python generator; drove it manually with `next()` / `gen.send()`.
- `MockOrchestratorContext` records `activities_called` and controls which task wins `task_any`
  (via `scenario` param: `"approve"`, `"deny"`, `"escalate"`, `"timeout"`).
- `MockTask.result` returns the inner decision/timeout task; identity comparison in orchestrator
  (`winner == decision_task`) uses Python default object identity — no `__eq__` needed.

**Bugs found in production code (to be fixed by Keaton / McManus):**
1. `src/api/orchestrator/dispute_orchestrator.py`: `bp = func.Blueprint()` — uses `azure.functions.Blueprint`
   which lacks `orchestration_trigger`. Must use `azure.durable_functions.Blueprint` (`df.Blueprint()`).
2. `src/api/activities/case_activities.py`: same issue — `bp = func.Blueprint()` lacks `activity_trigger`.
3. `src/api/triggers/case_actions.py`: `bp = func.Blueprint()` lacks `durable_client_input`.
   All three must use `df.Blueprint()` (or `df.DFApp`) for the durable decorators to resolve.

**SPA test:**
- On Windows, `subprocess.run(["npm", ...])` raises `FileNotFoundError` — must use `npm.cmd`.
  Fixed in test; production CI should use `shell=True` or `npm.cmd` on Windows agents.

**Final result:** 201 tests, 201 passed, 0 failed.


📌 Team update (2026-07-06T22:58:00Z): Story #21 finalized — kwarg fix merged, E2E suite 210/210 passed, PR #45 opened develop→main — decided by Scribe in coordination with Fenster, Kobayashi, McManus, Redfoot

---

### Public-repo prep QA pass — branch `security/public-repo-prep` (2026-08-12)

**Trigger:** Fenster committed `2b94710` removing sensitive artifacts and redacting internal program references ahead of making the repo public.

**Checks performed and outcomes:**

1. **`.env.sample` coverage** — ✅ PASS
   - `src/customer-portal/.env` had 2 keys: `VITE_USE_MOCK=false`, `VITE_API_BASE_URL=http://localhost:7071/api`.
   - `src/customer-portal/.env.sample` covers both (`VITE_USE_MOCK` as uncommented default, `VITE_API_BASE_URL` as commented example).
   - `src/web/.env` had only `VITE_USE_MOCK=false` — `src/web/.env.sample` covers it.
   - `src/customer-portal/.env.production.local` contained a live Azure Functions URL (correctly deleted; regenerated by `azure.yaml` `prepackage` hook at deploy time — hook verified intact).

2. **App ZIP reference scan** — ✅ PASS (benign)
   - Only reference to `20485227-3f9a-4894-b487-04c8ae2287d5-app.zip` is in `.squad/agents/fenster/history.md` (Fenster's own learnings note). No script, workflow, or doc references it operationally.

3. **Old script name references** — ✅ PASS (benign)
   - Only reference to `generate-delivery-word.*` is in `.squad/agents/fenster/history.md`. No `package.json`, CI workflow, or other script calls the old name.

4. **Test suite** — ✅ PASS
   - `pytest --collect-only`: 409 tests collected, 0 collection errors.
   - `pytest tests -k "not integration"`: **403 passed, 6 deselected, 0 failed** (ran in ~107s).

5. **`azure.yaml` prepackage hook** — ✅ PASS
   - Hook at lines 38–46 correctly regenerates `.env.production.local` from `$AZURE_FUNCTION_APP_URI` for both bash and PowerShell environments.

**No issues found. Repo is safe to make public.**

**Lesson:** When deleting `.env` files for public-repo prep, confirm `.env.sample` covers every variable name (not necessarily the same value). Production-only env files (`.env.production.local`) can be safely deleted if an IaC/deploy hook regenerates them — verify the hook exists and is correct.