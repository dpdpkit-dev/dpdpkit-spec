"""``dpdpkit-conformance`` — run the suite against DPDPKIT_BASE_URL or DPDPKIT_ASGI_APP."""

from __future__ import annotations

import sys
from collections.abc import Sequence

import pytest


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["upgrade"]:
        from dpdpkit_conformance.upgrade import main as upgrade_main

        return upgrade_main(args[1:])
    return int(pytest.main(["--pyargs", "dpdpkit_conformance.suite", "-p", "no:cacheprovider", *args]))


if __name__ == "__main__":
    sys.exit(main())
