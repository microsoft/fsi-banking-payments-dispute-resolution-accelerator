from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_ORCHESTRATOR_NAME = "dispute_orchestrator"
_ANALYST_EVENT_NAME = "analyst_decision"


def _base_url() -> str:
    explicit = os.environ.get("DURABLE_WEBHOOK_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")

    hostname = os.environ.get("WEBSITE_HOSTNAME", "").strip()
    if hostname:
        return f"https://{hostname}"

    return "http://localhost:7071"


def _query_string(extra: dict[str, str] | None = None) -> str:
    params = dict(extra or {})
    code = os.environ.get("DURABLE_WEBHOOK_CODE", "").strip()
    if code:
        params["code"] = code
    return f"?{urlencode(params)}" if params else ""


def _post(path: str, payload: dict[str, Any], *, query: dict[str, str] | None = None) -> int:
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        f"{_base_url()}{path}{_query_string(query)}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=10) as response:  # noqa: S310 - internal Functions endpoint
        return response.status


def start_dispute_orchestration(case_id: str) -> str:
    """Start the Durable dispute orchestrator for a caseId."""
    try:
        status = _post(
            f"/runtime/webhooks/durabletask/orchestrators/{_ORCHESTRATOR_NAME}",
            {"caseId": case_id},
            query={"instanceId": case_id},
        )
    except HTTPError as exc:
        if exc.code == 409:
            logger.info("[durable_client] orchestration already running — caseId=%s", case_id)
            return "already_running"
        raise RuntimeError(
            f"durable start failed with HTTP {exc.code} for caseId={case_id}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"durable start failed for caseId={case_id}: {exc}") from exc

    logger.info("[durable_client] orchestration started — caseId=%s status=%s", case_id, status)
    return "started"


def raise_analyst_decision(case_id: str, action: str, analyst_id: str, comment: str | None) -> bool:
    """Raise analyst_decision to the running Durable instance, if available."""
    try:
        _post(
            f"/runtime/webhooks/durabletask/instances/{case_id}/raiseEvent/{_ANALYST_EVENT_NAME}",
            {
                "action": action,
                "analystId": analyst_id,
                "comment": comment,
            },
        )
        logger.info(
            "[durable_client] analyst_decision raised — caseId=%s action=%s analystId=%s",
            case_id,
            action,
            analyst_id,
        )
        return True
    except HTTPError as exc:
        if exc.code in {404, 410}:
            logger.warning(
                "[durable_client] no active orchestration to signal — caseId=%s action=%s http=%s",
                case_id,
                action,
                exc.code,
            )
            return False
        raise RuntimeError(
            f"durable event raise failed with HTTP {exc.code} for caseId={case_id}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"durable event raise failed for caseId={case_id}: {exc}") from exc
