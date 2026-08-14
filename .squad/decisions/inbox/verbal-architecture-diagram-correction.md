# Verbal — Correct `docs/architecture.md` to the Final Phase 1 Networking Model

**Date:** 2026-07-09  
**Branch:** `verbal/update-architecture-phase1-networking`  
**Status:** Implemented in docs only; pending PR review.

## Decision

`docs/architecture.md` should describe the **actual live Phase 1 demo architecture**, not the previously proposed private-networking design from PR #81.

## Why

The repository's confirmed working state is now different from the architecture doc:

- CD runs entirely on **GitHub-hosted runners**
- Storage and Cosmos both run with **`publicNetworkAccess: Enabled`**
- The real Azure Policy governance workaround is the **`SecurityControl: 'Ignore'`** tag propagated from `infra/main.bicep`
- Functions deploy via **`Azure/functions-action@v1` with `remote-build: true`**, not via an in-VNet self-hosted runner

Leaving the old diagram in place would create false operational assumptions during future infra cleanup, demo reviews, and security conversations.

## Implications

- The self-hosted runner, NAT Gateway, private endpoints, Cosmos private DNS remnants, and Function App VNet integration are **not** part of the live CD security path for Phase 1.
- Those artifacts remain as **tech debt**, with cleanup tracked in [Issue #86](https://github.com/yortch/payment-disputes/issues/86).
- Future documentation should treat the tag-bypass/public-access model as the authoritative Phase 1 baseline unless and until the runtime architecture changes again.
