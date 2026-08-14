"""
Tests for services.scoring_service (Issue #30 — win-probability & risk scoring).

Design choices tested:
- winProbability is a deterministic blend of the reason code's historical
  win-rate and evidence completeness (quality-adjusted).
- Full evidence gathered -> higher score than partial/no evidence for the
  same reason code.
- riskLevel thresholds map winProbability to low/medium/high/critical.
- Data-integrity invariant: riskLevel == "critical" implies winProbability <= 0.5
  (mirrors tests/test_compliance.py::test_win_probability_lower_for_high_risk_cases).
- category routing: auto_approve / review / escalate, with critical evidence
  gaps forcing at least "review" or worse.
- Unknown reason codes fall back to a neutral base rate rather than crashing.
- gathered_evidence_ids can be derived automatically from an evidence list.
"""
from __future__ import annotations

import pytest

from services.scoring_service import score_case

# Visa 10.1 — win_rate 0.62; required: transaction_receipt, emv_chip_data, authorization_log
_VISA_10_1 = {"disputeId": "d-1", "networkCode": "visa", "reasonCode": "10.1"}
_ALL_REQUIRED_IDS = ["transaction_receipt", "emv_chip_data", "authorization_log"]


class TestWinProbabilityBlend:
    def test_full_evidence_scores_higher_than_no_evidence(self):
        full = score_case(_VISA_10_1, gathered_evidence_ids=_ALL_REQUIRED_IDS)
        none = score_case(_VISA_10_1, gathered_evidence_ids=[])
        assert full["winProbability"] > none["winProbability"]

    def test_partial_evidence_scores_between_none_and_full(self):
        partial = score_case(_VISA_10_1, gathered_evidence_ids=["transaction_receipt"])
        full = score_case(_VISA_10_1, gathered_evidence_ids=_ALL_REQUIRED_IDS)
        none = score_case(_VISA_10_1, gathered_evidence_ids=[])
        assert none["winProbability"] < partial["winProbability"] < full["winProbability"]

    def test_score_bounded_zero_to_one(self):
        for ids in ([], _ALL_REQUIRED_IDS, ["transaction_receipt"]):
            result = score_case(_VISA_10_1, gathered_evidence_ids=ids)
            assert 0.0 <= result["winProbability"] <= 1.0

    def test_base_win_rate_reported(self):
        result = score_case(_VISA_10_1, gathered_evidence_ids=_ALL_REQUIRED_IDS)
        assert result["baseWinRate"] == pytest.approx(0.62)

    def test_unknown_reason_code_falls_back_to_neutral_base(self):
        dispute = {"disputeId": "d-2", "networkCode": "visa", "reasonCode": "99.9"}
        result = score_case(dispute, gathered_evidence_ids=[])
        assert result["baseWinRate"] is None
        assert 0.0 <= result["winProbability"] <= 1.0  # does not raise


class TestReadyForRebuttalAndGaps:
    def test_ready_for_rebuttal_when_all_required_gathered(self):
        result = score_case(_VISA_10_1, gathered_evidence_ids=_ALL_REQUIRED_IDS)
        assert result["readyForRebuttal"] is True
        assert result["criticalGaps"] == 0

    def test_not_ready_when_required_missing(self):
        result = score_case(_VISA_10_1, gathered_evidence_ids=["transaction_receipt"])
        assert result["readyForRebuttal"] is False
        assert result["criticalGaps"] == 2  # emv_chip_data, authorization_log missing

    def test_completion_pct_reflects_gathered_fraction(self):
        result = score_case(_VISA_10_1, gathered_evidence_ids=_ALL_REQUIRED_IDS)
        assert result["completionPct"] == pytest.approx(100.0)


class TestRiskLevelThresholds:
    def test_full_evidence_yields_low_or_medium_risk(self):
        result = score_case(_VISA_10_1, gathered_evidence_ids=_ALL_REQUIRED_IDS)
        assert result["riskLevel"] in ("low", "medium")

    def test_no_evidence_yields_higher_risk_than_full(self):
        full = score_case(_VISA_10_1, gathered_evidence_ids=_ALL_REQUIRED_IDS)
        none = score_case(_VISA_10_1, gathered_evidence_ids=[])
        order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        assert order[none["riskLevel"]] >= order[full["riskLevel"]]

    def test_critical_risk_implies_win_probability_le_half(self):
        """Data-integrity invariant enforced across a sweep of synthetic scenarios."""
        scenarios = [
            {**_VISA_10_1, "reasonCode": "99.9"},  # unknown code, no evidence
            _VISA_10_1,
        ]
        for dispute in scenarios:
            for ids in ([], ["transaction_receipt"], _ALL_REQUIRED_IDS):
                result = score_case(dispute, gathered_evidence_ids=ids)
                if result["riskLevel"] == "critical":
                    assert result["winProbability"] <= 0.5


class TestCategoryRouting:
    def test_full_evidence_high_base_rate_can_auto_approve_or_review(self):
        result = score_case(_VISA_10_1, gathered_evidence_ids=_ALL_REQUIRED_IDS)
        assert result["category"] in ("auto_approve", "review")

    def test_no_evidence_with_critical_gaps_never_auto_approves(self):
        result = score_case(_VISA_10_1, gathered_evidence_ids=[])
        assert result["category"] != "auto_approve"

    def test_category_is_one_of_known_values(self):
        for ids in ([], _ALL_REQUIRED_IDS):
            result = score_case(_VISA_10_1, gathered_evidence_ids=ids)
            assert result["category"] in ("auto_approve", "review", "escalate")


class TestEvidenceQualityWeighting:
    def test_partial_completeness_evidence_scores_lower_than_complete(self):
        complete_evidence = [
            {"checklistItemId": cid, "completeness": "complete"} for cid in _ALL_REQUIRED_IDS
        ]
        partial_evidence = [
            {"checklistItemId": cid, "completeness": "partial"} for cid in _ALL_REQUIRED_IDS
        ]
        complete_result = score_case(_VISA_10_1, evidence=complete_evidence)
        partial_result = score_case(_VISA_10_1, evidence=partial_evidence)
        assert complete_result["winProbability"] > partial_result["winProbability"]

    def test_evidence_list_derives_gathered_ids_when_not_explicit(self):
        evidence = [{"checklistItemId": cid, "completeness": "complete"} for cid in _ALL_REQUIRED_IDS]
        result = score_case(_VISA_10_1, evidence=evidence)
        assert result["readyForRebuttal"] is True


class TestNetworkAndReasonCodeExtraction:
    def test_reports_normalized_network_and_code(self):
        result = score_case(_VISA_10_1, gathered_evidence_ids=[])
        assert result["network"] == "visa"
        assert result["reasonCode"] == "10.1"

    def test_prefixed_reason_code_string_parsed(self):
        dispute = {"disputeId": "d-3", "reasonCode": "Visa 10.1"}
        result = score_case(dispute, gathered_evidence_ids=[])
        assert result["network"] == "visa"
        assert result["reasonCode"] == "10.1"
