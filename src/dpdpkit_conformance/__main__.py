"""``dpdpkit-conformance`` — run the suite against DPDPKIT_BASE_URL or DPDPKIT_ASGI_APP."""

from __future__ import annotations

import sys
from collections.abc import Sequence

import pytest


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return int(pytest.main(["--pyargs", "dpdpkit_conformance.suite", "-p", "no:cacheprovider", *args]))


if __name__ == "__main__":
    sys.exit(main())
