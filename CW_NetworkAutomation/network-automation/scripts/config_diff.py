#!/usr/bin/env python3
"""Diff two text-based device configs with awareness of indented blocks.

Usage:
    config_diff.py <pre.cfg> <post.cfg> [--context N]

Standard `diff -u` works on configs but doesn't show the parent context for an
indented line — so you see "+ switchport access vlan 50" without knowing which
interface it's under. This script keeps the most recent unindented line ("section
header") in view so changes are readable in context.

Use it for:
  * pre/post-change verification (was this the *only* delta?)
  * comparing today's backup vs yesterday's
  * diffing rendered candidate config against running config

Output is unified-diff format with a "in section: <header>" comment above each
hunk. No external dependencies; stdlib only.
"""

import argparse
import difflib
import sys
from pathlib import Path


def find_section_header(lines: list[str], idx: int) -> str | None:
    """Walk backwards from idx looking for the most recent unindented, non-empty line."""
    for i in range(idx, -1, -1):
        line = lines[i]
        if not line.strip():
            continue
        if line.startswith((" ", "\t")):
            continue
        if line.lstrip().startswith(("!", "#")):
            continue
        return line.rstrip()
    return None


def annotated_diff(pre_lines: list[str], post_lines: list[str], context: int) -> list[str]:
    diff = list(difflib.unified_diff(pre_lines, post_lines, fromfile="pre", tofile="post", n=context))
    if not diff:
        return ["# no differences"]

    out: list[str] = []
    last_section = None
    for line in diff:
        if line.startswith("@@"):
            # parse the post-file starting line, e.g. @@ -10,7 +12,9 @@
            parts = line.split()
            try:
                post_start = int(parts[2].split(",")[0].lstrip("+")) - 1
            except (IndexError, ValueError):
                post_start = 0
            section = find_section_header(post_lines, post_start)
            if section and section != last_section:
                out.append(f"# in section: {section}")
                last_section = section
        out.append(line.rstrip("\n"))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pre", type=Path, help="Pre-change config file")
    parser.add_argument("post", type=Path, help="Post-change config file")
    parser.add_argument("--context", type=int, default=2, help="Lines of context (default: 2)")
    args = parser.parse_args()

    if not args.pre.is_file():
        print(f"File not found: {args.pre}", file=sys.stderr)
        return 1
    if not args.post.is_file():
        print(f"File not found: {args.post}", file=sys.stderr)
        return 1

    pre_lines = args.pre.read_text(errors="replace").splitlines(keepends=False)
    post_lines = args.post.read_text(errors="replace").splitlines(keepends=False)

    for line in annotated_diff(pre_lines, post_lines, args.context):
        print(line)

    return 0


if __name__ == "__main__":
    sys.exit(main())
