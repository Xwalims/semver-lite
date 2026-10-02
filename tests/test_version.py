"""Tests for strict SemVer 2.0.0 parsing and string round-tripping."""

import unittest

from semver_lite import InvalidVersion, PartialVersion, Version, parse, parse_partial


class TestValidVersions(unittest.TestCase):
    """Every version form the spec's grammar accepts must parse."""

    def test_parses_bare_core(self) -> None:
        v = parse("1.2.3")
        self.assertEqual((v.major, v.minor, v.patch), (1, 2, 3))
        self.assertEqual(v.prerelease, ())
        self.assertEqual(v.build, ())

    def test_parses_zero_version(self) -> None:
        self.assertEqual(parse("0.0.0").to_str(), "0.0.0")

    def test_parses_large_numbers(self) -> None:
        self.assertEqual(parse("99999999999999999999.0.0").major, 99999999999999999999)

    def test_parses_single_hyphen_prerelease(self) -> None:
        self.assertEqual(parse("1.0.0-alpha").prerelease, ("alpha",))

    def test_parses_dotted_prerelease(self) -> None:
        self.assertEqual(parse("1.0.0-alpha.1").prerelease, ("alpha", "1"))

    def test_parses_prerelease_from_spec_examples(self) -> None:
        for raw, pre in (
            ("1.0.0-alpha", ("alpha",)),
            ("1.0.0-alpha.1", ("alpha", "1")),
            ("1.0.0-0.3.7", ("0", "3", "7")),
            ("1.0.0-x.7.z.92", ("x", "7", "z", "92")),
            ("1.0.0-x-y-z.--", ("x-y-z", "--")),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(parse(raw).prerelease, pre)

    def test_parses_build_metadata_from_spec_examples(self) -> None:
        for raw, build in (
            ("1.0.0-alpha+001", ("001",)),
            ("1.0.0+20130313144700", ("20130313144700",)),
            ("1.0.0-beta+exp.sha.5114f85", ("exp", "sha", "5114f85")),
            ("1.0.0+21AF26D3----117B344092BD", ("21AF26D3----117B344092BD",)),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(parse(raw).build, build)

    def test_parses_prerelease_with_build(self) -> None:
        v = parse("1.0.0-rc.1+build.7")
        self.assertEqual(v.prerelease, ("rc", "1"))
        self.assertEqual(v.build, ("build", "7"))

    def test_build_may_contain_leading_zeroes(self) -> None:
        self.assertEqual(parse("1.0.0+0.build.1").build, ("0", "build", "1"))

    def test_to_str_round_trips(self) -> None:
        for raw in ("1.2.3", "0.0.4", "1.0.0-alpha", "1.0.0-rc.1+build.7"):
            with self.subTest(raw=raw):
                self.assertEqual(parse(raw).to_str(), raw)

    def test_direct_constructor_matches_parse(self) -> None:
        built = Version(1, 2, 3, ("rc", "1"), ("b",))
        self.assertEqual(built, parse("1.2.3-rc.1+b"))


class TestInvalidVersions(unittest.TestCase):
    """Every rejection the spec mandates must raise InvalidVersion."""

    def assert_rejected(self, raw: str) -> None:
        with self.assertRaises(InvalidVersion, msg=raw):
            parse(raw)

    def test_rejects_leading_v_prefix(self) -> None:
        self.assert_rejected("v1.2.3")

    def test_rejects_equals_prefix(self) -> None:
        self.assert_rejected("=1.2.3")

    def test_rejects_surrounding_whitespace(self) -> None:
        self.assert_rejected(" 1.2.3")
        self.assert_rejected("1.2.3 ")

    def test_rejects_missing_core_component(self) -> None:
        for raw in ("1", "1.2", "1.2.3.4", ""):
            with self.subTest(raw=raw):
                self.assert_rejected(raw)

    def test_rejects_leading_zeroes_in_core(self) -> None:
        for raw in ("01.2.3", "1.02.3", "1.2.03"):
            with self.subTest(raw=raw):
                self.assert_rejected(raw)

    def test_rejects_negative_core(self) -> None:
        self.assert_rejected("-1.2.3")
        self.assert_rejected("1.-2.3")

    def test_rejects_empty_prerelease(self) -> None:
        for raw in ("1.0.0-", "1.0.0-alpha..1", "1.0.0-alpha."):
            with self.subTest(raw=raw):
                self.assert_rejected(raw)

    def test_rejects_leading_zero_numeric_prerelease(self) -> None:
        for raw in ("1.0.0-01", "1.0.0-alpha.01"):
            with self.subTest(raw=raw):
                self.assert_rejected(raw)

    def test_rejects_non_ascii_identifier_characters(self) -> None:
        for raw in ("1.0.0-\u00e9", "1.0.0-alpha_\u00e9"):
            with self.subTest(raw=raw):
                self.assert_rejected(raw)

    def test_rejects_empty_build_identifier(self) -> None:
        for raw in ("1.0.0+", "1.0.0+build..1", "1.0.0+build."):
            with self.subTest(raw=raw):
                self.assert_rejected(raw)

    def test_rejects_two_build_separators(self) -> None:
        self.assert_rejected("1.0.0+a+b")

    def test_rejects_non_numeric_core(self) -> None:
        self.assert_rejected("one.two.three")
        self.assert_rejected("1.x.3")

    def test_rejects_range_operators(self) -> None:
        self.assert_rejected(">=1.2.3")
        self.assert_rejected("1.2.3 - 2.0.0")

    def test_error_message_names_the_offending_value(self) -> None:
        with self.assertRaises(InvalidVersion) as ctx:
            parse("01.2.3")
        self.assertIn("01.2.3", str(ctx.exception))


class TestNonStrictMode(unittest.TestCase):
    """Lenient parsing accepts the common tolerance shims only when asked."""

    def test_strict_mode_rejects_v_prefix_by_default(self) -> None:
        self.assertRaises(InvalidVersion, parse, "v1.2.3")

    def test_non_strict_mode_accepts_v_prefix(self) -> None:
        self.assertEqual(parse("v1.2.3", strict=False).to_str(), "1.2.3")

    def test_non_strict_mode_accepts_surrounding_whitespace(self) -> None:
        self.assertEqual(parse("  1.2.3\n", strict=False).to_str(), "1.2.3")

    def test_non_strict_mode_still_rejects_leading_zeroes(self) -> None:
        self.assertRaises(InvalidVersion, parse, "01.2.3", strict=False)


class TestPartialVersions(unittest.TestCase):
    """Partial versions back range endpoints and may omit trailing components."""

    def test_parses_each_partial_shape(self) -> None:
        self.assertEqual(parse_partial("1"), PartialVersion(1, None, None))
        self.assertEqual(parse_partial("1.2"), PartialVersion(1, 2, None))
        self.assertEqual(parse_partial("1.2.3"), PartialVersion(1, 2, 3))
        self.assertEqual(parse_partial("1.x"), PartialVersion(1, None, None))
        self.assertEqual(parse_partial("1.2.x"), PartialVersion(1, 2, None))

    def test_bare_wildcards_have_no_major(self) -> None:
        self.assertIsNone(parse_partial("x").major)
        self.assertIsNone(parse_partial("*").major)
        self.assertIsNone(parse_partial("X").major)

    def test_to_str_can_render_as_a_wildcard(self) -> None:
        self.assertEqual(parse_partial("1").to_str(), "1")
        self.assertEqual(parse_partial("1").to_str(wildcard=True), "1.x")
        self.assertEqual(parse_partial("1.2").to_str(wildcard=True), "1.2.x")
        self.assertEqual(parse_partial("1.2.3").to_str(wildcard=True), "1.2.3")

    def test_fill_defaults_missing_components_to_zero(self) -> None:
        self.assertEqual(parse_partial("1").fill(), parse("1.0.0"))
        self.assertEqual(parse_partial("1.2").fill(), parse("1.2.0"))

    def test_wildcard_has_no_concrete_value(self) -> None:
        self.assertRaises(InvalidVersion, parse_partial("x").fill)

    def test_rejects_invalid_partial_components(self) -> None:
        for raw in ("01.2", "one.two", "1.x.3", "1.2.3.4"):
            with self.subTest(raw=raw):
                self.assertRaises(InvalidVersion, parse_partial, raw)


class TestHashability(unittest.TestCase):
    """Versions are frozen values usable as dict keys."""

    def test_hashable_and_usable_in_sets(self) -> None:
        versions = {parse("1.0.0"), parse("1.0.0"), parse("1.0.1")}
        self.assertEqual(len(versions), 2)

    def test_frozen_dataclass_rejects_mutation(self) -> None:
        v = parse("1.2.3")
        self.assertRaises(Exception, setattr, v, "major", 9)


if __name__ == "__main__":
    unittest.main()