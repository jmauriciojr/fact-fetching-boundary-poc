"""Thin HTTP clients for the CRM (System of Record) and the Kogito DMN service."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from boundary_agent import config
from boundary_agent.contracts.models import DecisionRequest, Facts

_client: Optional[httpx.Client] = None


def http() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=10.0)
    return _client


# ---- CRM ----------------------------------------------------------------------


def resolve_ref(customer_ref: str) -> str:
    r = http().get(f"{config.CRM_BASE_URL}/resolve_ref/{customer_ref}")
    r.raise_for_status()
    return r.json()["account_id"]


def fetch_facts(account_id: str) -> Facts:
    r = http().get(f"{config.CRM_BASE_URL}/facts/{account_id}")
    r.raise_for_status()
    data = r.json()
    data.pop("account_id", None)  # tFacts has no account_id; StrictBaseModel would reject it
    return Facts(**data)


# ---- DMN ----------------------------------------------------------------------


def evaluate_raw(payload: dict[str, Any]) -> dict[str, Any]:
    """Baseline path: POST an arbitrary dict straight to Kogito. No validation, no facts."""
    r = http().post(f"{config.DMN_BASE_URL}{config.DMN_MODEL_PATH}", json=payload)
    r.raise_for_status()
    return r.json()


def evaluate(request: DecisionRequest) -> dict[str, Any]:
    return evaluate_raw(request.model_dump(mode="json"))
