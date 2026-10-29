"""Load closed operation contracts independently of full stored-record schemas.

D001: nested readOnly annotations do not reject malicious caller input. Narrow
contracts do. No persistence, HTTP, business decisions or fallback registry here.
"""
import json
import math
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

DIRECTORY = Path(__file__).resolve().parent / "schemas"


@lru_cache(maxsize=32)
def validator(name):
    """Return a registered request validator; unknown names raise KeyError."""
    catalog = json.loads((DIRECTORY / "contracts.json").read_text())["contracts"]
    schema = json.loads((DIRECTORY / catalog[name]).read_text())
    return Draft202012Validator(schema, format_checker=FormatChecker())


def problems(name, data):
    """Return value-free path/issue diagnostics; unknown fields are not ignored."""
    def nonfinite(value, path="body"):
        if isinstance(value, float) and not math.isfinite(value):
            return [{"field": path, "issue": "non_finite_number"}]
        if isinstance(value, dict):
            return [item for key, child in value.items() for item in nonfinite(child, f"{path}.{key}")]
        if isinstance(value, list):
            return [item for index, child in enumerate(value) for item in nonfinite(child, f"{path}[{index}]")]
        return []
    out = nonfinite(data)
    if out:
        return out
    for err in validator(name).iter_errors(data):
        path = ""
        for part in err.absolute_path:
            path += f"[{part}]" if isinstance(part, int) else ("." if path else "") + str(part)
        out.append({"field": path or "body", "issue": err.validator})
    return out


@lru_cache(maxsize=32)
def output_validator(name):
    catalog = json.loads((DIRECTORY / "outputs.json").read_text())["outputs"]
    return Draft202012Validator(json.loads((DIRECTORY / catalog[name]).read_text()), format_checker=FormatChecker())
