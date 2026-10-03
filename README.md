# semver-lite

A strict implementation of [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) in pure Python, with no dependencies. It parses and compares versions, sorts them, and tests them against version ranges using the same syntax as npm and Cargo.

<!-- hero -->

[![CI](https://github.com/Xwalims/semver-lite/actions/workflows/ci.yml/badge.svg)](https://github.com/Xwalims/semver-lite/actions/workflows/ci.yml)
![python 3.11 – 3.13](https://img.shields.io/badge/python-3.11–3.13-blue)
![MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![dependencies](https://img.shields.io/badge/dependencies-none-2f6f4f)

## Contents

- [What it is](#what-it-is)
- [Spec conformance](#spec-conformance)
- [Install](#install)
- [Usage](#usage)
  - [Command line](#command-line)
  - [Exit codes](#exit-codes)
- [Supported range syntax](#supported-range-syntax)
  - [The pre-release rule](#the-pre-release-rule)
- [Library API](#library-api)
  - [Parsing](#parsing)
  - [Exceptions](#exceptions)
- [Running the tests](#running-the-tests)
- [License](#license)

<!-- /hero -->

## What it is

- **Strict by default.** Only versions allowed by the spec's Backus-Naur form parse. A `v` prefix, an `=` prefix, surrounding whitespace, a leading zero in any core component, and a leading zero in any numeric pre-release identifier are all rejected.
- **Correct precedence.** The full ordering from section 11 of the spec, including numeric identifiers compared numerically rather than as text, numeric identifiers ranking below alphanumeric ones, ASCII ordering for alphanumeric identifiers, and a longer identifier list outranking a shorter one.
- **Build metadata is ignored for precedence,** as the spec requires, while still being preserved for round-tripping.
- **npm-compatible ranges,** including the pre-release rule that surprises people: a pre-release version only satisfies a range when a comparator pins the same `[major, minor, patch]` line with its own pre-release.
- **A command-line tool** with documented exit codes, suitable for use in shell scripts and CI.
- **No dependencies,** no C extensions, and no import-time configuration. Tested on Python 3.11, 3.12 and 3.13.

## Spec conformance

| Spec requirement | How it is met |
| --- | --- |
| `<valid semver>` grammar (section 10 BNF) | The grammar is transcribed directly to regular expressions; anything that does not match is rejected with a message naming the rule it breaks |
| Numeric identifiers must not have leading zeroes | Enforced for `MAJOR`, `MINOR`, `PATCH` and for every numeric pre-release identifier |
| Pre-release identifiers are `[0-9A-Za-z-]`, non-empty | Enforced per dot-separated identifier; empty identifiers such as in `1.0.0-alpha..1` are rejected |
| Build identifiers are `[0-9A-Za-z-]`, non-empty | Enforced per identifier; leading zeroes are allowed here, as the spec permits |
| Core compared numerically (section 11) | Integer comparison, so `1.9.0 < 1.10.0` |
| Pre-release ranks below its release | `1.0.0-rc.1 < 1.0.0` |
| Identifiers compared left to right until a difference | Implemented as specified |
| Numeric below alphanumeric | `1.0.0-1 < 1.0.0-alpha` |
| More identifiers outrank fewer | `1.0.0-alpha < 1.0.0-alpha.1` |
| Build metadata ignored in precedence | `1.0.0+a == 1.0.0+b` |

The spec does not define range syntax. This library follows the node-semver and Cargo conventions for ranges, and the behaviour was verified against node-semver 7 over a matrix of 98 range expressions against 42 versions — 4116 cases, of which the 252 using syntax node-semver rejects are excluded — with full agreement on every remaining case.

Two range details are worth stating explicitly, because both are easy to get backwards:

- **A wildcard group swallows the whole range.** In `* || 1.2.3`, the `*` makes every other group redundant, so the expression is just `*`. The same applies to `1.2.3 || *`, and to every other spelling of an unbounded group (`x`, `>=0.0.0`, `^x`).
- **A group that matches nothing is dropped, not absorbed.** `<x` and `>x` are unsatisfiable, since no version sorts below or above the whole space, so `<x || 1.2.3` narrows to `1.2.3`. They are the opposite of `*`, which constrains nothing rather than admitting nothing.

In a partial version every component may be a wildcard, or none may be: `x.x` and `1.x.x` are accepted and name the same thing as `x` and `1.x`, while `x.1.x` is rejected, because a number after a wildcard has no single reading.

## Install

This package is **not published to PyPI** — the name is unregistered, so
`pip install semver-lite` fails. Install it from a checkout instead:

```console
$ git clone https://github.com/Xwalims/semver-lite.git
$ cd semver-lite
$ python3 -m pip install .
```

To work on a checkout instead, run it straight from the project root with `python3 -m semver_lite.cli`; no installation is needed for that.

## Usage

### Command line

```console
$ python3 -m semver_lite.cli --help
usage: semver-lite [-h] COMMAND ...

Parse, compare, sort and test strict SemVer 2.0.0 versions.

positional arguments:
  COMMAND
    parse      print the canonical form of a version
    compare    compare two versions
    sort       sort versions in ascending order
    satisfies  test a version against a range

options:
  -h, --help   show this help message and exit

exit codes:
  0  success; for compare, A is greater than or equal to B
  1  for compare, A is less than B; for satisfies, V is outside RANGE
  2  usage error, invalid version or invalid range

examples:
  semver-lite parse 1.0.0-rc.1
  semver-lite compare 1.0.0-alpha 1.0.0
  semver-lite sort 1.10.0 1.9.0 1.0.0
  semver-lite satisfies 1.2.3 '^1.2.0'
```

Parse a version and print its canonical form:

```console
$ python3 -m semver_lite.cli parse 1.0.0-rc.1+build.7
1.0.0-rc.1+build.7
```

Compare two versions. A pre-release is less than its release, so the exit code is 1:

```console
$ python3 -m semver_lite.cli compare 1.0.0-alpha 1.0.0
less
$ echo $?
1
```

Sort a list, which orders numerically rather than lexically, so `1.10.0` lands after `1.9.0`:

```console
$ python3 -m semver_lite.cli sort 1.10.0 1.9.0 1.0.0-alpha 1.0.0-beta.11 1.0.0-beta.2 0.9.9 1.0.0
0.9.9
1.0.0-alpha
1.0.0-beta.2
1.0.0-beta.11
1.0.0
1.9.0
1.10.0
```

`sort` also reads from standard input when no versions are given:

```console
$ printf '2.0.0\n1.0.0\n1.5.0\n' | python3 -m semver_lite.cli sort
1.0.0
1.5.0
2.0.0
```

Test a version against a range:

```console
$ python3 -m semver_lite.cli satisfies 1.2.3 '^1.2.0'
true
$ python3 -m semver_lite.cli satisfies 2.0.0 '^1.2.0'
false
$ echo $?
1
```

Invalid input is reported on standard error with exit code 2:

```console
$ python3 -m semver_lite.cli parse 01.2.3
error: invalid semantic version '01.2.3': a normal version must take the form X.Y.Z of non-negative integers without leading zeroes
$ echo $?
2
```

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success. For `compare`, the first version is greater than or equal to the second. For `satisfies`, the version is inside the range. |
| `1` | For `compare`, the first version is less than the second. For `satisfies`, the version is outside the range. |
| `2` | Usage error, invalid version, or invalid range. |

## Supported range syntax

| Form | Example | Meaning |
| --- | --- | --- |
| Exact | `1.2.3` | Only `1.2.3` |
| Equality | `=1.2.3`, `==1.2.3` | Only `1.2.3` |
| Inequality | `!=1.2.3` | Anything except `1.2.3` |
| Greater than | `>1.2.3` | `1.2.4` and above |
| Greater or equal | `>=1.2.3` | `1.2.3` and above |
| Less than | `<1.2.3` | Below `1.2.3` |
| Less or equal | `<=1.2.3` | `1.2.3` and below |
| Caret | `^1.2.3` | `>=1.2.3 <2.0.0-0`; the left-most non-zero component is pinned, so `^0.2.3` is `>=0.2.3 <0.3.0-0` and `^0.0.3` is `>=0.0.3 <0.0.4-0` |
| Tilde | `~1.2.3` | `>=1.2.3 <1.3.0-0`; with no minor, `~1.2` still stops at `1.3.0-0` |
| Wildcard | `1.2.x`, `1.x`, `x`, `*` | `1.2.x` is `>=1.2.0 <1.3.0-0`; `1.x` is `>=1.0.0 <2.0.0-0`; `*` matches every release |
| Partial version | `1.2`, `1` | Same as the matching wildcard: `>=1.2.0 <1.3.0-0` and `>=1.0.0 <2.0.0-0` |
| Hyphen range | `1.2.3 - 2.0.0` | Inclusive at both ends; a partial upper endpoint widens, so `1.2.3 - 2.3` includes `2.3.9` |
| Conjunction | `>=1.2.3 <2.0.0` | Space-separated comparators, all of which must hold |
| Disjunction | `^1.0.0 \|\| ^2.0.0` | Either group may match |

Comparators applied to a partial version act on the whole line that the partial version names: `>=1.2` is `>=1.2.0`, `>1.2` excludes the entire `1.2` line, and `<=1.2` covers that line inclusively.

### The pre-release rule

A version carrying a pre-release satisfies a range only when some comparator in the matching set has the same `[major, minor, patch]` **and** its own pre-release. This is npm and Cargo behaviour, and it is deliberate: a range that names only release versions will not silently start accepting unstable builds.

```python
satisfies("1.5.0-beta", "^1.0.0")      # False, nothing pins a 1.5.0 pre-release
satisfies("1.5.0-beta", "*")            # False, the bare wildcard pins nothing
satisfies("1.0.0-beta", ">=1.0.0-0")   # True,  >=1.0.0-0 pins the 1.0.0 pre-release line
satisfies("1.0.0-beta", "^1.0.0-alpha")  # True, the floor pins the 1.0.0 pre-release line
```

The mechanism is an exclusive ceiling written `<NEXT-0`. The `-0` suffix is the lowest possible pre-release, so `^1.2.3` becomes `>=1.2.3 <2.0.0-0`, which contains every `1.x.y` release but no `2.0.0` pre-release.

## Library API

```python
from semver_lite import parse, compare, satisfies, sort_versions, parse_range
```

### Parsing

`parse(version, strict=True) -> Version` parses a version. With `strict=False` a leading `v` or `=` and surrounding whitespace are tolerated; every other rule still applies. Invalid input raises `InvalidVersion`, a subclass of `ValueError`, with a message naming the value and the rule it breaks.

```python
>>> parse("1.0.0-rc.1+build.7")
Version(major=1, minor=0, patch=0, prerelease=('rc', '1'), build=('build', '7'))
>>> parse("1.0.0").to_str()
'1.0.0'
>>> parse("v1.2.3", strict=False).to_str()
'1.2.3'
>>> parse("01.2.3")
InvalidVersion: invalid semantic version '01.2.3': a normal version must take the form X.Y.Z of non-negative integers without leading zeroes
```

`parse_partial(text) -> PartialVersion` parses the partial versions used inside ranges, accepting `1`, `1.2`, `1.2.3`, `1.x`, `1.2.x`, `x` and `*`.

### Comparing

`Version` is a frozen dataclass with a total ordering, so it supports `<`, `<=`, `==`, `>`, `>=`, `sorted`, and use as a dictionary key.

```python
>>> parse("1.0.0-alpha") < parse("1.0.0")
True
>>> parse("1.0.0-2") < parse("1.0.0-11")
True
>>> parse("1.0.0+a") == parse("1.0.0+b")
True
>>> compare("1.9.0", "1.10.0")
-1
>>> [v.to_str() for v in sorted(parse(s) for s in ("1.0.0", "1.0.0-alpha", "0.9.9"))]
['0.9.9', '1.0.0-alpha', '1.0.0']
```

`compare(left, right) -> int` accepts strings or `Version` objects and returns `-1`, `0` or `1`.

`sort_versions(versions) -> list[Version]` sorts an iterable of strings or `Version` objects. The sort is stable, so versions that differ only in build metadata keep their input order.

### Ranges

`satisfies(version, range_text) -> bool` accepts strings or objects on both sides.

```python
>>> satisfies("1.2.3", "^1.2.0")
True
>>> satisfies("2.0.0", "^1.2.0")
False
>>> satisfies("1.5.0", ">=1.0.0 <2.0.0 || >=3.0.0 <4.0.0")
True
```

`parse_range(text) -> Range` parses a range once for repeated use. `str(range)` shows the normalised form, which is useful for debugging.

```python
>>> print(parse_range("^1.2.3"))
>=1.2.3 <2.0.0-0
>>> print(parse_range("1.2.3 - 2.0.0"))
>=1.2.3 <=2.0.0
>>> range_ = parse_range("~1.2")
>>> satisfies("1.2.9", range_), satisfies("1.3.0", range_)
(True, False)
```

An invalid range raises `InvalidRange`, also a subclass of `ValueError`.

### Exceptions

| Exception | Base | Raised when |
| --- | --- | --- |
| `InvalidVersion` | `ValueError` | A version string violates the spec grammar |
| `InvalidRange` | `ValueError` | A range expression cannot be parsed |

## Running the tests

The suite uses only the standard library, so no installation step is needed:

```console
$ python3 -m unittest discover -s tests -t . -v
```

The full suite runs in about a second. CI runs the same command on Python 3.11, 3.12 and 3.13.

## License

MIT. See [LICENSE](LICENSE).
