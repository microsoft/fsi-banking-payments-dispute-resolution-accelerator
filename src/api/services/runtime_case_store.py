"""
In-memory runtime fallback store for disputes created while Cosmos is unavailable.

Purpose:
- Keep customer submissions visible in portal flows during transient storage outages.
- Provide read access for list/get/customer-filter endpoints when backend persistence fails.

Scope and limits:
- Process memory only (non-durable, instance-local).
- Intended for demo continuity and temporary fail-open behavior.
"""
from __future__ import annotations

from threading import RLock
from typing import Any

_lock = RLock()
_cases: dict[str, dict[str, Any]] = {}


def register_case(case: dict[str, Any]) -> None:
    """Insert or replace a runtime case by caseId/disputeId."""
    case_id = str(case.get("caseId") or case.get("disputeId") or case.get("id") or "").strip()
    if not case_id:
        return
    payload = dict(case)
    payload.setdefault("caseId", case_id)
    payload.setdefault("disputeId", case_id)
    payload.setdefault("id", case_id)
    with _lock:
        _cases[case_id] = payload


def get_case(case_id: str) -> dict[str, Any] | None:
    with _lock:
        case = _cases.get(case_id)
        return dict(case) if case else None


def list_cases() -> list[dict[str, Any]]:
    with _lock:
        return [dict(case) for case in _cases.values()]


def list_for_customer(
    *,
    customer_id: str | None = None,
    cardholder_name: str | None = None,
    card_last_four: str | None = None,
    include_closed: bool = True,
) -> list[dict[str, Any]]:
    """Filter runtime cases using the same inputs as the customer disputes endpoint."""
    customer_id = (customer_id or "").strip()
    cardholder_name = (cardholder_name or "").strip().lower()
    card_last_four = (card_last_four or "").strip()

    closed_statuses = {"approved", "denied", "submitted", "closed", "expired"}

    matched: list[dict[str, Any]] = []
    for case in list_cases():
        metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
        case_customer = str((metadata or {}).get("customerId") or "").strip()
        case_name = str(case.get("cardholderName") or "").strip().lower()
        case_last4 = str(case.get("cardLastFour") or "").strip()

        is_match = False
        if customer_id and case_customer == customer_id:
            is_match = True
        if cardholder_name and case_name and case_name == cardholder_name:
            is_match = True
        if card_last_four and case_last4 and case_last4 == card_last_four:
            is_match = True

        if not is_match:
            continue

        if not include_closed and str(case.get("status") or "").strip().lower() in closed_statuses:
            continue

        matched.append(case)

    matched.sort(key=lambda c: str(c.get("createdAt") or ""), reverse=True)
    return matched
