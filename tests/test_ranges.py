"""Tests for range syntax, each comparator's boundaries, and the pre-release rule.

Expected values are cross-checked against node-semver 7.x, which is the
reference implementation for this syntax. ``!=`` is a semver-lite extension:
node-semver has no such operator.
"""

import unittest

from semver_lite import InvalidRange, Range, parse, parse_range, satisfies


class TestComparatorOperators(unittest.TestCase):
    """Each comparison operator must accept exactly its own domain."""

    def test_equality_operators(self) -> None:
        for operator in ("=", "=="):
            with self.subTest(operator=operator):
                self.assertTrue(satisfies("1.2.3", f"{operator}1.2.3"))
                self.assertFalse(satisfies("1.2.4", f"{operator}1.2.3"))

    def test_not_equal_operator(self) -> None:
        self.assertTrue(satisfies("1.2.4", "!=1.2.3"))
        self.assertTrue(satisfies("1.2.2", "!=1.2.3"))
        self.assertFalse(satisfies("1.2.3", "!=1.2.3"))

    def test_greater_than_is_exclusive(self) -> None:
        self.assertTrue(satisfies("1.2.4", ">1.2.3"))
        self.assertTrue(satisfies("2.0.0", ">1.2.3"))
        self.assertFalse(satisfies("1.2.3", ">1.2.3"))

    def test_greater_than_or_equal_is_inclusive(self) -> None:
        self.assertTrue(satisfies("1.2.3", ">=1.2.3"))
        self.assertTrue(satisfies("1.2.4", ">=1.2.3"))

    def test_less_than_is_exclusive(self) -> None:
        self.assertTrue(satisfies("1.2.2", "<1.2.3"))
        self.assertFalse(satisfies("1.2.3", "<1.2.3"))

    def test_less_than_or_equal_is_inclusive(self) -> None:
        self.assertTrue(satisfies("1.2.3", "<=1.2.3"))
        self.assertTrue(satisfies("1.2.2", "<=1.2.3"))

    def test_bare_version_is_equality(self) -> None:
        self.assertTrue(satisfies("1.2.3", "1.2.3"))
        self.assertFalse(satisfies("1.2.4", "1.2.3"))


class TestCaretRanges(unittest.TestCase):
    """Caret pins the left-most non-zero component."""

    def test_caret_allows_minor_and_patch_bumps(self) -> None:
        for version in ("1.2.3", "1.2.4", "1.3.0", "1.9.9"):
            with self.subTest(version=version):
                self.assertTrue(satisfies(version, "^1.2.3"))

    def test_caret_excludes_next_major(self) -> None:
        for version in ("2.0.0", "2.0.0-alpha", "1.2.2"):
            with self.subTest(version=version):
                self.assertFalse(satisfies(version, "^1.2.3"))

    def test_caret_on_zero_major_pins_minor(self) -> None:
        self.assertTrue(satisfies("0.2.3", "^0.2.3"))
        self.assertTrue(satisfies("0.2.9", "^0.2.3"))
        self.assertFalse(satisfies("0.3.0", "^0.2.3"))

    def test_caret_on_zero_minor_pins_patch(self) -> None:
        self.assertTrue(satisfies("0.0.3", "^0.0.3"))
        self.assertFalse(satisfies("0.0.4", "^0.0.3"))

    def test_caret_with_partial_versions(self) -> None:
        self.assertTrue(satisfies("1.9.0", "^1.2"))
        self.assertFalse(satisfies("2.0.0", "^1.2"))
        self.assertTrue(satisfies("1.9.9", "^1"))
        self.assertFalse(satisfies("2.0.0", "^1"))
        self.assertTrue(satisfies("0.9.9", "^0"))
        self.assertFalse(satisfies("1.0.0", "^0"))

    def test_caret_with_wildcard(self) -> None:
        self.assertTrue(satisfies("1.3.0", "^1.2.x"))
        self.assertFalse(satisfies("2.0.0", "^1.x"))


