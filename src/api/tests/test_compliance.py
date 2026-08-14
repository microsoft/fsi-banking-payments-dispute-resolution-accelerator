"""
test_compliance.py

Verifies compliance / domain-logic rules:
  1. Deadline / SLA — near-expiry cases (≤7 days) are correctly identified.
  2. Evidence gap completeness — gaps with genuinely missing required items.
  3. Reason-code checklist alignment — unsatisfied *required* checklist items
     must be reflected as evidence gaps.
  4. Visa 13.1 specific — "proof of delivery" is required, unsatisfied, and
     a critical evidence gap covers it.
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta

import pytest

from services.case_store import _compute_days_remaining, list_cases

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_all_cases_raw() -> list[dict]:
    """Return all synthetic case dicts directly from disk (bypasses lru_cache)."""
    cases_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "src", "data", "synthetic", "cases",
    )
    # Normalise: tests/ is inside src/api/tests/
    api_tests_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(os.path.dirname(api_tests_dir))
    cases_dir = os.path.join(src_dir, "data", "synthetic", "cases")

    result = []
    for fname in os.listdir(cases_dir):
        if fname.endswith(".json"):
            with open(os.path.join(cases_dir, fname), encoding="utf-8") as fh:
                result.append(json.load(fh))
    return result


# ── 1. Deadline / SLA ─────────────────────────────────────────────────────────

NEAR_EXPIRY_THRESHOLD_DAYS = 7


class TestDeadlineSLA:
    def test_near_expiry_cases_detected(self):
        """
        Cases flagged as near-expiry by _compute_days_remaining() must exactly match
        the set produced by an independent pure date-arithmetic reference calculation.

        This cross-check is date-robust: both sides advance with the live clock, so
        the test never goes stale as dates in the fixture set pass the threshold.
        """
        cases = _load_all_cases_raw()

        # Production filter — uses case_store._compute_days_remaining()
        production_ids = {
            c["caseId"] for c in cases
            if _compute_days_remaining(c["deadline"]["dueDate"]) <= NEAR_EXPIRY_THRESHOLD_DAYS
        }

        # Independent reference — pure date arithmetic, no production helper involved
        reference_ids = {
            c["caseId"] for c in cases
            if (date.fromisoformat(c["deadline"]["dueDate"]) - date.today()).days
            <= NEAR_EXPIRY_THRESHOLD_DAYS
        }

        assert production_ids == reference_ids, (
            f"Near-expiry sets diverge.\n"
            f"  production : {sorted(i[:8] for i in production_ids)}\n"
            f"  reference  : {sorted(i[:8] for i in reference_ids)}"
        )

    def test_live_days_remaining_matches_computed(self):
        """The live-computed daysRemaining equals today's delta from dueDate."""
        cases = _load_all_cases_raw()
        for c in cases:
            due = c["deadline"]["dueDate"]
            computed = _compute_days_remaining(due)
            expected = (date.fromisoformat(due) - date.today()).days
            assert computed == expected

    def test_past_deadline_returns_negative(self):
        past_date = (date.today() - timedelta(days=1)).isoformat()
        assert _compute_days_remaining(past_date) < 0

    def test_sla_urgency_ordering(self):
        """list_cases() sorts by dueDate — first item should be most urgent."""
        summaries = list_cases()
        if len(summaries) >= 2:
            first_due = summaries[0]["deadline"]["dueDate"]
            second_due = summaries[1]["deadline"]["dueDate"]
            assert first_due <= second_due, "list_cases must sort by dueDate ascending"

    def test_most_urgent_case_has_smallest_days_remaining(self):
        summaries = list_cases()
        remaining_values = [s["deadline"]["daysRemaining"] for s in summaries]
        # First case should not have MORE days remaining than the last
        assert remaining_values[0] <= remaining_values[-1], (
            "First case in sorted list should have fewer or equal daysRemaining than last"
        )


# ── 2. Evidence gap completeness ──────────────────────────────────────────────

class TestEvidenceGaps:
    def test_critical_gaps_exist_in_dataset(self):
        """At least one case must have a critical-impact evidence gap."""
        cases = _load_all_cases_raw()
        critical_gap_cases = [
            c for c in cases
            if any(g.get("impact") == "critical" for g in c.get("evidenceGaps", []))
        ]
        assert len(critical_gap_cases) > 0, "No cases with critical evidence gaps found"

    def test_all_gaps_have_missing_item(self):
        """Every evidenceGap must have a non-empty missingItem."""
        cases = _load_all_cases_raw()
        for c in cases:
            for gap in c.get("evidenceGaps", []):
                assert gap.get("missingItem"), (
                    f"caseId {c['caseId'][:8]}: evidenceGap missing 'missingItem'"
                )

    def test_all_gaps_have_reason(self):
        """Every evidenceGap must have a non-empty reason."""
        cases = _load_all_cases_raw()
        for c in cases:
            for gap in c.get("evidenceGaps", []):
                assert gap.get("reason"), (
                    f"caseId {c['caseId'][:8]}: evidenceGap missing 'reason'"
                )

    def test_all_gaps_have_valid_impact(self):
        valid_impacts = {"critical", "high", "medium", "low"}
        cases = _load_all_cases_raw()
        for c in cases:
            for gap in c.get("evidenceGaps", []):
                assert gap["impact"] in valid_impacts, (
                    f"caseId {c['caseId'][:8]}: gap impact '{gap['impact']}' is invalid"
                )

    def test_cases_with_partial_or_missing_evidence_have_gaps(self):
        """
        Cases that have partial/missing evidence items should have evidenceGaps
        that explain what is incomplete.
        """
        cases = _load_all_cases_raw()
        for c in cases:
            incomplete = [
                ev for ev in c.get("evidence", [])
                if ev.get("completeness") in ("partial", "missing")
            ]
            if incomplete:
                assert len(c.get("evidenceGaps", [])) > 0, (
                    f"caseId {c['caseId'][:8]} has incomplete evidence but no evidenceGaps"
                )


