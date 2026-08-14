"""
Tests for services.gaps_service (Issue #18 — completeness & gaps detection).

Design choices tested:
- reasonCodeChecklist / evidenceGaps output matches the Case model contract
  ({"item","required","satisfied"} / {"missingItem","reason","impact"}) so the
  existing analyst-UI panels (EvidenceGapsPanel, ReasonCodeChecklist) can
  render the result directly.
- Missing REQUIRED items are surfaced with impact="critical"; missing
  recommended items are impact="medium".
- Configurable alert threshold: only fires when missing-required-count
  exceeds the threshold (default 2, overridable via param or env var).
- gathered ids can be supplied explicitly or derived from an evidence list.
- completionPct / readyForRebuttal mirror reason_code_engine.identify_evidence_gaps.
"""
from __future__ import annotations

import pytest

from services.gaps_service import detect_gaps, _get_alert_threshold

# Visa 10.1 — required: transaction_receipt, emv_chip_data, authorization_log (3 required, 0 recommended)
_VISA_10_1 = {"disputeId": "d-1", "networkCode": "visa", "reasonCode": "10.1"}
_ALL_REQUIRED_IDS = ["transaction_receipt", "emv_chip_data", "authorization_log"]

# Visa 10.4 — required: avs_cvv_results, ip_geolocation; recommended: device_fingerprint, 3ds_authentication
_VISA_10_4 = {"disputeId": "d-2", "networkCode": "visa", "reasonCode": "10.4"}


class TestChecklistShape:
    def test_checklist_matches_case_model_contract(self):
        result = detect_gaps(_VISA_10_1, gathered_evidence_ids=["transaction_receipt"])
        for entry in result["reasonCodeChecklist"]:
            assert set(entry.keys()) == {"item", "required", "satisfied"}
            assert isinstance(entry["required"], bool)
            assert isinstance(entry["satisfied"], bool)

    def test_satisfied_reflects_gathered_ids(self):
        result = detect_gaps(_VISA_10_1, gathered_evidence_ids=["transaction_receipt"])
        satisfied_items = {e["item"] for e in result["reasonCodeChecklist"] if e["satisfied"]}
        assert "Transaction Receipt" in satisfied_items

    def test_all_gathered_means_all_satisfied(self):
        result = detect_gaps(_VISA_10_1, gathered_evidence_ids=_ALL_REQUIRED_IDS)
        assert all(e["satisfied"] for e in result["reasonCodeChecklist"])
        assert result["evidenceGaps"] == []


class TestEvidenceGapsShape:
    def test_gaps_match_case_model_contract(self):
        result = detect_gaps(_VISA_10_1, gathered_evidence_ids=[])
        for gap in result["evidenceGaps"]:
            assert set(gap.keys()) == {"missingItem", "reason", "impact"}
            assert gap["impact"] in ("critical", "high", "medium", "low")

    def test_missing_required_item_is_critical_impact(self):
        result = detect_gaps(_VISA_10_1, gathered_evidence_ids=[])
        gaps_by_item = {g["missingItem"]: g for g in result["evidenceGaps"]}
        assert gaps_by_item["Transaction Receipt"]["impact"] == "critical"

    def test_missing_recommended_item_is_medium_impact(self):
        # device_fingerprint / 3ds_authentication are "recommended" on Visa 10.4
        result = detect_gaps(_VISA_10_4, gathered_evidence_ids=["avs_cvv_results", "ip_geolocation"])
        gaps_by_item = {g["missingItem"]: g for g in result["evidenceGaps"]}
        assert gaps_by_item["Device Fingerprint"]["impact"] == "medium"

    def test_reason_text_is_human_readable_and_non_empty(self):
        result = detect_gaps(_VISA_10_1, gathered_evidence_ids=[])
        for gap in result["evidenceGaps"]:
            assert isinstance(gap["reason"], str) and gap["reason"].strip()


class TestAlertThreshold:
    def test_no_alert_when_within_default_threshold(self):
        # 1 missing required item, default threshold is 2 -> not triggered
        result = detect_gaps(_VISA_10_1, gathered_evidence_ids=["transaction_receipt", "emv_chip_data"])
        assert result["missingRequiredCount"] == 1
        assert result["alertTriggered"] is False

    def test_alert_when_exceeding_default_threshold(self):
        # Visa 10.1 has 3 required items; gathering none => 3 missing > default threshold 2
        result = detect_gaps(_VISA_10_1, gathered_evidence_ids=[])
        assert result["missingRequiredCount"] == 3
        assert result["alertTriggered"] is True

    def test_explicit_threshold_override(self):
        result = detect_gaps(_VISA_10_1, gathered_evidence_ids=[], alert_threshold=5)
        assert result["missingRequiredCount"] == 3
        assert result["alertTriggered"] is False  # 3 <= 5

    def test_zero_threshold_flags_any_missing_required_item(self):
        result = detect_gaps(_VISA_10_1, gathered_evidence_ids=["transaction_receipt", "emv_chip_data"], alert_threshold=0)
        assert result["missingRequiredCount"] == 1
        assert result["alertTriggered"] is True

    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("EVIDENCE_GAP_ALERT_THRESHOLD", "0")
        assert _get_alert_threshold() == 0

    def test_invalid_env_var_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("EVIDENCE_GAP_ALERT_THRESHOLD", "not-a-number")
        assert _get_alert_threshold() == 2

    def test_unset_env_var_uses_default(self, monkeypatch):
        monkeypatch.delenv("EVIDENCE_GAP_ALERT_THRESHOLD", raising=False)
        assert _get_alert_threshold() == 2


class TestGatheredIdsFromEvidence:
    def test_derives_gathered_ids_from_evidence_list(self):
        evidence = [{"checklistItemId": cid} for cid in _ALL_REQUIRED_IDS]
        result = detect_gaps(_VISA_10_1, evidence=evidence)
        assert result["missingRequiredCount"] == 0
        assert result["readyForRebuttal"] is True

    def test_explicit_ids_take_precedence_over_evidence(self):
        evidence = [{"checklistItemId": cid} for cid in _ALL_REQUIRED_IDS]
        result = detect_gaps(_VISA_10_1, gathered_evidence_ids=[], evidence=evidence)
        # explicit empty list wins -> nothing gathered
        assert result["missingRequiredCount"] == 3

    def test_no_ids_and_no_evidence_means_nothing_gathered(self):
        result = detect_gaps(_VISA_10_1)
        assert result["missingRequiredCount"] == 3


class TestCompletionAndReadiness:
    def test_completion_pct_and_ready_flag_match_reason_code_engine(self):
        result = detect_gaps(_VISA_10_1, gathered_evidence_ids=_ALL_REQUIRED_IDS)
        assert result["completionPct"] == pytest.approx(100.0)
        assert result["readyForRebuttal"] is True

    def test_network_and_reason_code_reported(self):
        result = detect_gaps(_VISA_10_1, gathered_evidence_ids=[])
        assert result["network"] == "visa"
        assert result["reasonCode"] == "10.1"
