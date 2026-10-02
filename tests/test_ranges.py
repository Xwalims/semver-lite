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