#!/usr/bin/env python3
"""Audit P0.1 Debian-derived kernel config; do not alter security decisions."""
import argparse
import json
import pathlib
import sys

def read_config(path):
    values = {}
    for line in pathlib.Path(path).read_text(errors="replace").splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            k, v = line.split("=", 1)
            values[k] = v.strip('"')
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            k = line.removeprefix("# ").removesuffix(" is not set")
            values[k] = "n"
    return values

def audit(config, requirements):
    issues = []
    for severity in ("mandatory", "advisory"):
        for name, accepted in requirements[severity].items():
            value = config.get(name, "missing")
            ok = (value != "missing" if accepted == ["string"] else value in accepted)
            if not ok:
                issues.append((severity, name, value or "missing", ",".join(accepted)))
    return issues

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("config")
    p.add_argument("--requirements", default=str(pathlib.Path(__file__).resolve().parents[1] / "config/required-config.json"))
    args = p.parse_args()
    config = read_config(args.config)
    requirements = json.loads(pathlib.Path(args.requirements).read_text())
    issues = audit(config, requirements)
    for severity, name, value, wanted in issues:
        print(f"{severity.upper():9} {name}: {value} (expected {wanted})")
    errors = sum(s == "mandatory" for s, *_ in issues)
    print(f"Configuration audit: {len(config)} options read; {errors} mandatory failure(s), {len(issues)-errors} advisory warning(s)")
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
