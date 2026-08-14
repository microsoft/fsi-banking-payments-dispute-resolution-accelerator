# Decision: Public Repo Scope for `docs/delivery/`

**Date:** 2026-08-12
**Author:** Verbal (Lead / Architect)
**Branch:** `security/public-repo-prep`
**Status:** Decided

## Decision

Adopt **selective trim** for `docs/delivery/`.

Keep the technical companion material that helps public contributors understand and use the accelerator:

- `3-ARCHITECTURE-PACKAGE.md`
- `5-REUSABLE-CODE.md`
- `6-DEPLOYMENT-GUIDE.md`
- `8-LEARNING-LOG.md`
- `9-TECHNICAL-DEEP-DIVE.md`

Remove the audience-specific delivery collateral from the public repo:

- `1-BUSINESS-NARRATIVE.md`
- `2-DISCOVERY-KIT.md`
- `4-SECURITY-GOVERNANCE.md`
- `7-DEMO-KIT.md`
- `10-TEAM-DEMO-SCRIPT.md`
- `deliverables/Delivery-Package.docx`
- delivery-package generator scripts

## Rationale

The retained files are implementation-oriented and materially useful to an OSS reader: architecture, deployment, repo patterns, detailed interfaces, and lessons learned. The removed files are optimized for discovery, pre-sales, stakeholder demos, or aspirational governance packaging rather than the codebase itself.

`4-SECURITY-GOVERNANCE.md` was removed even though it contains technical content because it reads as delivery collateral, mixes current-state and aspirational controls, and is not the canonical technical source of truth for the repo. Public readers are better served by the architecture docs and technical deep dive than by a packaged compliance narrative.

Removing the bundled `.docx` and its generator scripts avoids leaving a broken or misleading public artifact after trimming the underlying markdown set.

## Implementation Notes

- Rewrote `docs/delivery/README.md` and `docs/delivery/DELIVERY-SUMMARY.md` so the folder clearly presents only public technical material.
- Scrubbed remaining project-context internal program name references from public-facing docs and infra comments; internal squad history/decision records remain the place for prior internal context.
