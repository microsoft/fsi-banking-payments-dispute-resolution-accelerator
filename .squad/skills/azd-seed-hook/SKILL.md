# Skill: AZD Postdeploy Seed Hook (Python + Cosmos)

**Category:** DevOps / Infrastructure  
**Author:** Fenster  
**Date:** 2026-07-07

> **Update (2026-07-09):** The top-level `postdeploy` hook described below was removed from
> `azure.yaml` — it fired after every `azd deploy <service>`, including `web`/`portal` on the
> GitHub-hosted runner, breaking CD once Cosmos went private. Seeding is now handled solely by
> the `deploy-api` job in `.github/workflows/cd.yml` (self-hosted, in-VNet runner). The pattern
> below (seed script design, upsert idempotency, env var reconciliation) is still accurate for
> the script itself — only the "wire to `azure.yaml`" hook step and the "double-run is harmless"
> claim are now obsolete.

---

## Pattern: Idempotent Cosmos seed wired as an azd postdeploy hook

### Problem

After `azd up`, a freshly provisioned Cosmos container is empty. You want synthetic / seed data automatically inserted on every clean deploy, without re-seeding breaking anything on subsequent runs.

### Solution

1. **Add `upsert_item` helper to `cosmos_client.py`** — one function, always idempotent:
   ```python
   def upsert_dispute(dispute: dict) -> dict:
       return _get_container("disputes").upsert_item(body=dispute)
   ```

2. **Write a seed script** at `src/api/scripts/seed_cosmos.py`:
   - Soft-fail if endpoint is absent (check both `COSMOS_ENDPOINT` and `AZURE_COSMOS_ENDPOINT`)
   - Defer `import cosmos_client` until after env vars are set (preserves testability)
   - Build documents per contract: `doc = {**case, "id": caseId, "disputeId": caseId, "networkCode": cardNetwork}`
   - Call `upsert_dispute(doc)` per item

3. **Reconcile env var names** — azd exposes Bicep outputs with AZURE_ prefix; the client may expect shorter names. In `_resolve_env()`:
   ```python
   endpoint = os.environ.get("COSMOS_ENDPOINT") or os.environ.get("AZURE_COSMOS_ENDPOINT", "")
   os.environ["COSMOS_ENDPOINT"] = endpoint  # set before deferred import
   ```

4. **Wire to `azure.yaml`** with posix/windows split. Use `continueOnError: false` once runner deps are installed (see Key rules):
   ```yaml
   hooks:
     postdeploy:
       posix:
         shell: sh
         run: cd src/api && PYTHONPATH=. python3 scripts/seed_cosmos.py
         continueOnError: false
       windows:
         shell: pwsh
         run: |
           $env:PYTHONPATH = "src\api"
           python src\api\scripts\seed_cosmos.py
         continueOnError: false
   ```

### Key rules

| Rule | Why |
|------|-----|
| **Prefer an explicit CD step over the azd postdeploy hook in CI** | The postdeploy hook output is invisible in CD runs (no log capture), and `continueOnError: true` silently swallows failures. An explicit `- name: Seed Cosmos DB` step after AZD Deploy shows output in the job log and fails loudly on non-zero exit. Keep the azure.yaml hook only for local `azd up` convenience — the double-run is harmless (upsert idempotency). |
| Install app deps on CI runner before azd deploy | The postdeploy hook runs on the same runner; `ubuntu-latest` does NOT have `azure-cosmos` / `azure-identity`. Add `actions/setup-python@v5` + `pip install -r requirements.txt` steps before the AZD Deploy step in `cd.yml`. Without this, imports fail silently. |
| Use `python3` in posix hooks, not `python` | Bare `python` is absent on `ubuntu-latest`; `python3` is the reliable alias. |
| `continueOnError: false` once deps are installed | With runner deps in place, a non-zero exit means a real problem. Use `false` so genuine failures (import errors, RBAC 403, upsert exception) fail the deploy visibly. The script's own `sys.exit(0)` on missing endpoint handles the soft-fail case — no need to swallow all errors at the hook level. |
| `continueOnError: true` only during bootstrap | Acceptable temporarily if RBAC propagation is known to lag and you have no retry wrapper. Remove as soon as possible. |
| Defer `import cosmos_client` | Avoids `DefaultAzureCredential` construction at import time — critical for test mocking |
| Soft-fail on missing endpoint | Enables running `azd up` from repo without Cosmos (e.g. local-only dev) |
| Upsert not insert | Re-running the hook is always safe; no duplicate-key errors |

### Testing

Mock `cosmos_client` before import with `sys.modules`:
```python
stub = MagicMock()
monkeypatch.setitem(sys.modules, "cosmos_client", stub)
import scripts.seed_cosmos as seed_mod
monkeypatch.setattr(seed_mod, "cosmos_client", stub, raising=False)
```

Assert `stub.upsert_dispute.call_count == len(cases)` and verify document shape.

Soft-fail test: confirm `SystemExit(0)` is raised (not an exception) when endpoint unset.
