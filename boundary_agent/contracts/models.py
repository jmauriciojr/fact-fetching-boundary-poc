"""Pydantic contracts for the Fact-Fetching Boundary.

Every model forbids unknown fields (``extra="forbid"``): an LLM cannot smuggle an
extra ``facts`` key into an intent, and a malformed DMN reply fails loudly.
All timestamps are timezone-aware UTC (``datetime.now(timezone.utc)``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False, frozen=False)


# --------------------------------------------------------------------------- errors


class BoundaryError(Exception):
    """Base class for Boundary rejections."""


class AuthorizationError(BoundaryError):
    """Actor is not allowed to act on behalf of the trigger's account."""


class TriggerBindingError(BoundaryError):
    """The agent's customer_ref does not resolve to the account that triggered the run."""


class GrantError(BoundaryError):
    """ExecutionGrant is missing, expired, tampered with, or not approved."""


# --------------------------------------------------------------------------- agent side


class ClaimedFacts(StrictBaseModel):
    """Unverified assertions extracted from the conversation. Never used as facts."""

    tier: Optional[str] = None


class AgentIntent(StrictBaseModel):
    """Probabilistic output of the LLM agent: what it *wants* to do and what it *believes*."""

    customer_ref: str
    proposed_discount_pct: float = Field(ge=0, le=100)
    claimed_facts: ClaimedFacts = Field(default_factory=ClaimedFacts)
    rationale: Optional[str] = None


class TriggerContext(StrictBaseModel):
    """Authoritative context of the event that started the agent run (not agent-controlled)."""

    trigger_id: str = Field(default_factory=lambda: new_id("trg"))
    account_id: str
    actor_id: str
    channel: str = "chat"
    occurred_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- DMN contract


class Facts(StrictBaseModel):
    """Mirror of DMN item definition ``tFacts`` (authoritative, fetched from the CRM)."""

    tier: str
    margin_pct: float
    credit_hold: bool


class IntentInput(StrictBaseModel):
    """Mirror of DMN item definition ``tIntent``."""

    proposed_discount_pct: float
    claimed_facts: ClaimedFacts


class DecisionRequest(StrictBaseModel):
    """Mirror of the Kogito ``DiscountApprovalInputSet`` schema. Exactly two top-level keys."""

    facts: Facts
    intent: IntentInput


class Outcome(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVIEW = "REVIEW"


class DecisionResponse(StrictBaseModel):
    evaluation_id: str = Field(default_factory=lambda: new_id("eval"))
    outcome: Outcome
    reason_code: str
    entitled_max_discount: float
    claim_escalation: bool
    request_hash: str
    decided_at: datetime = Field(default_factory=utcnow)
    raw: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- execution


class ExecutionGrant(StrictBaseModel):
    """Short-lived, single-use token binding an APPROVED evaluation to a concrete action."""

    grant_id: str = Field(default_factory=lambda: new_id("grant"))
    evaluation_id: str
    account_id: str
    action: str = "apply_discount"
    discount_pct: float
    request_hash: str
    issued_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    consumed: bool = False


class ExecutionResult(StrictBaseModel):
    grant_id: str
    evaluation_id: str
    account_id: str
    discount_pct: float
    erp_reference: str
    applied_at: datetime = Field(default_factory=utcnow)
