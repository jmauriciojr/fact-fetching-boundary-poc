"""In-memory stores for evaluations and grants (would be a DB / cache in production)."""

from __future__ import annotations

from typing import Optional

from boundary_agent.contracts.models import DecisionRequest, DecisionResponse, ExecutionGrant

_EVALUATIONS: dict[str, tuple[DecisionRequest, DecisionResponse]] = {}
_GRANTS: dict[str, ExecutionGrant] = {}


def save_evaluation(request: DecisionRequest, response: DecisionResponse) -> None:
    _EVALUATIONS[response.evaluation_id] = (request, response)


def get_evaluation(evaluation_id: str) -> Optional[tuple[DecisionRequest, DecisionResponse]]:
    return _EVALUATIONS.get(evaluation_id)


def save_grant(grant: ExecutionGrant) -> None:
    _GRANTS[grant.grant_id] = grant


def get_grant(grant_id: str) -> Optional[ExecutionGrant]:
    return _GRANTS.get(grant_id)


def clear() -> None:
    _EVALUATIONS.clear()
    _GRANTS.clear()