class TestTildeRanges(unittest.TestCase):
    """Tilde allows patch bumps when a minor is present, minor bumps otherwise."""

    def test_tilde_allows_patch_bumps_only(self) -> None:
        for version in ("1.2.3", "1.2.9"):
            with self.subTest(version=version):
                self.assertTrue(satisfies(version, "~1.2.3"))
        self.assertFalse(satisfies("1.3.0", "~1.2.3"))

    def test_tilde_on_zero_major(self) -> None:
        self.assertTrue(satisfies("0.2.9", "~0.2.3"))
        self.assertFalse(satisfies("0.3.0", "~0.2.3"))

    def test_tilde_with_partial_versions(self) -> None:
        self.assertTrue(satisfies("1.2.9", "~1.2"))
        self.assertFalse(satisfies("1.3.0", "~1.2"))
        self.assertTrue(satisfies("1.9.9", "~1"))
        self.assertFalse(satisfies("2.0.0", "~1"))
        self.assertTrue(satisfies("0.9.9", "~0"))

    def test_tilde_with_wildcard(self) -> None:
        self.assertTrue(satisfies("1.9.9", "~1.x"))
        self.assertTrue(satisfies("1.2.9", "~1.2.x"))


class TestWildcardsAndPartialVersions(unittest.TestCase):
    """Wildcards and partial versions stand in for the next component upward."""

    def test_bare_wildcard_matches_any_release(self) -> None:
        for version in ("0.0.0", "5.0.0", "99.99.99"):
            with self.subTest(version=version):
                self.assertTrue(satisfies(version, "*"))
        for wildcard in ("x", "X", "*"):
            with self.subTest(wildcard=wildcard):
                self.assertTrue(satisfies("5.0.0", wildcard))

    def test_partial_minor_version(self) -> None:
        self.assertTrue(satisfies("1.2.0", "1.2"))
        self.assertTrue(satisfies("1.2.9", "1.2"))
        self.assertFalse(satisfies("1.3.0", "1.2"))

    def test_partial_major_version(self) -> None:
        self.assertTrue(satisfies("1.0.0", "1"))
        self.assertTrue(satisfies("1.9.9", "1"))
        self.assertFalse(satisfies("2.0.0", "1"))

    def test_patch_wildcard(self) -> None:
        self.assertTrue(satisfies("1.2.0", "1.2.x"))
        self.assertTrue(satisfies("1.2.9", "1.2.x"))
        self.assertFalse(satisfies("1.3.0", "1.2.x"))

    def test_minor_wildcard(self) -> None:
        self.assertTrue(satisfies("1.0.0", "1.x"))
        self.assertTrue(satisfies("1.9.9", "1.x"))
        self.assertFalse(satisfies("2.0.0", "1.x"))

    def test_wildcard_with_explicit_operator(self) -> None:
        self.assertTrue(satisfies("1.2.9", "=1.2.x"))

    def test_empty_range_matches_everything(self) -> None:
        self.assertTrue(satisfies("1.0.0", ""))


class TestHyphenRanges(unittest.TestCase):
    """``low - high`` is inclusive at both ends, with partial upper endpoints widened."""

    def test_full_endpoints_are_inclusive(self) -> None:
        self.assertTrue(satisfies("1.2.3", "1.2.3 - 2.0.0"))
        self.assertTrue(satisfies("2.0.0", "1.2.3 - 2.0.0"))
        self.assertFalse(satisfies("2.0.1", "1.2.3 - 2.0.0"))
        self.assertFalse(satisfies("1.2.2", "1.2.3 - 2.0.0"))

    def test_full_upper_endpoint_stays_exact(self) -> None:
        self.assertTrue(satisfies("2.3.4", "1.2.3 - 2.3.4"))
        self.assertFalse(satisfies("2.3.5", "1.2.3 - 2.3.4"))
        self.assertFalse(satisfies("2.3.9", "1.2.3 - 2.3.4"))

    def test_partial_upper_endpoint_covers_its_whole_line(self) -> None:
        # "2.3" names a line of releases, so the range runs to the end of it.
        self.assertTrue(satisfies("2.3.9", "1.2.3 - 2.3"))
        self.assertFalse(satisfies("2.4.0", "1.2.3 - 2.3"))
        self.assertTrue(satisfies("2.2.9", "1.2.3 - 2.3"))

    def test_partial_both_endpoints(self) -> None:
        self.assertTrue(satisfies("1.5.0", "1.2 - 2"))
        self.assertFalse(satisfies("3.0.0", "1.2 - 2"))
        self.assertTrue(satisfies("2.3.4", "1.2 - 2.3.4"))

    def test_equal_endpoints_is_a_single_version(self) -> None:
        self.assertTrue(satisfies("1.2.3", "1.2.3 - 1.2.3"))
        self.assertFalse(satisfies("1.2.4", "1.2.3 - 1.2.3"))


