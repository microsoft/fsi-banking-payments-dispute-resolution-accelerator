# Redfoot — README restructure for reader flow + fresh UI screenshots — 2026-07-09

## TL;DR
`README.md` should lead with the product story and visible analyst experience before setup details, and deployment guidance should be split cleanly from local-development guidance. I moved **Business Scenario** ahead of setup, kept **Quick Deploy** limited to the Azure path, broke **Local Development** into its own top-level section, and refreshed both embedded screenshots from the live analyst UI.

## Decision

### 1. README section order
Use this top-level flow near the top of the document:

1. `Solution Overview`
2. `Business Scenario`
3. `Quick Deploy`
4. `GitHub Actions CI/CD`
5. `Local Development`
6. `Guidance`
7. `Project Structure`
8. `Supporting Documentation`

This keeps the narrative progression: what the accelerator is, what the analyst sees, how to deploy it fast, how CI/CD works, and only then how to run or debug it locally.

### 2. Quick Deploy vs. Local Development boundary
- **Quick Deploy** owns only the Azure deployment path: deploy prerequisites, `azd up`, optional split `azd provision` / `azd deploy`, and teardown.
- **Local Development** owns the workstation toolchain and hands-on development workflow: Node/Python/Functions prerequisites, React local run/build, local dev modes, local Functions setup/tests, and Cosmos seeding.
- **GitHub Actions CI/CD** stays adjacent to deployment topics as its own section so it remains easy to find without bloating the quick-start path.

### 3. Screenshot refresh source
The README screenshots should reflect the currently deployed analyst UI, not older mock or pre-polish captures. I refreshed:
- `docs/images/readme/case-queue.png` from the populated **Active** queue tab
- `docs/images/readme/case-detail.png` from the corresponding **TravelNow LLC** case detail page

## Why this is worth recording
Future README edits should preserve the separation between "get it running in Azure quickly" and "develop/debug it locally." That boundary makes the document easier to scan for both demo/deployment audiences and contributors working on the codebase.
