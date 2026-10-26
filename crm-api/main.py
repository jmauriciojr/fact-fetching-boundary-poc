"""Mock CRM: the authoritative System of Record used by the Fact-Fetching Boundary.

Two endpoints, static in-memory data. Nothing here trusts the caller: facts come
only from this store, never from the request.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

app = FastAPI(title="Mock CRM", version="1.0.0", description="System of Record for the PoC")


class CustomerFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    tier: str
    margin_pct: float
    credit_hold: bool


class ResolvedRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_ref: str
    account_id: str


# --- Static System of Record ---------------------------------------------------

FACTS: dict[str, CustomerFacts] = {
    "ACC-001": CustomerFacts(account_id="ACC-001", tier="standard", margin_pct=20.0, credit_hold=False),
    "ACC-002": CustomerFacts(account_id="ACC-002", tier="premium", margin_pct=18.0, credit_hold=False),
}

# Email / name / id aliases -> account_id (simulates identity resolution).
REFS: dict[str, str] = {
    "ACC-001": "ACC-001",
    "alice@example.com": "ACC-001",
    "alice": "ACC-001",
    "ACC-002": "ACC-002",
    "bob@example.com": "ACC-002",
    "bob": "ACC-002",
}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "UP"}


@app.get("/resolve_ref/{customer_ref}", response_model=ResolvedRef)
def resolve_ref(customer_ref: str) -> ResolvedRef:
    account_id = REFS.get(customer_ref) or REFS.get(customer_ref.lower())
    if account_id is None:
        raise HTTPException(status_code=404, detail=f"Unknown customer_ref: {customer_ref}")
    return ResolvedRef(customer_ref=customer_ref, account_id=account_id)


@app.get("/facts/{account_id}", response_model=CustomerFacts)
def facts(account_id: str) -> CustomerFacts:
    record = FACTS.get(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown account_id: {account_id}")
    return record