class TestConjunctionAndDisjunction(unittest.TestCase):
    """Space-separated comparators AND together; ``||`` groups OR together."""

    def test_space_separated_comparators_are_conjunctive(self) -> None:
        self.assertTrue(satisfies("1.9.9", ">=1.2.3 <2.0.0"))
        self.assertFalse(satisfies("2.0.0", ">=1.2.3 <2.0.0"))
        self.assertFalse(satisfies("1.2.2", ">=1.2.3 <2.0.0"))
        self.assertTrue(satisfies("1.3.0", ">1.2.3 <=1.3.0"))

    def test_disjunction_accepts_either_group(self) -> None:
        self.assertTrue(satisfies("1.2.3", "1.2.3 || 2.0.0"))
        self.assertTrue(satisfies("2.0.0", "1.2.3 || 2.0.0"))
        self.assertFalse(satisfies("3.0.0", "1.2.3 || 2.0.0"))

    def test_disjunction_of_carets(self) -> None:
        self.assertTrue(satisfies("2.5.0", "^1.0.0 || ^2.0.0"))
        self.assertFalse(satisfies("3.0.0", "^1.0.0 || ^2.0.0"))

    def test_disjunction_with_conjunctions_in_each_group(self) -> None:
        expression = ">=1.0.0 <2.0.0 || >=3.0.0 <4.0.0"
        self.assertTrue(satisfies("1.5.0", expression))
        self.assertFalse(satisfies("2.5.0", expression))
        self.assertTrue(satisfies("3.5.0", expression))

    def test_tolerates_extra_whitespace(self) -> None:
        self.assertTrue(satisfies("1.5.0", "  >=1.0.0   <2.0.0  "))
        self.assertTrue(satisfies("3.5.0", ">=1.0.0 <2.0.0 || >=3.0.0 <4.0.0"))

    def test_whitespace_between_operator_and_version_is_ignored(self) -> None:
        """``>= 1.2.3`` means ``>=1.2.3``.

        node-semver trims whitespace between an operator and the version it
        modifies before splitting the range into comparators, so the split
        never sees a bare ``>=``. Splitting first here left that bare operator
        as its own token, which then failed with "no version after its
        operator" -- an error on a range npm resolves happily.
        """
        for operator, expected in ((">=", ">=1.2.3"), ("<=", "<=1.2.3"), ("<", "<1.2.3"),
                                   (">", ">1.2.3"), ("=", "=1.2.3")):
            for spacing in (" ", "  ", "   "):
                with self.subTest(operator=operator, spacing=spacing):
                    expression = f"{operator}{spacing}1.2.3"
                    self.assertEqual(str(parse_range(expression)), expected)
        # Both spellings of the pessimistic operator, and both prefix forms.
        for expression, expected in (("~ 1.2.3", ">=1.2.3 <1.3.0-0"),
                                     ("~> 1.2.3", ">=1.2.3 <1.3.0-0"),
                                     ("^ 1.2.3", ">=1.2.3 <2.0.0-0"),
                                     (">= 2.0.0-0", ">=2.0.0-0"),
                                     (">= 1.0.0 < 2.0.0", ">=1.0.0 <2.0.0")):
            with self.subTest(expression=expression):
                self.assertEqual(str(parse_range(expression)), expected)
        # The trimmed form means the same thing, so it selects the same versions.
        self.assertTrue(satisfies("1.2.3", ">= 1.2.3"))
        self.assertTrue(satisfies("1.2.3", "~ 1.2.3"))
        self.assertFalse(satisfies("1.3.0", "~> 1.2.3"))

    def test_hyphen_range_survives_the_operator_trim(self) -> None:
        """Trimming must not eat a hyphen range's ``low - high`` endpoints.

        The `` - `` between the endpoints is whitespace after no operator, and
        the endpoints themselves may carry one *and* a space, as in
        ``>= 1.0.0 - 2.0.0``. The trim removes only the space after the
        operator; the operator-bearing endpoint is then rejected for carrying an
        operator at all, which is the hyphen rule below.
        """
        self.assertEqual(str(parse_range("1.2.3 - 2.0.0")), ">=1.2.3 <=2.0.0")
        self.assertTrue(satisfies("1.5.0", "1.2.3 - 2.0.0"))
        self.assertFalse(satisfies("2.0.1", "1.2.3 - 2.0.0"))

    def test_hyphen_endpoints_may_not_carry_an_operator(self) -> None:
        """``>=1.0.0 - 2.0.0`` is rejected, not read as ``>=1.0.0 <=2.0.0``.

        node-semver's HYPHENRANGE token allows only a bare endpoint on each
        side. This library used to strip the operator and expand the endpoint as
        if it were bare, so a range npm rejects became a real range here --
        silently, and to something other than what was written.
        """
        for expression in (">=1.0.0 - 2.0.0", "1.0.0 - <=2.0.0", "^1.0.0 - 2.0.0",
                           "~1.0.0 - 2.0.0", "<1.0.0 - 2.0.0", ">1.0.0 - 2.0.0",
                           "!=1.0.0 - 2.0.0", ">= 1.0.0 - 2.0.0", "1.0.0 - <= 2.0.0"):
            with self.subTest(expression=expression):
                with self.assertRaises(InvalidRange):
                    parse_range(expression)
        # Bare endpoints, the form node-semver does accept, still work.
        self.assertEqual(str(parse_range("1.0.0 - 2.0.0")), ">=1.0.0 <=2.0.0")
        self.assertEqual(str(parse_range("1.0.0 - 2.0.0-beta")), ">=1.0.0 <=2.0.0-beta")
        self.assertEqual(str(parse_range("1.2.3-alpha - 2.0.0")), ">=1.2.3-alpha <=2.0.0")
        self.assertEqual(str(parse_range("1.2.3 - 2.3")), ">=1.2.3 <2.4.0-0")

    def test_hyphen_range_must_be_the_whole_group(self) -> None:
        """``1.2.3 - 2.0.0 >=1.0.0`` is rejected, not merged with ``>=1.0.0``.

        node-semver's HYPHENRANGE token is anchored with ``^`` and ``$``, so the
        endpoints have to span the entire ``||`` group. This library searched for
        the shape anywhere in the group and kept whatever tokens were left over,
        so a range npm refuses was accepted here and its comparators silently
        attached to the hyphen bounds.
        """
        for expression in ("1.2.3 - 2.0.0 >=1.0.0", ">=1.0.0 1.2.3 - 2.0.0",
                           "1.2.3 - 2.0.0 <3.0.0", "~1.0.0 1.2.3 - 2.0.0",
                           "1.2.3 - 2.0.0 || >=1.0.0 <3.0.0"):
            with self.subTest(expression=expression):
                # The last one is legal: the hyphen group is the *first* one and
                # spans it entirely, so the comparator group beside it is a
                # separate "||" group. 2.5.0 is inside >=1.0.0 <3.0.0, and 3.5.0
                # is outside both groups.
                if expression == "1.2.3 - 2.0.0 || >=1.0.0 <3.0.0":
                    self.assertTrue(satisfies("1.5.0", expression))
                    self.assertTrue(satisfies("2.5.0", expression))
                    self.assertFalse(satisfies("3.5.0", expression))
                    self.assertFalse(satisfies("0.5.0", expression))
                    continue
                with self.assertRaises(InvalidRange):
                    parse_range(expression)
        # A separate group is the supported way to add a lower bound.
        self.assertEqual(str(parse_range(">=1.0.0 || 1.2.3 - 2.0.0")),
                         ">=1.0.0 || >=1.2.3 <=2.0.0")

    def test_tilde_gte_is_a_synonym_for_tilde(self) -> None:
        """``~>`` is node-semver's LONETILDE spelling, so it means ``~``."""
        for expression in ("~>1.2.3", "~> 1.2.3", "~>1.2", "~>1"):
            with self.subTest(expression=expression):
                self.assertEqual(str(parse_range(expression)), str(parse_range("~" + expression[2:])))
        self.assertTrue(satisfies("1.2.9", "~>1.2.3"))
        self.assertFalse(satisfies("1.3.0", "~>1.2.3"))

    def test_wildcard_group_absorbs_the_whole_disjunction(self) -> None:
        """``* || anything`` is just ``*``.

        node-semver collapses the entire range when any ``||`` group is a bare
        wildcard, so the other groups are redundant rather than additive. This
        is the wildcard absorbing them, not the wildcard being discarded: the
        sibling case, ``1.2.3 || *``, is the same range written backwards.
        """
        for expression in ("* || 1.2.3", "1.2.3 || *", "* || ^2.0.0", "^2.0.0 || *",
                           "1.2.3 || 1.2.4 || *", "* || *", "x || 1.2.3", "1.2.3 || x",
                           ">=0.0.0 || 1.2.3", "1.2.3 || >=0.0.0",
                           "* || >=1.0.0 <2.0.0", "1.2.3 || * || 5.0.0"):
            with self.subTest(expression=expression):
                # A wildcard matches every release version, whichever version
                # the sibling groups happen to name.
                for version in ("0.0.1", "1.2.3", "1.5.0", "2.0.0", "3.0.0", "5.0.0"):
                    self.assertTrue(satisfies(version, expression))
                # It still admits no pre-release, exactly like a bare "*".
                self.assertFalse(satisfies("1.0.0-alpha", expression))
                self.assertFalse(satisfies("1.2.3-alpha", expression))

    def test_disjunction_without_a_wildcard_group_is_not_absorbed(self) -> None:
        """The absorption above must not overreach onto ordinary disjunctions.

        ``>=0.0.0`` is itself a wildcard spelling, but only within its own
        conjunction, so this group keeps the sibling group that follows it:
        node-semver normalises the whole expression to ``<2.0.0||3.0.0``, not
        to the wildcard.
        """
        expression = ">=0.0.0 <2.0.0 || 3.0.0"
        self.assertTrue(satisfies("1.5.0", expression))
        # Nothing may match between the two groups, so absorption -- which
        # would make every release match -- is still disproved here.
        self.assertFalse(satisfies("2.5.0", expression))
        self.assertFalse(satisfies("3.5.0", expression))
        self.assertTrue(satisfies("3.0.0", expression))

    def test_wildcard_group_absorption_normalises_to_the_wildcard(self) -> None:
        """The normalised form of an absorbed range is the bare wildcard."""
        self.assertEqual(str(parse_range("* || 1.2.3")), "")
        self.assertEqual(str(parse_range("1.2.3 || *")), "")
        self.assertFalse(parse_range("* || 1.2.3"))

    def test_empty_group_is_a_wildcard_not_an_absent_one(self) -> None:
        """``1.0.0 ||`` is ``*``, not ``=1.0.0``.

        node-semver splits on ``||`` and parses each group, and the empty string
        parses to a single ANY comparator rather than to nothing. Its filter
        drops comparator lists that are empty, and this one is not, so the
        group survives and swallows the disjunction exactly as a bare ``*``
        would. Dropping it instead narrows the range to the groups that
        happened to survive, which is the opposite of what was written.
        """
        for expression in ("1.0.0 ||", "|| 1.0.0", "1.0.0 || ", " || 1.0.0",
                           "1.0.0||", "1.0.0 || || 2.0.0", "1.0.0 ||  || 2.0.0",
                           "1.0.0 || 2.0.0 ||", "|| 1.0.0 ||", "|| 1.0.0 || 2.0.0",
                           "|| 1.0.0-alpha", "1.0.0-alpha ||", "^1.0.0 ||",
                           "|| ^1.0.0", "|| || 1.0.0 || ||", "1.0.0 || ||",
                           "|| 1.0.0 || ||"):
            with self.subTest(expression=expression):
                for version in ("0.0.1", "0.3.2", "1.0.0", "2.0.0", "5.0.0", "9.9.9"):
                    self.assertTrue(satisfies(version, expression))
                # Being the wildcard, it still admits no pre-release.
                self.assertFalse(satisfies("1.0.0-alpha", expression))
                self.assertEqual(str(parse_range(expression)), "")

    def test_empty_group_absorbs_even_beside_a_null_set_group(self) -> None:
        """A dead group does not stop an empty group from widening the range.

        ``<x || 1.2.3`` drops the dead group and keeps ``1.2.3``, but appending
        an empty group adds a live ANY comparator, so the whole expression
        becomes the wildcard.
        """
        self.assertEqual(str(parse_range("<x ||")), "")
        self.assertEqual(str(parse_range("|| <x")), "")
        self.assertTrue(satisfies("9.9.9", "<x ||"))
        self.assertTrue(satisfies("9.9.9", "|| <x"))
        # Without the empty group the null set is still merely dropped.
        self.assertEqual(str(parse_range("<x || 1.2.3")), "=1.2.3")

    def test_null_set_group_is_dropped_rather_than_absorbed(self) -> None:
        """``<x`` matches nothing, so it must not widen the range to ``*``.

        This is the case that distinguishes the two ways a group can end up
        contributing no comparators. A bare ``*`` constrains nothing and makes
        the range unbounded; ``<x`` is unsatisfiable and contributes nothing.
        Conflating them turns ``<x || 1.2.3`` -- a dead group next to a real
        one -- into the wildcard, which matches everything.
        """
        for expression in ("<x", ">x", "<x || 1.2.3", ">x || 1.2.3", "1.2.3 || <x",
                           "<x || >x || 1.2.3"):
            with self.subTest(expression=expression):
                if expression in ("<x", ">x"):
                    # A lone null set still constrains something -- to nothing --
                    # so it is truthy, unlike the wildcard which constrains
                    # nothing at all. What matters is that it matches no version.
                    self.assertTrue(parse_range(expression))
                    self.assertFalse(satisfies("0.0.0", expression))
                    self.assertFalse(satisfies("1.2.3", expression))
                    continue
                self.assertTrue(satisfies("1.2.3", expression))
                self.assertFalse(satisfies("1.2.4", expression))
                self.assertFalse(satisfies("0.0.0", expression))

    def test_exclusive_comparators_against_the_wildcard_are_the_null_set(self) -> None:
        """``<x`` and ``>x`` are empty; the inclusive spellings are not."""
        # Nothing sorts below or above the whole space.
        for expression in ("<x", ">x", "<0.0.0-0"):
            with self.subTest(expression=expression):
                self.assertFalse(satisfies("0.0.0", expression))
                self.assertFalse(satisfies("9.9.9", expression))
        # >=x and <=x include the entire space, so they are the wildcard.
        for expression in (">=x", "<=x", "=x", "^x", "~x"):
            with self.subTest(expression=expression):
                self.assertTrue(satisfies("0.0.0", expression))
                self.assertTrue(satisfies("9.9.9", expression))
                self.assertFalse(satisfies("1.0.0-alpha", expression))

    def test_multi_component_wildcard_endpoints(self) -> None:
        """Every component of an endpoint may be a wildcard, or none may be.

        ``x.x`` and ``1.x.x`` are accepted, so a repeated wildcard is not a
        parse error. But ``x.1.x`` is rejected: a number after a wildcard has
        no single reading, and guessing would silently change the endpoint.
        """
        for expression in ("x.x", "X.X", "*.*", "x.*", "*.x"):
            with self.subTest(expression=expression):
                # Every component wild means the whole space, so it is the bare
                # wildcard and normalises to the empty range.
                self.assertEqual(str(parse_range(expression)), "")
                self.assertTrue(satisfies("9.9.9", expression))
        # A wildcard in a later position names the same line as a bare partial
        # version, since the components after it add nothing.
        self.assertEqual(str(parse_range("1.x.x")), str(parse_range("1.x")))
        self.assertTrue(satisfies("1.2.3", "1.x.x"))
        self.assertFalse(satisfies("2.0.0", "1.x.x"))
        # A wildcard group still absorbs its siblings.
        self.assertTrue(satisfies("9.9.9", "x.x || 1.2.3"))
        # A number after a wildcard has no single reading, so it is rejected.
        for expression in ("x.1.x", "x.x.1"):
            with self.subTest(expression=expression), self.assertRaises(InvalidRange):
                parse_range(expression)


