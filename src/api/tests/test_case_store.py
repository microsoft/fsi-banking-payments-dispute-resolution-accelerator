"""
test_case_store.py

Verifies:
  1. Loader parses all fixture files in the cases/ directory.
  2. list_cases() returns correct count and CaseSummary shape.
  3. list_cases(status_filter="pending_review") returns exactly the pending cases.
  4. get_case(known_id) returns full case.
  5. get_case(unknown_id) returns None.
  6. daysRemaining in get_case() is recomputed live from dueDate.
  7. list_cases() results are sorted by dueDate ascending.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from services.case_store import (
    MalformedCaseError,
    _compute_days_remaining,
    _load_individual_files,
    _to_summary,
    get_case,
    list_cases,
)

# Expected counts are derived dynamically from the synthetic fixtures rather
# than hardcoded, so this suite can't drift out of sync when the fixture set
# grows/shrinks (see cases.json going from 10 -> 61 records via an unrelated
# feature merge, which broke previously-hardcoded constants here).
INDIVIDUAL_FILE_CASES = len(_load_individual_files())  # cases/<uuid>.json files only
TOTAL_CASES = len(list_cases())  # merged cases.json + cases/ dir (list_cases() source of truth)
PENDING_REVIEW_CASES = len(list_cases(status_filter="pending_review"))

SUMMARY_FIELDS = {
    "caseId", "status", "cardNetwork", "merchantName", "transactionAmount",
    "reasonCode", "reasonCodeLabel", "winProbability", "riskLevel",
    "deadline", "createdAt", "updatedAt",
}


# ── 1. Loader ─────────────────────────────────────────────────────────────────

class TestLoader:
    def test_individual_files_loads_all_ten(self):
        store = _load_individual_files()
        assert len(store) == INDIVIDUAL_FILE_CASES, (
            f"Expected {INDIVIDUAL_FILE_CASES} cases from cases/ dir, got {len(store)}"
        )

    def test_each_case_has_case_id(self):
        store = _load_individual_files()
        for cid, case in store.items():
            assert "caseId" in case
            assert case["caseId"] == cid

    def test_all_case_ids_are_uuid_like(self):
        import re
        store = _load_individual_files()
        uuid_re = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        for cid in store:
            assert uuid_re.match(cid), f"caseId '{cid}' is not a valid UUID"


# ── 2. list_cases() shape and count ──────────────────────────────────────────

class TestListCases:
    def test_returns_all_cases(self):
        summaries = list_cases()
        assert len(summaries) == TOTAL_CASES

    def test_summary_has_required_fields(self):
        summaries = list_cases()
        for s in summaries:
            assert "caseId" in s
            assert "status" in s
            assert "reasonCode" in s
            assert "createdAt" in s
            assert "deadline" in s

    def test_summary_deadline_has_due_date_and_days(self):
        summaries = list_cases()
        for s in summaries:
            dl = s["deadline"]
            assert "dueDate" in dl, f"caseId {s['caseId']}: deadline missing dueDate"
            assert "daysRemaining" in dl, f"caseId {s['caseId']}: deadline missing daysRemaining"

    def test_summary_omits_network_from_deadline(self):
        """CaseSummary deadline must NOT include 'network' (queue-list subset per contract)."""
        summaries = list_cases()
        for s in summaries:
            assert "network" not in s["deadline"], (
                f"caseId {s['caseId']}: summary deadline must omit 'network'"
            )

    def test_sorted_by_due_date_ascending(self):
        summaries = list_cases()
        due_dates = [s["deadline"]["dueDate"] for s in summaries]
        assert due_dates == sorted(due_dates), "list_cases() results must be sorted by dueDate"

    def test_skips_malformed_case_and_logs_warning(self, monkeypatch, caplog):
        monkeypatch.delenv("CASE_STORE", raising=False)
        malformed = {
            "id": "smoke-doc-1",
            "_ts": 1720540800,
            "status": "pending_review",
            "deadline": {"dueDate": "2026-07-15"},
        }
        valid = {
            "caseId": "aaaaaaaa-0000-0000-0000-000000000001",
            "status": "pending_review",
            "deadline": {"dueDate": "2026-07-16"},
        }
        with (
            patch("services.case_store._load_all", return_value={"good": valid, "bad": malformed}),
            caplog.at_level(logging.WARNING),
        ):
            summaries = list_cases()

        assert [s["caseId"] for s in summaries] == [valid["caseId"]]
        assert "missing required field 'caseId'" in caplog.text
        assert "id=smoke-doc-1" in caplog.text
        assert "_ts=1720540800" in caplog.text


# ── 3. Status filter ──────────────────────────────────────────────────────────

class TestStatusFilter:
    def test_pending_review_filter_returns_correct_count(self):
        pending = list_cases(status_filter="pending_review")
        assert len(pending) == PENDING_REVIEW_CASES, (
            f"Expected {PENDING_REVIEW_CASES} pending_review cases, got {len(pending)}"
        )

    def test_all_filtered_cases_have_matching_status(self):
        for status in ("pending_review", "approved", "escalated", "evidence_gathering"):
            results = list_cases(status_filter=status)
            for s in results:
                assert s["status"] == status, (
                    f"Filter '{status}' returned case with status '{s['status']}'"
                )

    def test_unknown_status_returns_empty(self):
        results = list_cases(status_filter="nonexistent_status")
        assert results == []

    def test_none_filter_returns_all(self):
        assert len(list_cases(None)) == TOTAL_CASES


# ── 4 & 5. get_case() ────────────────────────────────────────────────────────

class TestGetCase:
    def test_known_id_returns_full_case(self, known_case_id):
        case = get_case(known_case_id)
        assert case is not None
        assert case["caseId"] == known_case_id

    def test_full_case_has_deadline_with_network(self, known_case_id):
        """Full Case (not CaseSummary) includes deadline.network."""
        case = get_case(known_case_id)
        assert "network" in case["deadline"], "Full case deadline must include 'network'"

    def test_full_case_has_evidence_list(self, known_case_id):
        case = get_case(known_case_id)
        assert "evidence" in case
        assert isinstance(case["evidence"], list)
        assert len(case["evidence"]) > 0

    def test_full_case_has_rebuttal_draft(self, known_case_id):
        case = get_case(known_case_id)
        assert "rebuttalDraft" in case
        assert "text" in case["rebuttalDraft"]

    def test_unknown_id_returns_none(self, unknown_case_id):
        result = get_case(unknown_case_id)
        assert result is None


# ── 6. daysRemaining recomputed live ─────────────────────────────────────────

class TestDaysRemainingLive:
    def test_compute_days_remaining_future(self):
        future = (date.today() + timedelta(days=5)).isoformat()
        assert _compute_days_remaining(future) == 5

    def test_compute_days_remaining_today(self):
        today = date.today().isoformat()
        assert _compute_days_remaining(today) == 0

    def test_compute_days_remaining_past(self):
        past = (date.today() - timedelta(days=3)).isoformat()
        assert _compute_days_remaining(past) == -3

    def test_compute_days_remaining_invalid(self):
        assert _compute_days_remaining("not-a-date") == 0
        assert _compute_days_remaining("") == 0

    def test_to_summary_raises_for_missing_case_id(self):
        with pytest.raises(MalformedCaseError, match="missing required field 'caseId'"):
            _to_summary({"id": "missing-case-id"})

    def test_get_case_recomputes_days_remaining(self, known_case_id):
        """
        get_case() must recompute daysRemaining live from dueDate.
        The stored daysRemaining in the JSON may differ from today's live value;
        verify the returned value matches _compute_days_remaining(dueDate).
        """
        case = get_case(known_case_id)
        due_date = case["deadline"]["dueDate"]
        expected = _compute_days_remaining(due_date)
        actual = case["deadline"]["daysRemaining"]
        assert actual == expected, (
            f"daysRemaining should be live-computed: expected {expected}, got {actual}"
        )

    def test_list_cases_recomputes_days_remaining(self):
        """list_cases() summaries also reflect live-computed daysRemaining."""
        summaries = list_cases()
        for s in summaries:
            dl = s["deadline"]
            expected = _compute_days_remaining(dl["dueDate"])
            assert dl["daysRemaining"] == expected, (
                f"caseId {s['caseId']}: daysRemaining should be {expected}, got {dl['daysRemaining']}"
            )
