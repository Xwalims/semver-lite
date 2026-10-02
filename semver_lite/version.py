"""Strict Semantic Versioning 2.0.0 parsing and precedence.

This module implements the grammar and precedence rules of
https://semver.org/spec/v2.0.0.html with no tolerance for anything the
spec's Backus-Naur Form does not allow.

Public API:
    Version: immutable, totally ordered version value.
    InvalidVersion: raised for any input the grammar rejects.
    parse: parse a version string, strictly by default.
    PartialVersion: parse a range-only partial version such as ``1.2`` or ``1.x``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering
from typing import Optional, Tuple, Union

__all__ = [
    "InvalidVersion",
    "PartialVersion",
    "Version",
    "compare",
    "parse",
]

# --- Spec grammar, transcribed to regular expressions -----------------------
# <numeric identifier> ::= "0" | <positive digit> <digits>
# Numeric identifiers MUST NOT contain leading zeroes, so "01" cannot match.
_NUMERIC = r"0|[1-9][0-9]*"
# <alphanumeric identifier> ::= one or more identifier characters, at least
# one of which is a non-digit (a letter or a hyphen).
_ALNUM = r"[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*"
# <identifier character> ::= <digit> | <non-digit>
_IDENTIFIER_CHARS = r"[0-9A-Za-z-]"

_NUMERIC_RE = re.compile(rf"^(?:{_NUMERIC})$")
_ALNUM_RE = re.compile(rf"^(?:{_ALNUM})$")
_IDENTIFIER_CHARS_RE = re.compile(rf"^(?:{_IDENTIFIER_CHARS})$")
# <pre-release identifier> ::= <alphanumeric identifier> | <numeric identifier>
_PRE_IDENTIFIER = rf"(?:{_ALNUM}|{_NUMERIC})"

# <valid semver> ::= <version core>
#                  | <version core> "-" <pre-release>
#                  | <version core> "+" <build>
#                  | <version core> "-" <pre-release> "+" <build>
_VERSION_RE = re.compile(
    rf"""
    ^
    (?P<major>{_NUMERIC})
    \.(?P<minor>{_NUMERIC})
    \.(?P<patch>{_NUMERIC})
    (?:
        -(?P<prerelease>
            {_PRE_IDENTIFIER} (?:\.{_PRE_IDENTIFIER})*
        )
    )?
    (?:
        \+(?P<build>
            {_IDENTIFIER_CHARS}+ (?:\.{_IDENTIFIER_CHARS}+)*
        )
    )?
    $
    """,
    re.VERBOSE,
)

# The spec's own example of ascending precedence, from section 11.
PRERELEASE_EXAMPLE_CHAIN = (
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-alpha.beta",
    "1.0.0-beta",
    "1.0.0-beta.2",
    "1.0.0-beta.11",
    "1.0.0-rc.1",
    "1.0.0",
)

# One entry per distinct failure mode, used to explain a rejection.
_RULE_CORE = (
    "a normal version must take the form X.Y.Z of non-negative integers "
    "without leading zeroes"
)
_RULE_PREFIX = "a 'v' or '=' prefix is not part of the grammar"
_RULE_PRERELEASE_CHARS = (
    "pre-release identifiers must comprise only ASCII alphanumerics and "
    "hyphens [0-9A-Za-z-]"
)
_RULE_PRERELEASE_EMPTY = "pre-release identifiers must not be empty"
_RULE_PRERELEASE_ZERO = "numeric pre-release identifiers must not include leading zeroes"
_RULE_BUILD_CHARS = (
    "build identifiers must comprise only ASCII alphanumerics and hyphens "
    "[0-9A-Za-z-]"
)
_RULE_BUILD_EMPTY = "build identifiers must not be empty"
_RULE_BUILD_COUNT = "at most one '+' build-metadata section is allowed"


class InvalidVersion(ValueError):
    """Raised when a string is not a valid Semantic Versioning 2.0.0 version.

    Subclasses :class:`ValueError`, so callers that already guard against
    ``ValueError`` keep working unchanged.
    """


def _fail(original: str, reason: str) -> InvalidVersion:
    """Build an :class:`InvalidVersion` naming the value and the spec rule it breaks."""
    return InvalidVersion(f"invalid semantic version {original!r}: {reason}")


@dataclass(frozen=True, order=False)
@total_ordering
class Version:
    """An immutable SemVer 2.0.0 version with spec-defined total precedence.

    Instances support ``==``, ``<``, ``<=``, ``>`` and ``>=`` against other
    :class:`Version` instances. Build metadata is stored verbatim but is
    deliberately ignored for precedence, as the spec requires.
    """

    major: int
    minor: int
    patch: int
    prerelease: Tuple[str, ...] = ()
    build: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Normalise the pre-release and build sequences to plain tuples of str."""
        object.__setattr__(self, "prerelease", tuple(self.prerelease))
        object.__setattr__(self, "build", tuple(self.build))

    def to_str(self) -> str:
        """Render this version in canonical ``MAJOR.MINOR.PATCH[-pre][+build]`` form."""
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text += "-" + ".".join(self.prerelease)
        if self.build:
            text += "+" + ".".join(self.build)
        return text

    def __str__(self) -> str:
        """Render this version via :meth:`to_str`."""
        return self.to_str()

    @property
    def _core(self) -> Tuple[int, int, int]:
        """Return the ``(major, minor, patch)`` core used for precedence."""
        return (self.major, self.minor, self.patch)

    @property
    def is_prerelease(self) -> bool:
        """Return ``True`` when this version carries a pre-release component."""
        return bool(self.prerelease)

    def compare(self, other: "Version") -> int:
        """Return -1, 0 or 1 for ``self < other``, equal, or ``self > other``.

        Precedence follows section 11 of the spec: major, minor and patch are
        compared numerically; a pre-release has lower precedence than the
        associated normal version; pre-release identifiers are then compared
        left to right, numeric identifiers numerically and alphanumeric ones
        in ASCII sort order, with numeric always ranking below alphanumeric
        and a larger set of identifiers ranking above a smaller set when all
        preceding identifiers are equal. Build metadata never affects
        precedence.
        """
        if not isinstance(other, Version):
            return NotImplemented
        if self._core != other._core:
            return -1 if self._core < other._core else 1
        return _compare_prerelease(self.prerelease, other.prerelease)

    def __eq__(self, other: object) -> bool:
        """Return ``True`` when both versions have equal precedence."""
        if not isinstance(other, Version):
            return NotImplemented
        return self.compare(other) == 0

    def __lt__(self, other: "Version") -> bool:
        """Return ``True`` when this version has lower precedence than ``other``."""
        if not isinstance(other, Version):
            return NotImplemented
        return self.compare(other) < 0

    def __hash__(self) -> int:
        """Hash on precedence only, so ``1.0.0+a`` and ``1.0.0+b`` collide by design."""
        return hash((self.major, self.minor, self.patch, self.prerelease))