# ── 3. Reason-code checklist alignment ───────────────────────────────────────

class TestChecklistAlignment:
    def test_unsatisfied_required_items_correspond_to_evidence_gaps(self):
        """
        For each unsatisfied required checklist item, at least one evidence gap
        must exist (i.e., the gap detection reflects genuinely missing items).

        This validates that the AI evidence assembly correctly propagates
        required-but-missing items from the checklist to evidenceGaps.
        """
        cases = _load_all_cases_raw()
        failures = []
        for c in cases:
            checklist = c.get("reasonCodeChecklist", [])
            gaps = c.get("evidenceGaps", [])
            unsatisfied_required = [
                item for item in checklist
                if item.get("required") and not item.get("satisfied")
            ]
            if unsatisfied_required and not gaps:
                failures.append(
                    f"caseId {c['caseId'][:8]} (reasonCode={c['reasonCode']}): "
                    f"{len(unsatisfied_required)} required checklist item(s) unsatisfied "
                    f"but evidenceGaps is empty"
                )
        assert not failures, "Checklist/gap mismatches:\n" + "\n".join(failures)

    def test_win_probability_lower_for_high_risk_cases(self):
        """
        Cases with riskLevel='critical' should not have winProbability > 0.5.
        A critical-risk case winning > 50% would be a data integrity concern.
        """
        cases = _load_all_cases_raw()
        violations = [
            c for c in cases
            if c.get("riskLevel") == "critical" and (c.get("winProbability") or 0) > 0.5
        ]
        assert not violations, (
            "Critical-risk cases with winProbability > 0.5: "
            + str([v["caseId"][:8] for v in violations])
        )


# ── 4. Visa 13.1 specific checklist check ────────────────────────────────────

VISA_131_CASE_ID = "bd3f6fe3-ad20-5e96-b926-da3b87c18834"


class TestVisa131Alignment:
    @pytest.fixture
    def visa_131_case(self):
        cases_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "..",
            "src", "data", "synthetic", "cases",
        )
        api_tests_dir = os.path.dirname(os.path.abspath(__file__))
        src_dir = os.path.dirname(os.path.dirname(api_tests_dir))
        fpath = os.path.join(
            src_dir, "data", "synthetic", "cases", f"{VISA_131_CASE_ID}.json"
        )
        with open(fpath, encoding="utf-8") as fh:
            return json.load(fh)

    def test_reason_code_is_visa_131(self, visa_131_case):
        assert visa_131_case["reasonCode"] == "13.1"
        assert visa_131_case["cardNetwork"] == "visa"

    def test_proof_of_delivery_is_required(self, visa_131_case):
        """Visa 13.1 'proof of delivery' checklist item must be marked required."""
        checklist = visa_131_case["reasonCodeChecklist"]
        pod_items = [
            item for item in checklist
            if "proof of delivery" in item["item"].lower() or "delivery" in item["item"].lower()
        ]
        assert pod_items, "Visa 13.1 checklist must include a 'proof of delivery' item"
        assert any(item["required"] for item in pod_items), (
            "Visa 13.1 'proof of delivery' checklist item must be marked required=true"
        )

    def test_proof_of_delivery_is_unsatisfied(self, visa_131_case):
        """Visa 13.1 'proof of delivery' must be unsatisfied in this test case."""
        checklist = visa_131_case["reasonCodeChecklist"]
        pod_items = [
            item for item in checklist
            if "delivery" in item["item"].lower() and item.get("required")
        ]
        unsatisfied = [item for item in pod_items if not item.get("satisfied")]
        assert unsatisfied, (
            "Visa 13.1: required 'proof of delivery' item should be unsatisfied in test case"
        )

    def test_critical_evidence_gap_exists_for_delivery(self, visa_131_case):
        """A critical evidence gap must exist for the missing delivery proof."""
        gaps = visa_131_case.get("evidenceGaps", [])
        critical_delivery_gaps = [
            g for g in gaps
            if g.get("impact") == "critical"
            and "delivery" in g.get("missingItem", "").lower()
        ]
        assert critical_delivery_gaps, (
            "Visa 13.1 case must have a critical evidence gap for missing delivery proof"
        )

    def test_checklist_unsatisfied_required_count_matches_gaps(self, visa_131_case):
        """
        Number of unsatisfied required checklist items should equal
        number of evidence gaps (1:1 correspondence for Visa 13.1 test case).
        """
        checklist = visa_131_case["reasonCodeChecklist"]
        unsatisfied_required = [
            item for item in checklist
            if item.get("required") and not item.get("satisfied")
        ]
        gaps = visa_131_case.get("evidenceGaps", [])
        assert len(unsatisfied_required) == len(gaps), (
            f"Visa 13.1: {len(unsatisfied_required)} unsatisfied required items "
            f"but {len(gaps)} evidence gaps — expected 1:1 correspondence"
        )
