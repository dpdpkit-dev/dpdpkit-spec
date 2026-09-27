"""dpdpkit REST contract and conformance suite.

Run against a live server::

    DPDPKIT_BASE_URL=http://localhost:8000/dpdp dpdpkit-conformance

or in-process against an ASGI app::

    DPDPKIT_ASGI_APP=examples.fastapi_shop.app:app dpdpkit-conformance
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

__version__ = "0.1.0a1"

PRINCIPAL_HEADER = "X-DPDP-Test-Principal"
ROLE_HEADER = "X-DPDP-Test-Role"


@lru_cache(maxsize=1)
def openapi() -> dict[str, Any]:
    """The OpenAPI document shipped with this package (or the repo copy in editable installs)."""
    packaged = resources.files(__name__) / "openapi.yaml"
    if packaged.is_file():
        text = packaged.read_text(encoding="utf-8")
    else:
        text = (Path(__file__).resolve().parents[2] / "openapi.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)  # type: ignore[no-any-return]


def schema_errors(instance: Any, schema_name: str) -> list[str]:
    """Validate ``instance`` against ``#/components/schemas/<schema_name>``; return error messages."""
    doc = openapi()
    validator = Draft202012Validator(
        {**doc, "$ref": f"#/components/schemas/{schema_name}"}, format_checker=FormatChecker()
    )
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in validator.iter_errors(instance)
    ]


def assert_schema(instance: Any, schema_name: str) -> None:
    errors = schema_errors(instance, schema_name)
    assert not errors, f"response does not match {schema_name}: {errors}"