def _is_numeric_identifier(identifier: str) -> bool:
    """Return ``True`` for an all-digit identifier that carries no leading zero."""
    return bool(_NUMERIC_RE.match(identifier))


def _is_digit_only(identifier: str) -> bool:
    """Return ``True`` when the identifier consists solely of ASCII digits."""
    return bool(identifier) and identifier.isdigit() and identifier.isascii()


def _compare_prerelease(left: Tuple[str, ...], right: Tuple[str, ...]) -> int:
    """Compare two pre-release tuples by spec precedence; an empty tuple means "normal version"."""
    if left and right:
        for a, b in zip(left, right):
            a_numeric, b_numeric = _is_numeric_identifier(a), _is_numeric_identifier(b)
            if a_numeric and b_numeric:
                if int(a) != int(b):
                    return -1 if int(a) < int(b) else 1
            elif a_numeric != b_numeric:
                # Numeric identifiers always have lower precedence.
                return -1 if a_numeric else 1
            else:
                if a != b:
                    return -1 if a < b else 1
        if len(left) != len(right):
            # A larger set of fields has higher precedence than a smaller set.
            return -1 if len(left) < len(right) else 1
        return 0
    if left:
        return -1
    if right:
        return 1
    return 0


def parse(version: str, strict: bool = True) -> Version:
    """Parse ``version`` into a :class:`Version`.

    Args:
        version: the string to parse.
        strict: when ``True`` (the default) only input allowed by the spec's
            grammar is accepted. When ``False``, a leading ``v``, ``V`` or
            ``=`` and surrounding whitespace are tolerated; everything else
            stays strict, so ``01.2.3`` still fails.

    Returns:
        The parsed :class:`Version`.

    Raises:
        InvalidVersion: if the string is not a valid semantic version.
    """
    if not isinstance(version, str):
        raise _fail(repr(version), "a version must be a string")
    if strict:
        text = version
    else:
        text = version.strip()
        if text[:1] in ("v", "V", "="):
            text = text[1:]
    if not text:
        raise _fail(version, "the empty string is not a version")
    match = _VERSION_RE.match(text)
    if match is None:
        raise _explain_rejection(version, text)
    prerelease = match.group("prerelease")
    build = match.group("build")
    return Version(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=tuple(prerelease.split(".")) if prerelease else (),
        build=tuple(build.split(".")) if build else (),
    )