class TestPrereleaseRule(unittest.TestCase):
    """npm/Cargo semantics: a pre-release needs a comparator pinning its own line."""

    def test_prerelease_rejected_when_range_names_only_releases(self) -> None:
        for expression in (">=1.0.0", "^1.0.0", "~1.2.3", "1.2.3 - 2.0.0", "*", "1.x"):
            with self.subTest(expression=expression):
                self.assertFalse(satisfies("1.0.0-beta", expression))
                self.assertFalse(satisfies("1.5.0-beta", expression))

    def test_prerelease_accepted_when_a_comparator_pins_its_line(self) -> None:
        self.assertTrue(satisfies("1.0.0-beta", ">=1.0.0-0"))
        self.assertTrue(satisfies("1.0.0", ">=1.0.0-0"))
        # The pinned line must be the candidate's own [major, minor, patch].
        self.assertTrue(satisfies("1.2.3-beta", ">=1.2.3-alpha"))
        self.assertTrue(satisfies("1.2.3", ">=1.2.3-alpha"))
        # 1.0.0-beta is not in the 1.2.3 prerelease line, and is below the floor.
        self.assertFalse(satisfies("1.0.0-beta", ">=1.2.3-alpha"))

    def test_caret_with_prerelease_endpoint(self) -> None:
        self.assertTrue(satisfies("1.0.0-alpha", "^1.0.0-alpha"))
        self.assertTrue(satisfies("1.0.0-beta", "^1.0.0-alpha"))
        self.assertTrue(satisfies("1.0.0", "^1.0.0-alpha"))
        self.assertTrue(satisfies("1.0.1", "^1.0.0-alpha"))
        # Only prereleases are gated; the upper bound still excludes 2.0.0.
        self.assertFalse(satisfies("2.0.0", "^1.0.0-alpha"))
        self.assertFalse(satisfies("1.3.0-alpha", "^1.2.3-alpha"))

    def test_release_versions_never_need_the_prerelease_opt_in(self) -> None:
        self.assertTrue(satisfies("1.0.0", ">=1.0.0"))
        self.assertTrue(satisfies("1.0.0", "1.x"))
        self.assertTrue(satisfies("1.0.0", "*"))

    def test_prerelease_below_the_pinned_floor_is_still_excluded(self) -> None:
        # 0.5.0 < 1.0.0-0, so the lower bound rejects it regardless of opt-in.
        self.assertFalse(satisfies("0.5.0-beta", ">=1.0.0-0"))

    def test_build_metadata_does_not_affect_satisfies(self) -> None:
        self.assertTrue(satisfies("1.0.0+build", "^1.0.0"))
        self.assertTrue(satisfies("1.0.0", "^1.0.0+build"))

    def test_build_metadata_on_a_wildcard_endpoint_is_ignored(self) -> None:
        # node-semver strips build metadata before it expands an x-range, so
        # "1.2.x+b" is exactly "1.2.x" and "x+b" is exactly "x". Verified
        # against node-semver 7.8.5: both normalise to the same comparator set.
        for suffixed, bare in (("1.2.x+b", "1.2.x"), ("1+b", "1"),
                               ("x+b", "x"), ("*+b", "*"),
                               ("1.x.x+b", "1.x"), ("1.2.3+b", "1.2.3")):
            with self.subTest(expression=suffixed):
                self.assertEqual(str(parse_range(suffixed)), str(parse_range(bare)))
        self.assertTrue(satisfies("9.9.9", "x+b"))
        self.assertTrue(satisfies("1.2.4", "1.2.x+b"))
        self.assertFalse(satisfies("2.0.0", "1.2.x+b"))

    def test_prerelease_on_a_wildcard_patch_is_ignored(self) -> None:
        # A wildcard patch names a whole line, which has no single pre-release
        # to pin, so node-semver expands "1.2.x-alpha" to ">=1.2.0 <1.3.0-0".
        # Confirmed by reading its expansion table, not inferred.
        for suffixed, bare in (("1.2.x-alpha", "1.2.x"), ("1.x.x-a", "1.x"),
                               ("0.0.x-alpha", "0.0.x"),
                               ("^1.2.x-alpha", "^1.2.x"),
                               ("~1.2.x-alpha", "~1.2.x"),
                               ("1.2.x-alpha+b", "1.2.x")):
            with self.subTest(expression=suffixed):
                self.assertEqual(str(parse_range(suffixed)), str(parse_range(bare)))
        self.assertTrue(satisfies("1.2.4", "1.2.x-alpha"))
        self.assertFalse(satisfies("2.0.0", "1.2.x-alpha"))
        # A wildcard patch still admits no pre-release of its own accord.
        self.assertFalse(satisfies("1.2.4-alpha", "1.2.x-alpha"))

    def test_prerelease_too_early_on_an_endpoint_is_rejected(self) -> None:
        # The pre-release needs a patch component to attach to. "1.2.3-alpha"
        # has one; "1.2-alpha" and "1.x-alpha" do not, so they are invalid
        # rather than silently read as their bare cores. node-semver 7.8.5
        # rejects all three of these too.
        for expression in ("1.2-alpha", "1.x-alpha", "x-alpha", "*-alpha",
                           "1.2-0", "1.x-a.1"):
            with self.subTest(expression=expression), self.assertRaises(InvalidRange):
                parse_range(expression)

    def test_junk_suffixes_are_reported_not_swallowed(self) -> None:
        # Dropping the suffix must not turn malformed input into a valid
        # range; each of these is invalid before and after the change.
        for expression in ("1.2.x-", "1.2.x-a_b", "1.2.x-a!", "1.2.x+",
                           "1.2.+", "1.2.+b", "1.2.3-", "1.2.3+",
                           "1.2.4.5-alpha", "1..2-x"):
            with self.subTest(expression=expression), self.assertRaises(InvalidRange):
                parse_range(expression)


