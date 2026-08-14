# Redfoot — Fresh Transactions + Dispute Filter — 2026-07-09

## TL;DR
Replace the static 6-transaction demo list in the customer portal with a random generator, and filter out already-disputed transactions using localStorage so testers always have fresh, disputable transactions and never hit a backend 409 from re-disputing the same charge.

## Decision

### 1. Random generation over a static seed list
`generateDemoTransactions(count)` in `mocks/transactions.ts` replaces the static `demoTransactions` array. The function picks randomly from a 12-entry MERCHANT_POOL (original 6 merchants + 6 new: FitGear Pro, HomeStyle Furnishings, QuickFuel Station, MediCare Pharmacy, PetPals Supplies, SkySafe Insurance), with per-category amount ranges, random date within the last 30 days, random card network, and random last-four digits.

Rationale: static lists run dry fast in a demo/test context; random generation with a wide enough state space makes dedupe collisions negligible without needing any hash-check logic.

### 2. localStorage as the persistence layer (demo-only)
Key: `disputedTransactionKeys` (JSON array of strings).
Dedupe key format: `network|last4|amount|date|merchant` — mirrors backend fields, reasonCode excluded so any dispute for a transaction suppresses it.

This is explicitly a demo mechanism. Clearing browser storage resets it. No server-side persistence is introduced.

### 3. Filter + backfill pattern in SelectTransactionPage
Generate TARGET_COUNT + disputed.size + 6 candidates, filter, slice to TARGET_COUNT (6). Using `useState` lazy initializer (not `useEffect`) ensures the computation is synchronous and happens exactly once per mount.

### 4. Record on submit success, not on confirmation mount
`markTransactionDisputed(transaction)` is called in `ReviewPage.handleSubmit()` immediately after `submitDispute()` resolves — before `navigate('/confirmation')`. This avoids double-recording if the confirmation page is revisited/reloaded.

## Why this is worth recording
Future portal work (real account API, persistence layer) should replace this pattern rather than extend it. The localStorage key `disputedTransactionKeys` is the interface point — a real implementation would read from an actual dispute history API instead.

## PR
https://github.com/yortch/payment-disputes/pull/95