def _explain_rejection(original: str, text: str) -> InvalidVersion:
    """Explain why ``text`` fails the grammar, naming the closest rule broken."""
    body = text.lstrip("vV=")
    if body[:1] in ("v", "V", "="):
        return _fail(original, _RULE_PREFIX)
    if body.count("+") > 1:
        return _fail(original, _RULE_BUILD_COUNT)

    core, separator, remainder = body.partition("-")
    if separator:
        prerelease, _, build = remainder.partition("+")
        if not prerelease or prerelease.startswith(".") or prerelease.endswith(".") or ".." in prerelease:
            return _fail(original, _RULE_PRERELEASE_EMPTY)
        for identifier in prerelease.split("."):
            if not identifier:
                return _fail(original, _RULE_PRERELEASE_EMPTY)
            if _is_digit_only(identifier) and len(identifier) > 1 and identifier.startswith("0"):
                return _fail(original, _RULE_PRERELEASE_ZERO)
            if not (_ALNUM_RE.match(identifier) or _NUMERIC_RE.match(identifier)):
                return _fail(original, _RULE_PRERELEASE_CHARS)
    else:
        _, _, build = "", "", ""

    if "+" in body:
        build = body.split("+", 1)[1]
        if not build or build.startswith(".") or build.endswith(".") or ".." in build:
            return _fail(original, _RULE_BUILD_EMPTY)
        for identifier in build.split("."):
            if not _IDENTIFIER_CHARS_RE.match(identifier):
                return _fail(original, _RULE_BUILD_CHARS)
    return _fail(original, _RULE_CORE)


_PARTIAL_RE = re.compile(
    rf"""
    ^
    (?P<major>{_NUMERIC})
    (?:\.(?P<minor>{_NUMERIC}))?
    (?:\.(?P<patch>{_NUMERIC}))?
    $
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class PartialVersion:
    """A version with trailing components omitted, as used by range endpoints."""

    major: Optional[int]
    minor: Optional[int] = None
    patch: Optional[int] = None

    @classmethod
    def parse(cls, text: str) -> "PartialVersion":
        """Parse ``1.2.3``, ``1.2``, ``1``, ``1.2.x``, ``1.x`` or the bare wildcard ``x``.

        Raises:
            InvalidVersion: if a component that is present is not a valid numeric identifier.
        """
        core = text.strip()
        if core[:1] in ("v", "V", "="):
            core = core[1:]
        lowered = core.lower()
        if lowered in ("x", "*"):
            return cls(None, None, None)
        if lowered.endswith(".x"):
            head = lowered[:-2]
            match = _PARTIAL_RE.match(head)
            if match is None:
                raise _fail(text, "range endpoints may omit trailing components or use 'x'")
            minor = match.group("minor")
            return cls(
                int(match.group("major")),
                None if minor is None else int(minor),
                None,
            )
        match = _PARTIAL_RE.match(core)
        if match is None:
            raise _fail(text, "range endpoints may omit trailing components or use 'x'")
        minor, patch = match.group("minor"), match.group("patch")
        return cls(
            int(match.group("major")),
            None if minor is None else int(minor),
            None if patch is None else int(patch),
        )

    def fill(self) -> "Version":
        """Return this partial version as a full :class:`Version`, defaulting to zero.

        Raises:
            InvalidVersion: if the version is unbounded (the bare wildcard).
        """
        if self.major is None:
            raise _fail("*", "the bare wildcard has no concrete value")
        return Version(self.major, self.minor or 0, self.patch or 0)

    def to_str(self) -> str:
        """Render the partial version, using ``x`` for each omitted component."""
        if self.major is None:
            return "*"
        text = str(self.major)
        if self.minor is not None:
            text += f".{self.minor}"
        if self.patch is not None:
            text += f".{self.patch}"
        return text


def parse_partial(text: str) -> PartialVersion:
    """Parse a range endpoint such as ``1.2.3``, ``1.2``, ``1``, ``1.x`` or ``*``.

    Args:
        text: the endpoint string.

    Returns:
        A :class:`PartialVersion` whose omitted components are ``None``.

    Raises:
        InvalidVersion: if the components that are present are not valid.
    """
    return PartialVersion.parse(text)


def compare(left: Union[str, Version], right: Union[str, Version]) -> int:
    """Compare two versions supplied as strings or :class:`Version` objects.

    Args:
        left: the first version.
        right: the second version.

    Returns:
        -1, 0 or 1 for ``left < right``, equal precedence, or ``left > right``.

    Raises:
        InvalidVersion: if either argument is not a valid version.
    """
    a = left if isinstance(left, Version) else parse(left)
    b = right if isinstance(right, Version) else parse(right)
    return a.compare(b)