class TestRangeNormalisation(unittest.TestCase):
    """parse_range should expose the same comparator sets satisfies uses."""

    def test_caret_normalises_to_comparators(self) -> None:
        self.assertEqual(str(parse_range("^1.2.3")), ">=1.2.3 <2.0.0-0")
        self.assertEqual(str(parse_range("^0.2.3")), ">=0.2.3 <0.3.0-0")
        self.assertEqual(str(parse_range("^0.0.3")), ">=0.0.3 <0.0.4-0")
        self.assertEqual(str(parse_range("~1.2.3")), ">=1.2.3 <1.3.0-0")

    def test_partial_and_hyphen_normalise_to_comparators(self) -> None:
        self.assertEqual(str(parse_range("1.2")), ">=1.2.0 <1.3.0-0")
        self.assertEqual(str(parse_range("1")), ">=1.0.0 <2.0.0-0")
        self.assertEqual(str(parse_range("1.2.3 - 2.0.0")), ">=1.2.3 <=2.0.0")
        self.assertEqual(str(parse_range("1.2.3 - 2.3")), ">=1.2.3 <2.4.0-0")
        self.assertEqual(str(parse_range("1.2 - 2")), ">=1.2.0 <3.0.0-0")

    def test_bare_wildcard_normalises_to_empty_range(self) -> None:
        self.assertEqual(str(parse_range("*")), "")
        self.assertFalse(bool(parse_range("*")))
        self.assertTrue(bool(parse_range(">=1.0.0")))

    def test_caret_and_tilde_partial_normalisation(self) -> None:
        self.assertEqual(str(parse_range("^1.2")), ">=1.2.0 <2.0.0-0")
        self.assertEqual(str(parse_range("^0.2")), ">=0.2.0 <0.3.0-0")
        self.assertEqual(str(parse_range("~1.2")), ">=1.2.0 <1.3.0-0")
        self.assertEqual(str(parse_range("~1")), ">=1.0.0 <2.0.0-0")

    def test_range_object_is_reusable(self) -> None:
        parsed = parse_range("^1.0.0")
        self.assertIsInstance(parsed, Range)
        self.assertTrue(satisfies("1.5.0", parsed))
        self.assertFalse(satisfies("2.0.0", parsed))

    def test_parsed_range_accepts_prebuilt_version(self) -> None:
        self.assertTrue(satisfies(parse("1.5.0"), "^1.0.0"))


