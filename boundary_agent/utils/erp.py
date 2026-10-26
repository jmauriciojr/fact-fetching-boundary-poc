"""Mock ERP: records applied discounts in memory."""

from uuid import uuid4

APPLIED: list[dict] = []


def apply_discount(account_id: str, discount_pct: float, grant_id: str) -> str:
    ref = f"ERP-{uuid4().hex[:8].upper()}"
    APPLIED.append({"ref": ref, "account_id": account_id, "discount_pct": discount_pct, "grant_id": grant_id})
    return ref
