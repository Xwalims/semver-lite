"""Tests for SemVer 2.0.0 precedence ordering, as specified in section 11."""

import unittest

from semver_lite import PRERELEASE_EXAMPLE_CHAIN, Version, compare, parse


class TestCanonicalChain(unittest.TestCase):
    """The spec's own precedence chain must hold exactly as written."""

    def test_spec_example_chain_is_strictly_ascending(self) -> None:
        versions = [parse(raw) for raw in PRERELEASE_EXAMPLE_CHAIN]
        for lower, higher in zip(versions, versions[1:]):
            with self.subTest(lower=lower.to_str(), higher=higher.to_str()):
                self.assertLess(lower, higher)

    def test_spec_example_chain_uses_every_documented_identifier(self) -> None:
        self.assertEqual(
            PRERELEASE_EXAMPLE_CHAIN,
            (
                "1.0.0-alpha",
                "1.0.0-alpha.1",
                "1.0.0-alpha.beta",
                "1.0.0-beta",
                "1.0.0-beta.2",
                "1.0.0-beta.11",
                "1.0.0-rc.1",
                "1.0.0",
            ),
        )

    def test_numeric_identifiers_compare_numerically_not_lexically(self) -> None:
        # "11" > "2" numerically, which string comparison would get backwards.
        self.assertLess(parse("1.0.0-2"), parse("1.0.0-11"))
        self.assertLess(parse("1.0.0-beta.2"), parse("1.0.0-beta.11"))

    def test_numeric_identifiers_rank_below_alphanumeric(self) -> None:
        self.assertLess(parse("1.0.0-1"), parse("1.0.0-alpha"))
        self.assertLess(parse("1.0.0-alpha.1"), parse("1.0.0-alpha.beta"))

    def test_alphanumeric_identifiers_compare_in_ascii_order(self) -> None:
        self.assertLess(parse("1.0.0-A"), parse("1.0.0-Z"))
        self.assertLess(parse("1.0.0-alpha"), parse("1.0.0-beta"))
        # ASCII sorts every uppercase letter before every lowercase one.
        self.assertLess(parse("1.0.0-Z"), parse("1.0.0-a"))

    def test_longer_prerelease_ranks_above_shorter_prefix(self) -> None:
        self.assertLess(parse("1.0.0-alpha"), parse("1.0.0-alpha.1"))
        self.assertLess(parse("1.0.0-alpha.1"), parse("1.0.0-alpha.1.0"))

    def test_prerelease_ranks_below_its_own_release(self) -> None:
        self.assertLess(parse("1.0.0-rc.1"), parse("1.0.0"))
        self.assertLess(parse("1.0.0-zzz"), parse("1.0.0"))

    def test_core_components_compare_numerically(self) -> None:
        self.assertLess(parse("1.0.0"), parse("2.0.0"))
        self.assertLess(parse("2.0.0"), parse("2.1.0"))
        self.assertLess(parse("2.1.0"), parse("2.1.1"))
        self.assertLess(parse("1.9.0"), parse("1.10.0"))

    def test_core_dominates_prerelease(self) -> None:
        # 1.0.0-alpha loses to 0.9.9 even though it is a prerelease.
        self.assertLess(parse("0.9.9"), parse("1.0.0-alpha"))


class TestBuildMetadataIsIgnored(unittest.TestCase):
    """Section 10: build metadata must not affect precedence."""

    def test_versions_differing_only_in_build_are_equal(self) -> None:
        self.assertEqual(parse("1.0.0+build.1"), parse("1.0.0+build.2"))
        self.assertEqual(parse("1.0.0+alpha"), parse("1.0.0+beta"))

    def test_release_and_prerelease_still_differ_with_build(self) -> None:
        self.assertLess(parse("1.0.0-alpha+001"), parse("1.0.0+002"))

    def test_build_metadata_survives_round_trip(self) -> None:
        self.assertEqual(parse("1.0.0+001").to_str(), "1.0.0+001")
        self.assertEqual(parse("1.0.0+exp.sha.5114f85").build, ("exp", "sha", "5114f85"))
        self.assertEqual(parse("1.0.0+a").build, ("a",))

    def test_hash_ignores_build_metadata(self) -> None:
        self.assertEqual(hash(parse("1.0.0+a")), hash(parse("1.0.0+b")))


class TestTotalOrdering(unittest.TestCase):
    """The ordering must be a total order over Version instances."""

    SAMPLES = (
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-beta",
        "1.0.0",
        "1.0.1",
        "1.1.0",
        "2.0.0",
        "0.1.0",
    )

    def test_sorting_yields_spec_order(self) -> None:
        ordered = [v.to_str() for v in sorted(parse(s) for s in self.SAMPLES)]
        self.assertEqual(
            ordered,
            [
                "0.1.0",
                "1.0.0-alpha",
                "1.0.0-alpha.1",
                "1.0.0-beta",
                "1.0.0",
                "1.0.1",
                "1.1.0",
                "2.0.0",
            ],
        )

    def test_comparison_is_antisymmetric_and_total(self) -> None:
        versions = [parse(s) for s in self.SAMPLES]
        for a in versions:
            for b in versions:
                with self.subTest(a=a.to_str(), b=b.to_str()):
                    self.assertEqual(a.compare(b), -b.compare(a))
                    self.assertEqual(a < b, b > a)
                    self.assertEqual(a == b, b == a)

    def test_compare_returns_minus_one_zero_or_one(self) -> None:
        self.assertEqual(compare("1.0.0", "2.0.0"), -1)
        self.assertEqual(compare("2.0.0", "1.0.0"), 1)
        self.assertEqual(compare("1.0.0", "1.0.0+a"), 0)

    def test_sort_is_stable_for_equal_precedence(self) -> None:
        left = parse("1.0.0+first")
        right = parse("1.0.0+second")
        self.assertEqual([v.build[0] for v in sorted([left, right])], ["first", "second"])
        self.assertEqual([v.build[0] for v in sorted([right, left])], ["second", "first"])

    def test_sort_versions_sorts_mixed_strings_and_versions(self) -> None:
        from semver_lite import sort_versions

        result = [v.to_str() for v in sort_versions(["1.10.0", parse("1.9.0"), "1.2.0"])]
        self.assertEqual(result, ["1.2.0", "1.9.0", "1.10.0"])

    def test_comparison_with_non_version_is_not_implemented(self) -> None:
        self.assertNotEqual(parse("1.0.0"), "1.0.0")
        self.assertRaises(TypeError, lambda: parse("1.0.0") < "1.0.0")

    def test_total_ordering_provides_ge_and_le(self) -> None:
        low, high = parse("1.0.0"), parse("2.0.0")
        self.assertTrue(low <= high)
        self.assertFalse(low >= high)
        self.assertTrue(low >= low)
        self.assertTrue(high >= low)
        self.assertFalse(high <= low)
        self.assertTrue(high > low)
        self.assertTrue(low < high)


if __name__ == "__main__":
    unittest.main()