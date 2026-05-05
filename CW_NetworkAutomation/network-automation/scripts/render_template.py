#!/usr/bin/env python3
"""Render a Jinja2 device-config template against a YAML inventory.

Usage:
    render_template.py --template <template.j2> --inventory <inventory.yml> [--host <name>] [--out <dir>]

Inventory format:
    hosts:
      sw-access-01:
        hostname: sw-access-01
        mgmt_ip: 10.10.10.11
        ...
      sw-access-02:
        hostname: sw-access-02
        ...

If --host is given, render only that host. Otherwise render all hosts.
Output goes to stdout if --out is omitted, else one file per host in <out>/<hostname>.cfg.

Why this exists: when you're standing up 30 access switches with the same template
but per-host VLAN/IP differences, hand-editing each is the wrong tool. This is the
right tool. Use it for any "same config, varying parameters" scenario.

Requires: jinja2, pyyaml
"""

import argparse
import sys
from pathlib import Path

try:
    import yaml
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError as exc:
    print(
        f"Missing dependency: {exc.name}. Install with: pip install jinja2 pyyaml",
        file=sys.stderr,
    )
    sys.exit(1)


def render_one(template_path: Path, host_vars: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )
    template = env.get_template(template_path.name)
    return template.render(**host_vars)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--template", required=True, type=Path, help="Path to .j2 template")
    parser.add_argument("--inventory", required=True, type=Path, help="Path to inventory YAML")
    parser.add_argument("--host", help="Render only this host (default: all hosts)")
    parser.add_argument("--out", type=Path, help="Output directory (default: stdout)")
    args = parser.parse_args()

    if not args.template.is_file():
        print(f"Template not found: {args.template}", file=sys.stderr)
        return 1
    if not args.inventory.is_file():
        print(f"Inventory not found: {args.inventory}", file=sys.stderr)
        return 1

    with args.inventory.open() as f:
        inventory = yaml.safe_load(f)

    hosts = inventory.get("hosts", {})
    if not hosts:
        print("Inventory has no 'hosts' section", file=sys.stderr)
        return 1

    if args.host:
        if args.host not in hosts:
            print(f"Host '{args.host}' not in inventory. Available: {', '.join(hosts)}", file=sys.stderr)
            return 1
        targets = {args.host: hosts[args.host]}
    else:
        targets = hosts

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    for hostname, host_vars in targets.items():
        try:
            output = render_one(args.template, host_vars)
        except Exception as exc:
            print(f"[{hostname}] render failed: {exc}", file=sys.stderr)
            return 2

        if args.out:
            out_path = args.out / f"{hostname}.cfg"
            out_path.write_text(output)
            print(f"[{hostname}] wrote {out_path}")
        else:
            print(f"# ===== {hostname} =====")
            print(output)
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
