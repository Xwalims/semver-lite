"""End-to-end tests for the semver-lite command-line interface.

Each test runs the CLI in a real subprocess so exit codes and stdout are
exercised end to end, the way a shell or CI job would use it.
"""

import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_cli(*arguments: str) -> subprocess.CompletedProcess:
    """Run ``python3 -m semver_lite.cli`` with ``arguments`` in the project root.

    Args:
        *arguments: the command-line arguments to pass.

    Returns:
        The completed process, with captured stdout and stderr.
    """
    return subprocess.run(
        [sys.executable, "-m", "semver_lite.cli", *arguments],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class TestHelpAndUsage(unittest.TestCase):
    """The CLI must document itself and refuse unknown arguments."""

    def test_help_exits_zero_and_lists_commands(self) -> None:
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0)
        for command in ("parse", "compare", "sort", "satisfies"):
            with self.subTest(command=command):
                self.assertIn(command, result.stdout)

    def test_no_arguments_is_a_usage_error(self) -> None:
        result = run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage", result.stderr.lower())

    def test_unknown_command_is_a_usage_error(self) -> None:
        result = run_cli("bogus")
        self.assertEqual(result.returncode, 2)


class TestParseCommand(unittest.TestCase):
    """``parse`` echoes the canonical form of a version."""

    def test_parse_prints_canonical_version(self) -> None:
        result = run_cli("parse", "1.2.3")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "1.2.3")

    def test_parse_preserves_prerelease_and_build(self) -> None:
        result = run_cli("parse", "1.0.0-rc.1+build.7")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "1.0.0-rc.1+build.7")

    def test_parse_rejects_invalid_version_with_exit_code_two(self) -> None:
        result = run_cli("parse", "01.2.3")
        self.assertEqual(result.returncode, 2)
        self.assertIn("01.2.3", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_parse_rejects_leading_v_prefix(self) -> None:
        self.assertEqual(run_cli("parse", "v1.2.3").returncode, 2)


class TestCompareCommand(unittest.TestCase):
    """``compare`` prints an ordering word and signals it through its exit code."""

    def test_greater_exits_zero_and_prints_greater(self) -> None:
        result = run_cli("compare", "2.0.0", "1.0.0")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "greater")

    def test_less_exits_one_and_prints_less(self) -> None:
        result = run_cli("compare", "1.0.0", "2.0.0")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "less")

    def test_equal_exits_zero_and_prints_equal(self) -> None:
        result = run_cli("compare", "1.0.0", "1.0.0+b")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "equal")

    def test_prerelease_precedence_is_honoured(self) -> None:
        result = run_cli("compare", "1.0.0-alpha", "1.0.0")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "less")

    def test_invalid_input_is_a_usage_error(self) -> None:
        result = run_cli("compare", "1.0.0", "nope")
        self.assertEqual(result.returncode, 2)
        self.assertIn("nope", result.stderr)

    def test_missing_operand_is_a_usage_error(self) -> None:
        self.assertEqual(run_cli("compare", "1.0.0").returncode, 2)


class TestSortCommand(unittest.TestCase):
    """``sort`` prints one ascending version per line."""

    def test_sort_orders_versions_ascending(self) -> None:
        result = run_cli(
            "sort", "1.10.0", "1.9.0", "1.0.0-alpha", "1.0.0", "0.9.9"
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout.split(),
            ["0.9.9", "1.0.0-alpha", "1.0.0", "1.9.0", "1.10.0"],
        )

    def test_sort_accepts_versions_from_stdin(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "semver_lite.cli", "sort"],
            cwd=PROJECT_ROOT,
            input="2.0.0\n1.0.0\n1.5.0\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.split(), ["1.0.0", "1.5.0", "2.0.0"])

    def test_sort_rejects_any_invalid_version(self) -> None:
        result = run_cli("sort", "1.0.0", "not-a-version")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not-a-version", result.stderr)

    def test_sort_with_no_input_is_a_usage_error(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "semver_lite.cli", "sort"],
            cwd=PROJECT_ROOT,
            input="",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("no versions to sort", result.stderr)


class TestSatisfiesCommand(unittest.TestCase):
    """``satisfies`` prints ``true``/``false`` and reports via its exit code."""

    def test_satisfied_version_prints_true_and_exits_zero(self) -> None:
        result = run_cli("satisfies", "1.2.3", "^1.2.0")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "true")

    def test_unsatisfied_version_prints_false_and_exits_one(self) -> None:
        result = run_cli("satisfies", "2.0.0", "^1.2.0")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "false")

    def test_hyphen_range_from_the_shell(self) -> None:
        result = run_cli("satisfies", "1.5.0", "1.2.3 - 2.0.0")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "true")

    def test_invalid_range_is_a_usage_error(self) -> None:
        result = run_cli("satisfies", "1.0.0", "garbage")
        self.assertEqual(result.returncode, 2)
        self.assertIn("garbage", result.stderr)

    def test_invalid_version_is_a_usage_error(self) -> None:
        result = run_cli("satisfies", "nope", "^1.0.0")
        self.assertEqual(result.returncode, 2)
        self.assertIn("nope", result.stderr)


if __name__ == "__main__":
    unittest.main()