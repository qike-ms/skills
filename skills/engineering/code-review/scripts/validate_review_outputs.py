#!/usr/bin/env python3
"""Fail closed unless every reviewer completed and emitted a valid verdict."""

import argparse
import json
from pathlib import Path
import re
import sys

VERDICTS = {"APPROVE", "APPROVE-WITH-CHANGES", "REJECT"}


def validate(name, status_path, output_path, required_verdict=None, require_json=False):
    errors = []
    try:
        status = json.loads(Path(status_path).read_text(encoding="utf-8"))
    except Exception:
        return [f"{name}: invalid status file"]
    if status.get("state") != "completed": errors.append(f"{name}: state is not completed")
    if status.get("returnCode") != 0: errors.append(f"{name}: return code is not zero")
    if status.get("cleanupSucceeded") is not True: errors.append(f"{name}: process cleanup was not verified")
    try:
        text = Path(output_path).read_text(encoding="utf-8")
    except Exception:
        return errors + [f"{name}: unreadable output"]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return errors + [f"{name}: empty output"]
    verdicts = [line for line in lines if line in VERDICTS]
    terminal = lines[-1] if lines[-1] in VERDICTS else None
    if len(verdicts) != 1 or terminal is None:
        errors.append(f"{name}: output must end with exactly one bare verdict token")
    if required_verdict and terminal != required_verdict:
        errors.append(f"{name}: required verdict was not returned")
    if require_json:
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        try:
            payload = json.loads(match.group(1)) if match else None
        except Exception:
            payload = None
        findings = payload.get("findings") if isinstance(payload, dict) else None
        if not isinstance(findings, list):
            errors.append(f"{name}: missing valid findings JSON object")
        else:
            required = {"severity", "confidence", "title", "location", "evidence", "impact", "fix"}
            for finding in findings:
                if not isinstance(finding, dict) or not required.issubset(finding):
                    errors.append(f"{name}: malformed finding object")
                    break
                if finding["severity"] not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
                    errors.append(f"{name}: invalid finding severity")
                    break
                if not isinstance(finding["confidence"], (int, float)) or finding["confidence"] < 80:
                    errors.append(f"{name}: invalid finding confidence")
                    break
            if terminal == "APPROVE" and findings:
                errors.append(f"{name}: approval cannot contain material findings")
        if isinstance(payload, dict) and payload.get("verdict") != terminal:
            errors.append(f"{name}: JSON and terminal verdicts differ")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", nargs=3, action="append", metavar=("NAME", "STATUS", "OUTPUT"), required=True)
    parser.add_argument("--require-verdict", choices=sorted(VERDICTS))
    parser.add_argument("--require-json-verdict", action="store_true")
    args = parser.parse_args()
    errors = [e for r in args.review for e in validate(*r, args.require_verdict, args.require_json_verdict)]
    for error in errors: print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
