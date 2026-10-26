"""Contract test: the Pydantic DecisionRequest must match Kogito's DiscountApprovalInputSet."""

import httpx
import pytest

from boundary_agent import config
from boundary_agent.contracts.models import DecisionRequest

# Pydantic JSON-schema type -> acceptable OpenAPI types
TYPE_COMPAT = {"number": {"number", "integer"}, "integer": {"number", "integer"},
               "string": {"string"}, "boolean": {"boolean"}, "object": {"object"}}


@pytest.fixture(scope="module")
def openapi() -> dict:
    r = httpx.get(f"{config.DMN_BASE_URL}/q/openapi.json", timeout=10.0)
    r.raise_for_status()
    return r.json()


def _deref(schema: dict, root: dict) -> dict:
    while "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = root["components"]["schemas"][name]
    return schema


def _pyd_deref(schema: dict, root: dict) -> dict:
    while "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = root["$defs"][name]
    return schema


def _pyd_type(prop: dict) -> str:
    if "type" in prop:
        return prop["type"]
    # Optional[str] -> anyOf [{type: string}, {type: null}]
    types = [a["type"] for a in prop.get("anyOf", []) if a.get("type") != "null"]
    return types[0] if types else "object"


def _compare(pyd: dict, pyd_root: dict, oas: dict, oas_root: dict, path: str) -> None:
    pyd = _pyd_deref(pyd, pyd_root)
    oas = _deref(oas, oas_root)
    pyd_props = pyd.get("properties", {})
    oas_props = oas.get("properties", {})
    assert set(pyd_props) == set(oas_props), f"{path}: field mismatch {set(pyd_props) ^ set(oas_props)}"
    for name, pprop in pyd_props.items():
        oprop = _deref(oas_props[name], oas_root)
        ptype = _pyd_type(pprop)
        otype = oprop.get("type", "object")
        assert otype in TYPE_COMPAT[ptype], f"{path}.{name}: pydantic={ptype} openapi={otype}"
        if ptype == "object":
            _compare(pprop, pyd_root, oprop, oas_root, f"{path}.{name}")


def test_endpoint_references_input_set(openapi):
    body = openapi["paths"]["/DiscountApproval"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert body["$ref"] == "#/components/schemas/DiscountApprovalInputSet"


def test_decision_request_matches_discount_approval_input_set(openapi):
    input_set = openapi["components"]["schemas"]["DiscountApprovalInputSet"]
    assert set(input_set["required"]) == {"facts", "intent"}
    pyd = DecisionRequest.model_json_schema()
    assert set(pyd["required"]) == {"facts", "intent"}
    _compare(pyd, pyd, input_set, openapi, "DecisionRequest")


def test_explicit_type_assertions(openapi):
    schemas = openapi["components"]["schemas"]
    assert schemas["tIntent"]["properties"]["proposed_discount_pct"]["type"] == "number"
    assert schemas["tFacts"]["properties"]["margin_pct"]["type"] == "number"
    assert schemas["tFacts"]["properties"]["credit_hold"]["type"] == "boolean"
    assert schemas["tFacts"]["properties"]["tier"]["type"] == "string"
    assert schemas["tClaimedFacts"]["properties"]["tier"]["type"] == "string"
    assert "account_id" not in schemas["tFacts"]["properties"]  # Facts strips the CRM's account_id


def test_output_set_has_outcome_and_reason_code(openapi):
    result = openapi["components"]["schemas"]["tApprovalResult"]["properties"]
    outcome = _deref(result["Outcome"], openapi)
    assert set(outcome["enum"]) == {"APPROVED", "REJECTED", "REVIEW"}
    assert result["Reason Code"]["type"] == "string"
