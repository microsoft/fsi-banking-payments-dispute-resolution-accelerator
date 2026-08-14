# Fenster decision note: resource identifier redaction and history squash (2026-08-14)

## Date
2026-08-14

## Context
Prior to public release, a sweep identified that the AZD-generated resource-name token
(embedded in all deployed Azure resource names), a managed subscription name, a tenant
domain, and two live Static Web App hostnames were still present in HEAD across 16 files.
Separately, the full commit history (278 commits) was determined to be unrecoverable from
a public-safety standpoint — it contained the above identifiers plus five previously-flagged
GUIDs and author email addresses in commit metadata. The user chose to redact HEAD then squash
the entire history to a single root commit before making the repository public.

## What was redacted (HEAD, Part 1)

**Resource-name token** — every Azure resource name containing the AZD deployment token was
replaced with a named placeholder. Affected resource types: Storage Account, Cosmos DB account,
Function App, AI Services account, Event Grid topic, Analyst SWA, Customer Portal SWA. FQDNs
were handled correctly (domain suffixes preserved, only the resource-name portion replaced).
Affected files: 16, spread across `.squad/` agent history, `.squad/decisions.md`,
`.squad/decisions/inbox/`, `.squad/log/`, `.squad/orchestration-log/`, `CHANGELOG.md`,
`README.md`, `docs/DOCUMENT_UPLOAD_HANDOFF.md`, `docs/architecture.md`,
`src/api/services/document_service.py`, `src/api/services/embeddings_client.py`,
`src/api/services/evidence_search_agent_client.py`, `src/web/playwright.config.ts`.

**Managed subscription name and tenant domain** — replaced with `<AZURE_SUBSCRIPTION_NAME>`
and `<AZURE_TENANT_DOMAIN>` respectively. Bare qualifier in prose rewritten to
"Managed Azure subscription tenants" / "the managed Azure subscription" for grammatical flow.

**Live Static Web App hostnames** — two hostnames replaced with `<ANALYST_SWA_HOSTNAME>`
and `<PORTAL_SWA_HOSTNAME>` in `docs/architecture.md` (Mermaid nodes + table), `README.md`,
`src/web/playwright.config.ts`, and `.squad/agents/` history files.

**Source file treatment (embeddings_client.py, evidence_search_agent_client.py):**
Per explicit user instruction, no structural refactoring. `DEFAULT_ENDPOINT` constants updated
in-place; env-var fallback mechanism and function signatures unchanged. Brief comment added to
each constant noting the documented env-var override path.

## What was squashed (Part 3)

The entire commit history was collapsed to a single orphan root commit. Steps:
1. `git checkout --orphan squash-root` — orphan branch off current (redacted) working tree.
2. `git add -A` — 392 files, 162,409 insertions.
3. Single initial commit with a clean, public-facing commit message describing the project.
4. `git branch -f main <squash-sha>` — main now points to the single root commit.
5. Verified: `git rev-list --count main` = 1, parent field empty, working tree clean,
   file count unchanged (392 before and after), all sensitive patterns absent.
6. `git push --force origin main`.

The squash permanently eliminates all prior commit messages, author emails in commit metadata,
and any sensitive values that survived in old commit bodies (including the five previously-
flagged GUIDs and 255 commits' worth of resource-name token occurrences).

## What was preserved

- Local branch `backup/pre-rewrite-main` — NOT pushed to origin; serves as a local pointer
  to the pre-squash history tree.
- `../disputes-pre-squash-backup.bundle` — full git bundle of all refs and complete history,
  created and verified before any destructive step. 4.9 MB.

## Ref cleanup

- Tag referencing the v1.1 release point: deleted locally and from origin.
- Tag referencing the prior delivery milestone: was local-only; deleted locally (was never
  on origin).
- Remaining remote refs after cleanup: `refs/heads/main` only. Confirmed with
  `git ls-remote --heads --tags origin`.
- Known exception: GitHub retains `refs/pull/103/*` for the prior PR — this is accepted
  and no attempt was made to delete it.

## Judgment calls

1. **Squash vs. filter-repo:** The user explicitly chose the full squash. `git-filter-repo`
   would have been an alternative for targeted history rewriting, but the user confirmed
   history has no ongoing value to the project.

2. **Source file constants not refactored:** `DEFAULT_ENDPOINT` constants in two Python files
   now hold placeholder strings rather than live endpoints. This means if someone runs the
   code without setting the env var, they get an obviously-invalid hostname rather than a
   live endpoint. This is the correct public-repo behaviour and matches the env-var
   documentation already present in each file's docstring.

3. **`backup/pre-rewrite-main` kept local-only:** Pushing it would defeat the purpose of
   removing history from origin. If the backup branch is ever needed, it exists locally
   and in the bundle.

4. **Records written after squash:** These history/decision records were added in a second
   commit on top of the squash root, so they describe the squash from outside it. No sensitive
   tokens appear in these records.
