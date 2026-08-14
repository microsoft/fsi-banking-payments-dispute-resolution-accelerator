# Fenster decision note: remove obsolete `network-reconcile.yml`

## Date
2026-07-09

## Decision
Remove `.github/workflows/network-reconcile.yml`.

## Why
- The workflow was an explicitly temporary Phase 0 stopgap whose own header said it must be
  removed once the longer-term fix was deployed.
- PR #80's `SecurityControl: 'Ignore'` tag-bypass is now confirmed stable: organizational Azure Policy governance is
  no longer forcing Storage/Cosmos `publicNetworkAccess` back to `Disabled`.
- PR #83 fixed the unrelated FC1 deployment mechanism by switching Functions deploys to
  `Azure/functions-action@v1` with `remote-build: true`, and the full GitHub-hosted CD pipeline
  completed green end-to-end on 2026-07-09 (including Cosmos seed with real records).
- Leaving the cron in place would only add unnecessary Azure control-plane churn and can interfere
  with troubleshooting by repeatedly touching Cosmos network settings.

## Consequence
- CD/runtime no longer depend on the reconcile workflow.
- Future network regressions should be treated as fresh incidents, not silently papered over by a
  cron job.
