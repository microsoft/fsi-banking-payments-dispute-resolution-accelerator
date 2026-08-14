# Fenster decision note: GUID purge phase 1 — residual identifiers missed by PR #103

## Date
2026-08-14

## Context
The public-repo-prep sweep (PR #103, merged) missed two live Azure identifiers that remained in `main` HEAD after merge. A follow-up direct commit was made to `main` to avoid creating a PR page that would render the removed values in its diff (which would recreate the exposure in a permanent `refs/pull/*` ref — exactly what happened with PR #103).

## What was found and redacted

**Subscription ID** — three locations:
- `src/api/services/document_service.py`: appeared in a module-level docstring (comment block). Verified purely decorative — not used functionally anywhere in the file. Replaced with `<AZURE_SUBSCRIPTION_ID>`.
- `HANDOFF.md`: appeared in the deployed environment table. Replaced with `<AZURE_SUBSCRIPTION_ID>`.
- `.squad/decisions.md`: appeared in a policy-evidence section header. Replaced with `<AZURE_SUBSCRIPTION_ID>`.

**Fabric workspace ID** — one location:
- `CHANGELOG.md`: appeared in the Fabric mirroring attempt entry. Replaced with `<FABRIC_WORKSPACE_ID>`.

**Internal program name and policy set name residuals** — seven files:
- `.squad/agents/fenster/history.md`: multiple occurrences of two internal program/policy names in historical notes.
- `.squad/agents/kobayashi/history.md`: one internal program name reference (old script name in a scan result).
- `.squad/agents/verbal/history.md`: two internal program name references.
- `.squad/decisions.md`: ten-plus occurrences of an internal program name and an internal policy set name.
- `.squad/decisions/inbox/fenster-remove-network-reconcile.md`: one internal program name reference.
- `.squad/decisions/inbox/verbal-architecture-diagram-correction.md`: one internal program name reference.
- `.squad/decisions/inbox/verbal-docs-delivery-scope.md`: one internal program name reference.

All occurrences were replaced with neutral equivalents: "organizational Azure Policy governance" for policy behavior descriptions, "the delivery program" / "the project team" for byline and program name references, and "the governance policy set" for the internal policy set name.

## Judgment calls

1. **Direct push to `main` vs. PR:** User explicitly requested direct commit. Rationale is sound — a PR diff page renders removed values and creates a permanent git ref. Direct commit avoids that exposure surface while a restore point (`v1.1` tag + `backup/pre-rewrite-main` branch) exists.

2. **Internal policy set name → `OrgGovDeployPolicies`:** This is a fictitious neutral stand-in. The surrounding analysis (DINE effect, auth-hardening targets) remains technically accurate — only the name is neutralized.

3. **`document_service.py` comment block:** Confirmed comment-only before redacting. Checked for any functional usage of the subscription ID value in the file — none found. Test suite passed (403 non-integration tests, 0 failures) confirming no behavioral change.

4. **Commit message discipline:** Raw GUID values and internal program names were NOT included in commit messages. Sensitive tokens are described generically throughout squad records.

## Consequence
- All five target GUIDs verified absent from working tree (confirmed with `git grep`).
- All internal program name and internal policy set name references confirmed absent outside seed/synthetic/test paths.
- `document_service.py` edit is comment-only; no functional code was modified.
- Test suite: 403 passed, 0 failed.
