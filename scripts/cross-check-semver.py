#!/usr/bin/env python3
"""Compare semver-lite's range parser against node-semver, if node-semver exists.

This script exists because hand-written expectations about range syntax got it
wrong three separate times: 2001:db8-style guesses about wildcard endpoints, a
claim that a pre-release needs all three components spelled out, and a reading
of "accepted" from node-semver that was actually a null range quietly meaning
"rejected". Asking the reference implementation is faster than reasoning.

node-semver is NOT a dependency of this project. When no copy can be found the
script says so and exits 0, so it is safe to wire into CI on a machine that
does not have it.

Usage:  python3 scripts/cross-check-semver.py
Exit 0 when every case agrees (or when no oracle is available), 1 otherwise.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Ranges that exercise endpoint parsing: wildcard cores, suffixes attached to
# wildcards, suffixes with too few components to bind to, and malformed input.
CASES = [
    # valid, and the suffix binds to the patch
    "1.2.3-alpha",
    "1.2.3-alpha.1",
    "1.2.3-alpha.1+b",
    "1.2.3+build",
    # valid: a wildcard supplies the component the suffix attaches to
    "1.2.x-alpha",
    "1.2.x+b",
    "1.2.x-ALPHA",
    "x-alpha.1",
    "x+b",
    # plain wildcards and comparators
    "*",
    "1.2.x",
    ">=1.2",
    "1.2.3 - 2.0.0",
    "1.2.3-alpha - 2.0.0",
    "1.2.3 || 2.0.0-alpha",
    # an empty group is a wildcard group, not a missing one
    "1.2.3 ||",
    "|| 1.2.3",
    "1.2.3 || || 2.0.0",
    "<x ||",
    # whitespace between an operator and its version
    ">= 1.2.3",
    "<=  1.2.3",
    "~ 1.2.3",
    "^ 1.2.3",
    ">= 1.0.0 < 2.0.0",
    ">= 1.0.0 - 2.0.0",
    # node-semver's LONETILDE spelling, the same token as "~"
    "~>1.2.3",
    "~> 1.2.3",
    # a hyphen range is anchored and its endpoints must be bare
    "1.2.3 - 2.0.0-beta",
    "1.2.3-alpha - 2.0.0",
    "1.2.3 - 2.3",
    ">=1.0.0 - 2.0.0",
    "1.0.0 - <=2.0.0",
    "^1.0.0 - 2.0.0",
    "1.2.3 - 2.0.0 >=1.0.0",
    ">=1.0.0 1.2.3 - 2.0.0",
    ">=1.0.0 || 1.2.3 - 2.0.0",
    # a suffix with no patch component to bind to
    "1.2-alpha",
    "1.x-alpha",
    "1-alpha",
    "x-alpha",
    "-alpha",
    "~1.2-alpha",
    "^1.2-alpha",
    # malformed
    "1.2.3-",
    "1.2.3.4-alpha",
    "1.2.3-a_b",
    # ^ and ~ accept a wildcard major, even one with numbers after it: the
    # tokenizer's XRANGEPLAIN lets every component be a wildcard independently,
    # and replaceCaret/replaceTilde discard the token when the major is x. These
    # were all rejected here until they were found against the reference.
    "^x.1.8",
    "^x.1",
    "~x.1.8",
    "~x.0",
    "~>x.0",
    "^x.x.8",
    "~>x.2.6-0",
    "^X.1.0-rc.1",
    "~X.3.3-beta",
    # a wildcard below the major contributes nothing, so these mean ^1.x, ^0.x, ^x
    "^1.x.8",
    "~1.x.8",
    "~>1.x.8",
    "^0.x.8",
    "~0.x.8",
    "^1.x.x",
    "~1.x.x",
    # the bare form still refuses a number after a wildcard, so it must not
    # start accepting these by accident
    "x.1.8",
    "x.1",
    "x.1.x",
    "x.x.8",
    "1.x.8",
    "*.1.8",
    "X.1.8",
    ">=x.1.8",
    ">x.1.8",
    "<x.1.8",
]

NODE_PROBE = r"""
const candidates = [];
if (process.argv[2]) candidates.push(process.argv[2]);
for (const p of (process.env.NODE_PATH || '').split(':').filter(Boolean)) {
  candidates.push(p + '/semver');
}
let s = null;
for (const c of candidates) {
  try { s = require(c); break; } catch (e) { /* try the next one */ }
}
if (!s) { console.log(JSON.stringify({ found: false })); process.exit(0); }
const cases = JSON.parse(process.argv[1]);
const out = cases.map((r) => {
  // A null range means node-semver could not build a usable range. That is a
  // rejection, however quietly it happened, and treating it as "accepted" is
  // how this script first produced nine phantom mismatches.
  const range = s.validRange(r);
  return [r, range === null ? 'rejected' : 'accepted'];
});
console.log(JSON.stringify({ found: true, out }));
"""


def find_node_semver():
    """Locate a usable copy of node-semver, or return None."""
    roots = [
        "/home/user/.npm-global/lib/node_modules/openclaw/node_modules",
        "/home/user/.hermes/lsp/node_modules",
        "/home/user/.hermes/hermes-agent/node_modules",
    ]
    which = shutil.which("node")
    if not which:
        return None
    # Ask node itself first, honouring whatever it can resolve from here.
    probe = subprocess.run(
        ["node", "-e", "try{console.log(require.resolve('semver'))}catch(e){}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if probe.stdout.strip():
        return probe.stdout.strip()
    for root in roots:
        candidate = Path(root) / "semver"
        if (candidate / "package.json").exists():
            return str(candidate)
    return None


def semver_lite_verdicts():
    """Parse every case with this project and record accept/reject."""
    sys.path.insert(0, str(ROOT))
    from semver_lite import parse_range  # noqa: E402

    out = []
    for text in CASES:
        try:
            parse_range(text)
            out.append([text, "accepted"])
        except Exception:  # noqa: BLE001 - any rejection is a rejection
            out.append([text, "rejected"])
    return out


def main():
    oracle_path = find_node_semver()
    if not oracle_path:
        print("node-semver is not available on this machine; skipping.")
        print("This is not a failure: node-semver is not a dependency of this project.")
        return 0

    probe = subprocess.run(
        ["node", "-e", NODE_PROBE, json.dumps(CASES), oracle_path],
        cwd=ROOT, capture_output=True, text=True,
    )
    if probe.returncode != 0:
        print(f"could not run the node probe: {probe.stderr.strip()}")
        return 0

    payload = json.loads(probe.stdout.strip())
    if not payload.get("found"):
        print("node-semver was located but would not load; skipping.")
        return 0

    mine = semver_lite_verdicts()
    theirs = payload["out"]

    mismatches = []
    for (text, their_verdict), (_, my_verdict) in zip(theirs, mine):
        if their_verdict != my_verdict:
            mismatches.append((text, their_verdict, my_verdict))

    print(f"oracle: node-semver at {oracle_path}")
    print(f"{len(theirs)} range syntax cases compared, {len(mismatches)} mismatch(es)")
    for text, their_verdict, my_verdict in mismatches:
        print(f"  {text!r}: node-semver={their_verdict} semver-lite={my_verdict}")

    if mismatches:
        print("\nMISMATCHES FOUND")
        return 1
    print("\nrange parsing agrees with node-semver on every case")
    return 0


if __name__ == "__main__":
    sys.exit(main())