"""Range parsing and evaluation for semver-lite.

The SemVer 2.0.0 specification defines version syntax and precedence but not
range syntax, so this module follows the de-facto node-semver / Cargo
conventions. Supported forms:

* Comparators: ``=``, ``==``, ``!=``, ``>``, ``>=``, ``<``, ``<=``
* Caret:  ``^1.2.3`` allows changes that do not modify the left-most non-zero
  component
* Tilde:  ``~1.2.3`` allows patch-level changes when a minor is given
* Wildcards: ``1.2.x``, ``1.x``, ``x``, ``*``
* Partial versions: ``1.2`` means ``>=1.2.0 <1.3.0-0``
* Hyphen ranges: ``1.2.3 - 2.0.0``
* Conjunction: space-separated comparators, e.g. ``>=1.2.3 <2.0.0``
* Disjunction: ``||``-separated groups, e.g. ``^1.0.0 || ^2.0.0``

Ranges are normalised to a disjunction of comparator sets, exactly as
node-semver does, so an exclusive upper bound is written ``<NEXT-0``. The
``-0`` suffix is the lowest possible pre-release, which keeps pre-releases out
of ranges whose endpoints name a release version.

Pre-release rule (npm and Cargo behaviour): a version carrying a pre-release
satisfies a range only when some comparator in the matching comparator set has
the same ``[major, minor, patch]`` **and** its own pre-release. That is why
``^1.0.0`` rejects ``1.5.0-beta`` while ``^1.0.0-alpha`` accepts ``1.0.0-beta``,
and why even ``*`` rejects every pre-release.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Tuple, Union

from .version import InvalidVersion, PartialVersion, Version, parse

__all__ = [
    "Comparator",
    "ComparatorSet",
    "InvalidRange",
    "Range",
    "parse_range",
    "satisfies",
    "sort_versions",
]

# Longest operators first so ">=" is never split into ">" plus "=".
_OPERATORS = ("<=", ">=", "!=", "==", "=", "<", ">")
_HYPHEN_RE = re.compile(r"^(?P<low>\S+)\s+-\s+(?P<high>\S+)$")
# The same shape, but able to sit between other tokens in a conjunction.
_HYPHEN_GROUP_RE = re.compile(r"(?P<low>\S+)\s+-\s+(?P<high>\S+)")
_CARET_RE = re.compile(r"^\^(?P<version>.*)$")
_TILDE_RE = re.compile(r"^~(?P<version>.*)$")
_WILDCARDS = frozenset({"x", "X", "*"})
# Splits a range endpoint into its numeric core and any "-pre"/"+build" suffix.
_ENDPOINT_RE = re.compile(r"^(?P<core>\d+(?:\.\d+)*)(?P<rest>[-+].*)?$")


class InvalidRange(ValueError):
    """Raised when a range expression cannot be parsed.

    Subclasses :class:`ValueError` for the same reason as
    :class:`~semver_lite.version.InvalidVersion`.
    """


def _fail(raw: str, reason: str) -> InvalidRange:
    """Build an :class:`InvalidRange` naming the range and the reason it failed."""
    return InvalidRange(f"invalid version range {raw!r}: {reason}")


def _as_range_error(raw: str, error: Exception) -> InvalidRange:
    """Re-wrap a version-parsing failure as an :class:`InvalidRange`."""
    return error if isinstance(error, InvalidRange) else _fail(raw, str(error))


def _next_of(core: Tuple[int, int, int], level: str) -> Tuple[int, int, int]:
    """Return the core one step above ``core`` at the given granularity.

    Args:
        core: the ``(major, minor, patch)`` core to advance from.
        level: ``"major"``, ``"minor"`` or ``"patch"``: the component that is
            incremented, with every component to its right reset to zero.
    """
    major, minor, patch = core
    if level == "major":
        return (major + 1, 0, 0)
    if level == "minor":
        return (major, minor + 1, 0)
    return (major, minor, patch + 1)


def _exclusive_upper_bound(core: Tuple[int, int, int]) -> Version:
    """Return the smallest version above ``core``: ``core`` with a ``-0`` pre-release."""
    return Version(core[0], core[1], core[2], ("0",))


def _core_of(partial: PartialVersion) -> Tuple[int, int, int]:
    """Return the zero-filled ``(major, minor, patch)`` core of a partial version."""
    return (partial.major or 0, partial.minor or 0, partial.patch or 0)


def _caret_level(partial: PartialVersion) -> str:
    """Return the granularity a caret range pins: ``major``, ``minor`` or ``patch``."""
    if partial.major:
        return "major"
    if partial.minor:
        return "minor"
    return "patch"


@dataclass(frozen=True)
class Comparator:
    """A single operator/version pair such as ``>=1.2.3``.

    Build metadata is ignored during comparison, so ``>=1.2.3+build`` and
    ``>=1.2.3`` are indistinguishable.
    """

    operator: str
    version: Version

    def test(self, candidate: Version) -> bool:
        """Return ``True`` when ``candidate`` satisfies this comparator."""
        order = candidate.compare(self.version)
        if self.operator in ("=", "=="):
            return order == 0
        if self.operator == "!=":
            return order != 0
        if self.operator == ">":
            return order > 0
        if self.operator == ">=":
            return order >= 0
        if self.operator == "<":
            return order < 0
        return order <= 0

    def __str__(self) -> str:
        """Render the comparator, omitting a redundant ``==``."""
        return f"{'' if self.operator == '==' else self.operator}{self.version.to_str()}"


@dataclass(frozen=True)
class ComparatorSet:
    """A conjunction of comparators: a version matches when all of them pass."""

    comparators: Tuple[Comparator, ...] = ()

    def test(self, candidate: Version) -> bool:
        """Return ``True`` when ``candidate`` satisfies every comparator in the set."""
        return all(comparator.test(candidate) for comparator in self.comparators)

    def allows_prerelease(self, candidate: Version) -> bool:
        """Return ``True`` when this set opts ``candidate``'s pre-release in.

        npm and Cargo let a pre-release satisfy a comparator set only when some
        comparator in it pins the same ``[major, minor, patch]`` with its own
        pre-release. A set built from release endpoints alone (such as
        ``^1.0.0``) therefore never admits ``1.5.0-beta``, and an empty set
        admits no pre-release at all.
        """
        if not candidate.is_prerelease:
            return True
        core = (candidate.major, candidate.minor, candidate.patch)
        return any(
            comparator.version.is_prerelease
            and (comparator.version.major, comparator.version.minor, comparator.version.patch) == core
            for comparator in self.comparators
        )

    def __str__(self) -> str:
        """Render the comparators space-separated."""
        return " ".join(str(comparator) for comparator in self.comparators)


@dataclass(frozen=True)
class Range:
    """A disjunction of comparator sets, that is ``A B || C D``.

    A range with no comparator sets matches every release version and no
    pre-release, which is what ``*`` and the empty expression mean.
    """

    sets: Tuple[ComparatorSet, ...] = field(default=())

    def __bool__(self) -> bool:
        """Return ``True`` when the range constrains anything; ``*`` is falsy."""
        return bool(self.sets)

    def test(self, candidate: Version) -> bool:
        """Return ``True`` when ``candidate`` satisfies any comparator set.

        The pre-release rule is applied per comparator set, so a pre-release
        admitted by one group never leaks through another.
        """
        if not self.sets:
            return not candidate.is_prerelease
        return any(
            comparator_set.test(candidate) and comparator_set.allows_prerelease(candidate)
            for comparator_set in self.sets
        )

    def __str__(self) -> str:
        """Render the range in its normalised form."""
        return " || ".join(str(comparator_set) for comparator_set in self.sets)


@dataclass(frozen=True)
class _Endpoint:
    """A range endpoint split into its partial core and optional suffix."""

    partial: PartialVersion
    suffix: str = ""

    @property
    def is_wildcard(self) -> bool:
        """Return ``True`` when the endpoint omits every component."""
        return self.partial.major is None

    def exact(self) -> Version:
        """Return the endpoint as a concrete version, defaulting missing parts to zero."""
        return self.partial.fill()

    def suffixed(self) -> Version:
        """Return the endpoint with its ``-pre``/``+build`` suffix re-attached."""
        return parse(f"{self.exact().to_str()}{self.suffix}")


def _split_operator(text: str) -> Tuple[str, str]:
    """Split a leading comparison operator off an endpoint.

    A bare endpoint, or one whose "operator" is really a pre-release hyphen such
    as in ``1.2.3-beta``, is returned as ``("=", text)``.
    """
    for operator in _OPERATORS:
        if text.startswith(operator):
            return operator, text[len(operator) :].strip()
    return "=", text.strip()


def _split_endpoint(text: str, raw: str) -> _Endpoint:
    """Split a range endpoint into a partial core and any ``-pre``/``+build`` suffix.

    Raises:
        InvalidRange: if the endpoint is not a usable partial version.
    """
    match = _ENDPOINT_RE.match(text.strip())
    try:
        if match is None:
            return _Endpoint(PartialVersion.parse(text), "")
        return _Endpoint(PartialVersion.parse(match.group("core")), match.group("rest") or "")
    except InvalidVersion as error:
        raise _as_range_error(raw, error) from error


def _line_cores(partial: PartialVersion) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """Return the first core of a partial version's line and the first core above it.

    ``1`` yields ``((1,0,0), (2,0,0))`` and ``1.2`` yields
    ``((1,2,0), (1,3,0))``.
    """
    if partial.major is None:
        raise _fail("*", "the bare wildcard has no bounds")
    floor = (partial.major, partial.minor or 0, 0)
    level = "minor" if partial.minor is not None else "major"
    return floor, _next_of(floor, level)


def _line_bounds(partial: PartialVersion) -> Tuple[Version, Version]:
    """Return the inclusive floor and exclusive ceiling of a partial version's line.

    ``1`` yields ``(1.0.0, <2.0.0-0)`` and ``1.2`` yields ``(1.2.0, <1.3.0-0)``.
    """
    floor, next_core = _line_cores(partial)
    return Version(*floor), _exclusive_upper_bound(next_core)


def _just_below(core: Tuple[int, int, int]) -> Version:
    """Return the highest version below ``core``, that is ``core`` with a ``-0`` pre-release."""
    return Version(core[0], core[1], core[2], ("0",))


def _expand_bare(text: str, raw: str, operator: str = "=") -> Tuple[Comparator, ...]:
    """Expand one version, with or without an operator, into comparators.

    An exact version keeps its operator, so ``>1.2.3`` stays ``>1.2.3``. A
    partial version names a whole line of releases, so the operator is applied
    to that line: ``>=1.2`` is ``>=1.2.0``, ``>1.2`` excludes the entire 1.2
    line (so it is ``>=1.3.0``), ``<=1.2`` covers the line inclusively (so it
    is ``<1.3.0-0``) and ``<1.2`` stops at its start (so it is ``<1.2.0-0``).
    The ceiling carries a ``-0`` pre-release so no pre-release sneaks in.
    """
    endpoint = _split_endpoint(text, raw)
    if endpoint.is_wildcard:
        return ()
    if endpoint.suffix or endpoint.partial.patch is not None:
        return (Comparator(operator, endpoint.suffixed() if endpoint.suffix else endpoint.exact()),)
    floor_core, next_core = _line_cores(endpoint.partial)
    floor = Version(*floor_core)
    ceiling = _exclusive_upper_bound(next_core)
    if operator in ("=", "=="):
        return (Comparator(">=", floor), Comparator("<", ceiling))
    if operator == ">=":
        return (Comparator(">=", floor),)
    if operator == ">":
        return (Comparator(">=", Version(*next_core)),)
    if operator == "<=":
        return (Comparator("<", ceiling),)
    return (Comparator("<", _just_below(floor_core)),)


def _expand_caret(text: str, raw: str) -> Tuple[Comparator, ...]:
    """Expand ``^x.y.z`` into comparators.

    With a patch given, the ceiling is fixed by the left-most non-zero
    component: ``^1.2.3`` is ``>=1.2.3 <2.0.0-0``, ``^0.2.3`` is
    ``>=0.2.3 <0.3.0-0`` and ``^0.0.3`` is ``>=0.0.3 <0.0.4-0``. With only a
    minor given the ceiling is the next major for a non-zero major (``^1.2`` is
    ``>=1.2.0 <2.0.0-0``) but the next minor for a zero one (``^0.2`` is
    ``>=0.2.0 <0.3.0-0``). ``^0`` and ``^0.0`` constrain only the ceiling,
    because ``0.x`` is the initial-development line: ``^0`` is ``<1.0.0-0``.
    """
    endpoint = _split_endpoint(text, raw)
    partial = endpoint.partial
    if partial.major is None:
        return ()
    if partial.patch is None:
        if partial.minor is None:
            if partial.major == 0:
                return (Comparator("<", _exclusive_upper_bound(_next_of((0, 0, 0), "major"))),)
            floor, ceiling = _line_bounds(partial)
            return (Comparator(">=", floor), Comparator("<", ceiling))
        if partial.major == 0:
            floor, ceiling = _line_bounds(partial)
            return (Comparator(">=", floor), Comparator("<", ceiling))
        return (
            Comparator(">=", Version(partial.major, partial.minor, 0)),
            Comparator("<", _exclusive_upper_bound(_next_of((partial.major, 0, 0), "major"))),
        )
    return (
        Comparator(">=", endpoint.suffixed() if endpoint.suffix else endpoint.exact()),
        Comparator("<", _exclusive_upper_bound(_next_of(_core_of(partial), _caret_level(partial)))),
    )


def _expand_tilde(text: str, raw: str) -> Tuple[Comparator, ...]:
    """Expand ``~x.y.z``.

    With a minor given, only the patch may change, so ``~1.2.3`` is
    ``>=1.2.3 <1.3.0-0`` and ``~1.2`` is ``>=1.2.0 <1.3.0-0``. Without a minor
    the minor may change too, making ``~1`` equivalent to ``1``; ``~0`` is
    the ceiling-only form used for the initial-development line.
    """
    endpoint = _split_endpoint(text, raw)
    partial = endpoint.partial
    if partial.major is None:
        return ()
    if partial.minor is None:
        if partial.major == 0:
            return (Comparator("<", _exclusive_upper_bound(_next_of((0, 0, 0), "major"))),)
        floor, ceiling = _line_bounds(partial)
        return (Comparator(">=", floor), Comparator("<", ceiling))
    core = (partial.major, partial.minor, partial.patch or 0)
    return (
        Comparator(">=", endpoint.suffixed() if endpoint.suffix else Version(*core)),
        Comparator("<", _exclusive_upper_bound(_next_of(core, "minor"))),
    )


def _expand_hyphen(low: str, high: str, raw: str) -> Tuple[Comparator, ...]:
    """Expand ``low - high``, where either endpoint may be partial.

    Both ends are inclusive: a bare lower endpoint becomes ``>=low`` and a bare
    upper endpoint becomes ``<=high``. A partial upper endpoint is widened to
    the end of its own line, so ``1.2.3 - 2.3`` includes ``2.3.9``.
    """
    low_operator, low_version = _split_operator(low)
    # "=" would pin the lower bound to a single version, so a bare or "="-marked
    # lower endpoint means "at least this version".
    if low_operator == "=":
        low_operator = ">="
    comparators: List[Comparator] = list(_expand_bare(low_version, raw, low_operator))

    high_operator, high_version = _split_operator(high)
    if high_operator == "=":
        # Likewise a bare upper endpoint means "at most this version".
        high_operator = "<="
    comparators.extend(_expand_bare(high_version, raw, high_operator))
    return tuple(comparators)


def _expand_not_equal(text: str, raw: str) -> Tuple[Comparator, ...]:
    """Expand ``!=x``; against a partial version the whole line is excluded."""
    endpoint = _split_endpoint(text, raw)
    if endpoint.is_wildcard:
        return ()
    if endpoint.suffix or endpoint.partial.patch is not None:
        return (Comparator("!=", endpoint.suffixed() if endpoint.suffix else endpoint.exact()),)
    floor, ceiling = _line_bounds(endpoint.partial)
    return (Comparator(">=", floor), Comparator("<", ceiling))


def _expand_token(token: str, raw: str) -> Tuple[Comparator, ...]:
    """Expand a single range token into comparators.

    Raises:
        InvalidRange: if the token is not a recognised range form.
    """
    hyphen = _HYPHEN_RE.match(token)
    if hyphen:
        return _expand_hyphen(hyphen.group("low"), hyphen.group("high"), raw)
    caret = _CARET_RE.match(token)
    if caret:
        if not caret.group("version").strip():
            raise _fail(raw, "'^' must be followed by a version")
        return _expand_caret(caret.group("version"), raw)
    tilde = _TILDE_RE.match(token)
    if tilde:
        if not tilde.group("version").strip():
            raise _fail(raw, "'~' must be followed by a version")
        return _expand_tilde(tilde.group("version"), raw)
    for operator in _OPERATORS:
        if token.startswith(operator):
            remainder = token[len(operator) :].strip()
            if not remainder:
                raise _fail(raw, f"{token!r} has no version after its operator")
            if operator == "!=":
                return _expand_not_equal(remainder, raw)
            return _expand_bare(remainder, raw, operator)
    if token in _WILDCARDS:
        return ()
    return _expand_bare(token, raw)


def _parse_comparator_set(text: str, raw: str) -> ComparatorSet:
    """Parse one whitespace-separated conjunction into a :class:`ComparatorSet`.

    A hyphen range is written ``low - high`` with spaces around the dash, so it
    spans three whitespace-separated tokens rather than one. Such groups are
    scanned from the left for that shape, and only the remaining tokens are
    split normally; this lets a comparator sit on either endpoint, as in
    ``>=1.0.0 - 2.0.0``.
    """
    comparators: List[Comparator] = []
    remainder = text
    match = _HYPHEN_GROUP_RE.search(remainder)
    if match is not None:
        comparators.extend(_expand_hyphen(match.group("low"), match.group("high"), raw))
        remainder = remainder[: match.start()] + " " + remainder[match.end() :]
    for token in remainder.split():
        comparators.extend(_expand_token(token, raw))
    return ComparatorSet(tuple(comparators))


def parse_range(text: Union[str, Range]) -> Range:
    """Parse a range expression into a :class:`Range`.

    Args:
        text: the range expression, for example ``"^1.2.3 || >=2.0.0 <3.0.0"``.

    Returns:
        The normalised :class:`Range`. ``*`` and the empty string both yield a
        range with no comparator sets, which matches every release version.

    Raises:
        InvalidRange: if any part of the expression cannot be parsed.
    """
    if isinstance(text, Range):
        return text
    if not isinstance(text, str):
        raise _fail(repr(text), "a range must be a string")
    stripped = text.strip()
    if not stripped:
        return Range(())
    sets: List[ComparatorSet] = []
    for group in stripped.split("||"):
        cleaned = group.strip()
        if not cleaned:
            continue
        comparator_set = _parse_comparator_set(cleaned, stripped)
        # A group that constrains nothing (a lone "*") would otherwise admit
        # every pre-release, so it is dropped rather than kept as an empty set.
        if comparator_set.comparators:
            sets.append(comparator_set)
    return Range(tuple(sets))


def satisfies(version: Union[str, Version], range_text: Union[str, Range]) -> bool:
    """Return ``True`` when ``version`` satisfies ``range_text``.

    Args:
        version: the version to test, as a string or :class:`Version`.
        range_text: the range expression, or an already parsed :class:`Range`.

    Returns:
        ``True`` when the version falls inside the range.

    Raises:
        InvalidVersion: if ``version`` is not a valid semantic version.
        InvalidRange: if the range expression cannot be parsed.
    """
    candidate = version if isinstance(version, Version) else parse(version)
    return parse_range(range_text).test(candidate)


def sort_versions(versions: Iterable[Union[str, Version]]) -> List[Version]:
    """Return ``versions`` in ascending precedence order.

    The sort is stable, so versions of equal precedence (differing only in
    build metadata) keep their input order.

    Args:
        versions: an iterable of :class:`Version` objects or version strings.

    Returns:
        A new list of :class:`Version` objects in ascending order.

    Raises:
        InvalidVersion: if any element is not a valid semantic version.
    """
    return sorted(item if isinstance(item, Version) else parse(item) for item in versions)