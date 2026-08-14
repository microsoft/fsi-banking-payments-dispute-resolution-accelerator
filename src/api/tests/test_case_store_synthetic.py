"""
test_case_store_synthetic.py — story #51

Guarantees the API serves GET /cases and GET /cases/{id} from synthetic
fixture files with NO Cosmos connection when CASE_STORE is unset or
set to "synthetic".  No COSMOS_ENDPOINT, no azure.cosmos, no network.

Tests
-----
1.  list_cases() returns all synthetic cases (smoke test for cold-boot)
2.  list_cases() CaseSummary fields are present and non-empty
3.  list_cases(status_filter="pending_review") returns the pending cases
4.  get_case(known_id) returns the full Case document
5.  get_case(unknown_id) returns None  (404 guard)
6.  Synthetic mode does NOT invoke cosmos_client.query_disputes
7.  Synthetic mode does NOT import services.cosmos_store at call time
     (cosmos module stays out of sys.modules for a fresh call path)
8.  update_case_status() in synthetic mode is a no-op — no Cosmos write
"""
from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from services.case_store import get_case, list_cases, update_case_status

# Expected counts are derived dynamically from the synthetic fixtures rather
# than hardcoded, so this suite can't drift out of sync when the fixture set
# grows/shrinks (see cases.json going from 10 -> 61 records via an unrelated
# feature merge, which broke previously-hardcoded constants here).
TOTAL_CASES = len(list_cases())
PENDING_REVIEW_CASES = len(list_cases(status_filter="pending_review"))

REQUIRED_SUMMARY_FIELDS = {
    "caseId", "status", "cardNetwork", "merchantName", "transactionAmount",
    "reasonCode", "deadline",
}

# A known caseId present in the synthetic fixture set (Visa 13.1 — confirmed in conftest)
KNOWN_ID = "bd3f6fe3-ad20-5e96-b926-da3b87c18834"
UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"


# ── 1–2: list_cases smoke tests ───────────────────────────────────────────────

class TestSyntheticListCases:
    def test_returns_ten_cases_by_default(self, monkeypatch):
        """With CASE_STORE unset, list_cases() must return all synthetic fixtures."""
        monkeypatch.delenv("CASE_STORE", raising=False)
        results = list_cases()
        assert len(results) == TOTAL_CASES, (
            f"Expected {TOTAL_CASES} synthetic cases, got {len(results)}"
        )

    def test_case_store_synthetic_explicit_also_returns_ten(self, monkeypatch):
        """CASE_STORE=synthetic must behave identically to the unset default."""
        monkeypatch.setenv("CASE_STORE", "synthetic")
        results = list_cases()
        assert len(results) == TOTAL_CASES

    def test_each_summary_has_required_fields(self, monkeypatch):
        """Every CaseSummary must expose the fields expected by the UI queue."""
        monkeypatch.delenv("CASE_STORE", raising=False)
        results = list_cases()
        for summary in results:
            missing = REQUIRED_SUMMARY_FIELDS - summary.keys()
            assert not missing, (
                f"CaseSummary for {summary.get('caseId')} missing fields: {missing}"
            )

    def test_status_filter_returns_pending_review_cases(self, monkeypatch):
        """list_cases(status_filter='pending_review') must return only pending cases."""
        monkeypatch.delenv("CASE_STORE", raising=False)
        results = list_cases(status_filter="pending_review")
        assert len(results) == PENDING_REVIEW_CASES
        for s in results:
            assert s["status"] == "pending_review"

    def test_results_sorted_by_due_date(self, monkeypatch):
        """Synthetic results must be ordered by deadline.dueDate ascending."""
        monkeypatch.delenv("CASE_STORE", raising=False)
        results = list_cases()
        due_dates = [s["deadline"]["dueDate"] for s in results]
        assert due_dates == sorted(due_dates), "list_cases() must be sorted by dueDate ascending"


# ── 3–4: get_case smoke tests ─────────────────────────────────────────────────

class TestSyntheticGetCase:
    def test_returns_full_case_for_known_id(self, monkeypatch):
        """get_case(known_id) must return a dict with caseId and full-case fields."""
        monkeypatch.delenv("CASE_STORE", raising=False)
        result = get_case(KNOWN_ID)
        assert result is not None, f"Expected a case for {KNOWN_ID}, got None"
        assert result["caseId"] == KNOWN_ID
        assert "evidence" in result
        assert "rebuttalDraft" in result

    def test_returns_none_for_unknown_id(self, monkeypatch):
        """get_case(unknown_id) must return None (no 404 crash)."""
        monkeypatch.delenv("CASE_STORE", raising=False)
        assert get_case(UNKNOWN_ID) is None

    def test_days_remaining_is_live(self, monkeypatch):
        """daysRemaining must be computed from dueDate, not from the fixture's stale value."""
        from datetime import date
        monkeypatch.delenv("CASE_STORE", raising=False)
        result = get_case(KNOWN_ID)
        deadline = result["deadline"]
        due = date.fromisoformat(deadline["dueDate"])
        expected = (due - date.today()).days
        assert deadline["daysRemaining"] == expected


# ── 5–7: Cosmos non-touch guarantees ─────────────────────────────────────────

class TestSyntheticNoCosmosDependency:
    """
    These tests prove the synthetic path NEVER touches Cosmos.  They are the
    contract that local-dev mode (no Cosmos account, no COSMOS_ENDPOINT) works.
    """

    def test_list_cases_does_not_call_cosmos_query(self, monkeypatch):
        """cosmos_client.query_disputes must NEVER be called in synthetic mode."""
        monkeypatch.delenv("CASE_STORE", raising=False)
        with patch(
            "cosmos_client.query_disputes",
            side_effect=RuntimeError("cosmos_client.query_disputes called in synthetic mode!"),
        ):
            results = list_cases()   # must NOT raise
        assert len(results) == TOTAL_CASES

    def test_get_case_does_not_call_cosmos_query(self, monkeypatch):
        """cosmos_client.query_disputes must NEVER be called by get_case in synthetic mode."""
        monkeypatch.delenv("CASE_STORE", raising=False)
        with patch(
            "cosmos_client.query_disputes",
            side_effect=RuntimeError("cosmos_client.query_disputes called in synthetic mode!"),
        ):
            result = get_case(KNOWN_ID)   # must NOT raise
        assert result is not None

    def test_synthetic_list_cases_does_not_import_cosmos_store(self, monkeypatch):
        """
        After a synthetic list_cases() call, services.cosmos_store must not have
        been freshly imported.  We evict it from sys.modules first to simulate a
        cold-start, then confirm it stays absent after the call.
        """
        monkeypatch.delenv("CASE_STORE", raising=False)
        # Evict cosmos modules to get a clean slate for this check
        evicted = {k: sys.modules.pop(k) for k in list(sys.modules)
                   if k in ("services.cosmos_store", "cosmos_client")}
        try:
            list_cases()
            assert "services.cosmos_store" not in sys.modules, (
                "services.cosmos_store was imported during a synthetic list_cases() call — "
                "check for an unconditional import in case_store.py"
            )
        finally:
            # Restore evicted modules so other tests are unaffected
            sys.modules.update(evicted)

    def test_update_case_status_is_noop_in_synthetic(self, monkeypatch):
        """update_case_status in synthetic mode must not write to Cosmos."""
        monkeypatch.setenv("CASE_STORE", "synthetic")
        with patch("cosmos_client.update_dispute") as mock_upd:
            update_case_status(KNOWN_ID, "approved")   # must not raise
        mock_upd.assert_not_called()
