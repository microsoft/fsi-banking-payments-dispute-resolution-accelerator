"""
Case store — env-selectable data layer for the dispute read API.

Selectable via ``CASE_STORE`` env var:
  • ``synthetic`` (default) — loads fixtures from src/data/synthetic/
  • ``cosmos``              — reads/writes Azure Cosmos DB (disputes container)

Synthetic mode sources (merged at startup):
  • src/data/synthetic/cases.json          — full array of Case objects
  • src/data/synthetic/cases/<uuid>.json   — individual per-case files
  Individual files take precedence over the array file on caseId collision.

Public interface (identical for both modes):
    list_cases(status_filter: str | None) -> list[dict]    # CaseSummary list
    get_case(case_id: str)               -> dict | None    # full Case
    update_case_status(case_id, status)  -> None           # status mutation

Cosmos document contract:
    Documents stored in the ``disputes`` container use the Case-contract
    field names verbatim, augmented with two PK helper fields:
        id           = caseId       (Cosmos document id)
        disputeId    = caseId       (duplicate for clarity)
        networkCode  = cardNetwork  (partition key component)
    Partition key path: ['/networkCode', '/disputeId'] (MultiHash v2)
    deadline.daysRemaining is NOT persisted — recomputed live on every read.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date
from functools import lru_cache

from services.runtime_case_store import list_cases as list_runtime_cases, get_case as get_runtime_case

RUNNING_IN_AZURE = bool(os.getenv("WEBSITE_INSTANCE_ID"))
ALLOW_DEMO_FALLBACK = os.getenv("ALLOW_DEMO_FALLBACK", "false" if RUNNING_IN_AZURE else "true").strip().lower() == "true"

# ── Path resolution ───────────────────────────────────────────────────────────
# __file__ = .../src/api/services/case_store.py
_SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))   # .../src/api/services
_API_DIR      = os.path.dirname(_SERVICES_DIR)                # .../src/api
_SRC_DIR      = os.path.dirname(_API_DIR)                     # .../src


def _resolve_synthetic_dir() -> str:
    """Locate synthetic case data in both local-repo and deployed-package layouts."""
    candidates = [
        os.path.join(_API_DIR, "data", "synthetic"),
        os.path.join(_SRC_DIR, "data", "synthetic"),
    ]
    for path in candidates:
        if os.path.isdir(path) or os.path.isfile(os.path.join(path, "cases.json")):
            return path
    return candidates[0]


_SYNTHETIC_DIR = _resolve_synthetic_dir()


# ── Deadline helpers ──────────────────────────────────────────────────────────

def _compute_days_remaining(due_date_str: str) -> int:
    """
    Return calendar days from today to due_date_str (ISO-8601 date string).
    Returns a negative value if the deadline has already passed.
    """
    try:
        return (date.fromisoformat(due_date_str) - date.today()).days
    except (ValueError, TypeError):
        return 0


def _refresh_deadline(case: dict) -> dict:
    """
    Return a shallow copy of case with deadline.daysRemaining recomputed
    live from deadline.dueDate so the demo countdown is always current.
    """
    dl = case.get("deadline")
    if dl and dl.get("dueDate"):
        case = {**case, "deadline": {**dl, "daysRemaining": _compute_days_remaining(dl["dueDate"])}}
    return case


# ── Loaders (swap these to change the backing store) ─────────────────────────

def _load_array_file() -> dict[str, dict]:
    """Load cases.json (full-array format) → {caseId: case}."""
    path = os.path.join(_SYNTHETIC_DIR, "cases.json")
    if not os.path.isfile(path):
        logging.warning("[case_store] cases.json not found at %s", path)
        return {}
    with open(path, encoding="utf-8") as fh:
        items: list[dict] = json.load(fh)
    loaded = {c["caseId"]: c for c in items if "caseId" in c}
    logging.info("[case_store] cases.json → %d cases", len(loaded))
    return loaded


def _load_individual_files() -> dict[str, dict]:
    """Load each <uuid>.json file in the cases/ subdirectory → {caseId: case}."""
    dir_path = os.path.join(_SYNTHETIC_DIR, "cases")
    if not os.path.isdir(dir_path):
        return {}
    result: dict[str, dict] = {}
    for fname in sorted(os.listdir(dir_path)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(dir_path, fname)
        try:
            with open(fpath, encoding="utf-8") as fh:
                case: dict = json.load(fh)
            if "caseId" in case:
                result[case["caseId"]] = case
        except (json.JSONDecodeError, OSError) as exc:
            logging.warning("[case_store] skipping %s — %s", fpath, exc)
    logging.info("[case_store] cases/ dir → %d cases", len(result))
    return result


@lru_cache(maxsize=1)
def _load_all() -> dict[str, dict]:
    """
    Merge both sources into a single {caseId: full-case-dict} store.
    Cached after first call (module lifetime / function host lifetime).
    Individual per-case files win over the array on caseId collision.
    """
    store = _load_array_file()
    store.update(_load_individual_files())
    logging.info("[case_store] store ready — %d total cases", len(store))
    return store


# ── CaseSummary projection ────────────────────────────────────────────────────

class MalformedCaseError(ValueError):
    """Raised when a case document is missing required fields."""


def _describe_case_document(case: dict) -> str:
    """Return best-effort identifying metadata for logging malformed docs."""
    parts = []
    for key in ("id", "caseId", "_ts"):
        value = case.get(key)
        if value not in (None, ""):
            parts.append(f"{key}={value}")
    return " ".join(parts) if parts else "id=<unknown>"


def _require_case_id(case: dict, expected_case_id: str | None = None) -> str:
    """Return caseId or raise a descriptive MalformedCaseError."""
    case_id = case.get("caseId")
    if not case_id:
        raise MalformedCaseError(
            f"missing required field 'caseId' ({_describe_case_document(case)})"
        )
    if expected_case_id and case_id != expected_case_id:
        raise MalformedCaseError(
            "caseId mismatch "
            f"(expected={expected_case_id} actual={case_id} {_describe_case_document(case)})"
        )
    return case_id


def _extract_case_description(case: dict) -> str:
    """Return customer-submitted narrative when present, else a generated intake summary."""
    metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
    candidate_fields = [
        case.get("caseDescription"),
        case.get("description"),
        case.get("cardholderStatement"),
        case.get("customerStatement"),
        case.get("disputeDescription"),
        metadata.get("description") if metadata else None,
        metadata.get("disputeDescription") if metadata else None,
    ]
    for value in candidate_fields:
        if isinstance(value, str) and value.strip():
            return value.strip()

    amount = case.get("transactionAmount")
    amount_text = f"${amount:,.2f}" if isinstance(amount, (int, float)) else "a transaction"
    merchant = case.get("merchantName") or "the merchant"
    reason = case.get("reasonCodeLabel") or case.get("reasonCode") or "a billing issue"
    return f"Customer submitted a dispute for {amount_text} with {merchant} related to {reason}."


def _with_case_description(case: dict) -> dict:
    description = _extract_case_description(case)
    if case.get("caseDescription") == description:
        return case
    return {**case, "caseDescription": description}

def _to_summary(case: dict) -> dict:
    """
    Project a full Case dict down to the CaseSummary shape
    (queue-list subset per the Story #21 contract).
    daysRemaining is computed live from dueDate.
    """
    case_id = _require_case_id(case)
    dl = case.get("deadline") or {}
    due_date: str = dl.get("dueDate", "")
    summary: dict = {
        "caseId":           case_id,
        "status":           case.get("status", ""),
        "cardNetwork":      case.get("cardNetwork"),
        "merchantName":     case.get("merchantName"),
        "caseDescription":  _extract_case_description(case),
        "transactionAmount": case.get("transactionAmount"),
        "reasonCode":       case.get("reasonCode", ""),
        "reasonCodeLabel":  case.get("reasonCodeLabel"),
        "winProbability":   case.get("winProbability"),
        "riskLevel":        case.get("riskLevel"),
        "deadline": {
            "dueDate":        due_date,
            "daysRemaining":  _compute_days_remaining(due_date),
        },
        "createdAt":  case.get("createdAt", ""),
        "updatedAt":  case.get("updatedAt"),
        "lastActivityAt": case.get("lastActivityAt"),
        "lastActivityType": case.get("lastActivityType"),
        "lastActivityActor": case.get("lastActivityActor"),
        "lastActivityDetail": case.get("lastActivityDetail"),
    }
    # Include analyst assignment fields when present
    if case.get("assignedAnalystId"):
        summary["assignedAnalystId"] = case["assignedAnalystId"]
    if case.get("assignedAnalystName"):
        summary["assignedAnalystName"] = case["assignedAnalystName"]
    return summary


# ── Public interface ──────────────────────────────────────────────────────────

def list_cases(status_filter: str | None = None) -> list[dict]:
    """
    Return a list of CaseSummary dicts, optionally filtered by status.

    Delegates to the Cosmos store when ``CASE_STORE=cosmos``; otherwise uses
    the synthetic fixture files (default behaviour).

    Args:
        status_filter: exact CaseStatus string to filter on (e.g. "pending_review").
                       Pass None to return all cases.

    Returns:
        List of CaseSummary dicts sorted by deadline.dueDate ascending.
    """
    case_store_mode = os.environ.get("CASE_STORE", "synthetic").lower()
    summaries: list[dict] = []
    should_merge_runtime = case_store_mode != "cosmos"
    cosmos_succeeded = False

    if case_store_mode == "cosmos":
        from services import cosmos_store  # lazy — no Cosmos import in synthetic mode

        try:
            summaries = cosmos_store.list_cases(status_filter)
            cosmos_succeeded = True
        except Exception as exc:  # noqa: BLE001
            if not ALLOW_DEMO_FALLBACK:
                raise
            should_merge_runtime = True
            logging.warning(
                "[case_store] cosmos list_cases failed — falling back to synthetic data "
                "(filter=%s exc=%s)",
                status_filter,
                exc,
            )

    if not summaries and not cosmos_succeeded:
        store = _load_all()
        for case in store.values():
            try:
                summaries.append(_to_summary(case))
            except MalformedCaseError as exc:
                logging.warning("[case_store] skipping malformed case in list_cases — %s", exc)

    if should_merge_runtime and ALLOW_DEMO_FALLBACK:
        runtime_summaries: list[dict] = []
        for case in list_runtime_cases():
            try:
                runtime_summaries.append(_to_summary(case))
            except MalformedCaseError as exc:
                logging.warning("[case_store] skipping malformed runtime case in list_cases — %s", exc)

        if runtime_summaries:
            by_case_id = {item["caseId"]: item for item in summaries if item.get("caseId")}
            for runtime_item in runtime_summaries:
                by_case_id[runtime_item["caseId"]] = runtime_item
            summaries = list(by_case_id.values())

    if status_filter:
        summaries = [s for s in summaries if s["status"] == status_filter]
    summaries.sort(key=lambda s: s["deadline"]["dueDate"])
    return summaries


def get_case(case_id: str) -> dict | None:
    """
    Return the full Case dict for the given caseId, or None if not found.
    deadline.daysRemaining is recomputed live from dueDate.

    Delegates to the Cosmos store when ``CASE_STORE=cosmos``.
    """
    if os.environ.get("CASE_STORE", "synthetic").lower() == "cosmos":
        from services import cosmos_store  # lazy — no Cosmos import in synthetic mode

        try:
            cosmos_case = cosmos_store.get_case(case_id)
            if cosmos_case is not None:
                return cosmos_case
        except Exception as exc:  # noqa: BLE001
            if not ALLOW_DEMO_FALLBACK:
                raise
            logging.warning(
                "[case_store] cosmos get_case failed — falling back to synthetic data "
                "(caseId=%s exc=%s)",
                case_id,
                exc,
            )

    raw = _load_all().get(case_id)
    if raw is None:
        runtime_case = get_runtime_case(case_id)
        if runtime_case is None:
            return None
        raw = runtime_case
    try:
        _require_case_id(raw, expected_case_id=case_id)
    except MalformedCaseError as exc:
        logging.warning("[case_store] skipping malformed case in get_case — %s", exc)
        return None
    return _refresh_deadline(_with_case_description(raw))


def update_case_status(case_id: str, status: str) -> None:
    """
    Update the status of a case in the backing store.

    In ``cosmos`` mode: writes the new status to Cosmos DB and stamps updatedAt.
    In ``synthetic`` mode: logs a warning and is a no-op (fixtures are read-only).
    """
    if os.environ.get("CASE_STORE", "synthetic").lower() == "cosmos":
        from services import cosmos_store  # lazy
        try:
            cosmos_store.update_case_status(case_id, status)
            return
        except KeyError:
            raise
        except Exception as exc:  # noqa: BLE001
            logging.warning(
                "[case_store] cosmos update_case_status failed — skipping write "
                "(caseId=%s status=%s exc=%s)",
                case_id,
                status,
                exc,
            )
            return
    else:
        logging.warning(
            "[case_store] update_case_status called in synthetic mode — no-op "
            "(caseId=%s status=%s)",
            case_id,
            status,
        )
