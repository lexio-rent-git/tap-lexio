"""Generate tap_lexio/schemas/*.json from spec/openapi.json (Lexio Rent API v1).

Usage: python scripts/gen_schemas.py
"""
from __future__ import annotations

import copy
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = json.loads((ROOT / "spec" / "openapi.json").read_text(encoding="utf-8"))
OUT = ROOT / "tap_lexio" / "schemas"

STREAMS = {
    "vehicles": "/vehicles",
    "categories": "/categories",
    "locations": "/locations",
    "options": "/options",
    "deductibles": "/deductibles",
    "deposits": "/deposits",
    "mileage_packages": "/mileage-packages",
    "customers": "/customers",
    "rentals": "/rentals",
    "vehicle_blocks": "/vehicle-blocks",
    "maintenance_records": "/maintenance-records",
    "events": "/events",
}
DROP = {"examples", "example", "$schema", "readOnly", "writeOnly", "discriminator", "xml", "externalDocs", "deprecated"}


def resolve(node, seen=()):
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if ref in seen:  # recursive schema: keep it open
                return {}
            target = SPEC
            for part in ref.lstrip("#/").split("/"):
                target = target[part]
            merged = {**copy.deepcopy(target), **{k: v for k, v in node.items() if k != "$ref"}}
            return resolve(merged, seen + (ref,))
        out = {}
        for key, value in node.items():
            if key in DROP:
                continue
            if key == "description" and isinstance(value, str):
                value = " ".join(value.split())[:300]
            out[key] = resolve(value, seen)
        return out
    if isinstance(node, list):
        return [resolve(v, seen) for v in node]
    return node


def item_schema(path: str) -> dict:
    op = SPEC["paths"][path]["get"]
    body = resolve(op["responses"]["200"]["content"]["application/json"]["schema"])
    return body["properties"]["data"]["items"]


OUT.mkdir(parents=True, exist_ok=True)
for name, path in STREAMS.items():
    schema = item_schema(path)
    schema.pop("required", None)  # be lenient: the API may omit fields on older records
    (OUT / f"{name}.json").write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{name:20s} {len(schema.get('properties', {}))} properties")
print("spec version", SPEC["info"]["version"])
