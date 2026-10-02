"""semver-lite: strict Semantic Versioning 2.0.0 with zero dependencies.

Quick start::

    from semver_lite import parse, satisfies, sort_versions

    parse("1.0.0-alpha") < parse("1.0.0")      # True
    satisfies("1.2.3", "^1.2.0")               # True
    sort_versions(["1.10.0", "1.9.0"])         # ['1.9.0', '1.10.0']

The canonical spec examples::

    1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta < 1.0.0-beta
              < 1.0.0-beta.2 < 1.0.0-beta.11 < 1.0.0-rc.1 < 1.0.0
"""

from __future__ import annotations

from .ranges import (
    Comparator,
    ComparatorSet,
    InvalidRange,
    Range,
    parse_range,
    satisfies,
    sort_versions,
)
from .version import (
    PRERELEASE_EXAMPLE_CHAIN,
    InvalidVersion,
    Version,
    compare,
    parse,
    parse_partial,
)

__version__ = "0.1.0"

__all__ = [
    "Comparator",
    "ComparatorSet",
    "InvalidRange",
    "InvalidVersion",
    "PRERELEASE_EXAMPLE_CHAIN",
    "Range",
    "Version",
    "__version__",
    "compare",
    "parse",
    "parse_partial",
    "parse_range",
    "satisfies",
    "sort_versions",
]