# Decision: EasyAuth Async Race-Condition Fix — postprovision Hook

**Date:** 2026-07-09
**Author:** Keaton (Backend/Infra)
**Status:** Proposed
**Scope:** `azure.yaml`, `infra/modules/functions.bicep`, `infra/modules/staticwebapp.bicep`

---

## Context

The Function App (`<FUNCTION_APP_NAME>`) has an `authsettingsV2` Bicep resource (added in commit `03e6918`, see `infra/modules/functions.bicep` ~line 183) that explicitly disables EasyAuth v2 (`platform.enabled: false`, `unauthenticatedClientAction: AllowAnonymous`). This was put in place because linking the Function App as a Static Web App backend via `linkedBackends` causes Azure to auto-provision EasyAuth v2 with only that SWA registered as an allowed identity provider — silently 401/400-ing every other caller.

Despite this Bicep resource, **live production hit the bug again on 2026-07-09**: `az webapp auth show` showed `enabled: true, unauthenticatedClientAction: RedirectToLoginPage` with no identity providers configured, causing `POST /api/disputes` from the `portal` SWA to fail with HTTP 400.

---

## Root Cause

Azure's platform triggers an asynchronous EasyAuth reconciliation job when a `linkedBackends` association is created or updated. This job fires **after the ARM deployment completes** — it is NOT controlled by ARM ordering or `dependsOn`. The `authsettingsV2` Bicep resource correctly sets the desired state during ARM, but the async platform job runs afterward and overwrites it.

`dependsOn` reordering in Bicep **cannot fix this** — the race is between ARM completion and an out-of-band Azure platform job.

---

## Decision: postprovision azd Hook

**Chosen approach:** Add a `postprovision` hook in `azure.yaml` that:
1. Sleeps 90 seconds after `azd provision` completes (giving the async Azure job time to fire and settle)
2. Re-asserts `authsettingsV2` via `az rest PUT` (`platform.enabled: false`, `unauthenticatedClientAction: AllowAnonymous`)

This runs as part of every `azd provision` / `azd up` cycle and is idempotent.

**Rejected alternative — `Microsoft.Resources/deploymentScripts`:** A deploymentScript runs DURING the ARM deployment, which is still BEFORE Azure's async EasyAuth job fires. It would not win the race. Additionally, it requires a managed identity with appropriate RBAC, adding complexity.

**Rejected alternative — `dependsOn` reordering:** The async re-enable is not an ARM-ordering race. Reordering would have no effect.

---

## Files Changed

- `azure.yaml` — added `postprovision` hook (cross-platform: posix + windows variants)
- `.squad/agents/keaton/history.md` — learnings appended
- `.squad/decisions/inbox/keaton-easyauth-race-fix.md` — this file

**No Bicep changes** — the existing `authsettingsV2` resource in `infra/modules/functions.bicep` is correct and unchanged. It remains as the ARM-time guard and documents the auth model.

---

## Validation

After the next `azd provision` / CD run:
1. `AZD Provision` step runs ARM (authsettingsV2 resource sets correct state)
2. Azure async job fires and re-enables EasyAuth (the bug)
3. `postprovision` hook waits 90s, then PUTs correct state (the fix)
4. Verify: `az webapp auth show --name <func-app> --resource-group <rg> --query "properties.platform.enabled"` → `false`
5. Verify: `POST /api/disputes` from the portal SWA returns 201 Created (not 400)

---

## References

- Original EasyAuth fix: commit `03e6918`
- Bug recurrence: 2026-07-09 live production incident
- PR: see linked PR referencing this decision