class TestInvalidRanges(unittest.TestCase):
    """Unparseable expressions must raise InvalidRange with a useful message."""

    def assert_rejected(self, expression: str) -> None:
        with self.assertRaises(InvalidRange, msg=expression):
            parse_range(expression)

    def test_rejects_operator_without_version(self) -> None:
        for expression in (">=", "<", "^", "~"):
            with self.subTest(expression=expression):
                self.assert_rejected(expression)

    def test_rejects_garbage(self) -> None:
        for expression in ("garbage", "not-a-range", "1.2.3.4", "^^1.2.3", "one.two"):
            with self.subTest(expression=expression):
                self.assert_rejected(expression)

    def test_rejects_dangling_hyphen_range(self) -> None:
        self.assert_rejected("1.2.3 -")
        self.assert_rejected("- 2.0.0")

    def test_rejects_invalid_endpoint_in_otherwise_valid_range(self) -> None:
        self.assert_rejected(">=1.0.0 garbage")
        self.assert_rejected("^1.0.0 || garbage")

    def test_error_message_names_the_range(self) -> None:
        with self.assertRaises(InvalidRange) as ctx:
            parse_range("garbage")
        self.assertIn("garbage", str(ctx.exception))

    def test_invalid_range_is_a_value_error(self) -> None:
        self.assertTrue(issubclass(InvalidRange, ValueError))


if __name__ == "__main__":
    unittest.main()