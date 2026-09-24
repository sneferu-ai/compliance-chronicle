"""Command-line interface for The Compliance Chronicle.

Usage::

    python3 -m compliance_chronicle assemble --report R.json --curation C.json --out issue.json
    python3 -m compliance_chronicle validate issue.json
    python3 -m compliance_chronicle render-email issue.json --out-dir out/
    python3 -m compliance_chronicle render-pdf issue.json --out issue.pdf
    python3 -m compliance_chronicle archive --issues issue1.json issue2.json --out-dir archive/
    python3 -m compliance_chronicle build-sample --out-dir sample_issue/

Exit codes: 0 success; 1 hard gate failure on validate/assemble;
2 usage or input error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List

from . import assemble, gates, render_email, render_pdf
from .models import Issue


def _print_gates(results) -> None:
    for result in results:
        mark = "PASS" if result.passed else ("FAIL" if result.severity == "fail" else "WARN")
        print(f"[{mark}] {result.gate_id}: {result.message}")


def _cmd_assemble(args: argparse.Namespace) -> int:
    try:
        report = assemble.load_json(args.report)
        curation = assemble.load_json(args.curation)
        issue = assemble.assemble_issue(report, curation)
    except (assemble.AssemblyError, ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"assemble: {exc}", file=sys.stderr)
        return 2
    results = gates.validate_issue(issue)
    _print_gates(results)
    if not gates.is_shippable(results) and not args.force:
        print(
            "assemble: issue failed one or more hard gates; not writing output "
            "(re-run with --force to write it anyway for inspection)",
            file=sys.stderr,
        )
        return 1
    assemble.save_issue(issue, args.out)
    print(f"wrote {args.out}")
    return 0 if gates.is_shippable(results) else 1


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        issue = assemble.load_issue(args.issue)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"validate: {exc}", file=sys.stderr)
        return 2
    results = gates.validate_issue(issue)
    _print_gates(results)
    shippable = gates.is_shippable(results)
    print("SHIPPABLE" if shippable else "NOT SHIPPABLE")
    return 0 if shippable else 1


def _cmd_render_email(args: argparse.Namespace) -> int:
    try:
        issue = assemble.load_issue(args.issue)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"render-email: {exc}", file=sys.stderr)
        return 2
    os.makedirs(args.out_dir, exist_ok=True)
    base = os.path.join(args.out_dir, issue.slug())
    with open(base + ".txt", "w", encoding="utf-8") as handle:
        handle.write(render_email.render_plain(issue))
    with open(base + ".html", "w", encoding="utf-8") as handle:
        handle.write(render_email.render_html(issue))
    minutes = render_email.read_minutes(render_email.render_plain(issue))
    print(f"wrote {base}.txt and {base}.html (est. read time {minutes:.1f} min)")
    return 0


def _cmd_render_pdf(args: argparse.Namespace) -> int:
    try:
        issue = assemble.load_issue(args.issue)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"render-pdf: {exc}", file=sys.stderr)
        return 2
    render_pdf.render_issue_pdf(issue, args.out)
    print(f"wrote {args.out}")
    return 0


def _cmd_archive(args: argparse.Namespace) -> int:
    issues: List[Issue] = []
    for path in args.issues:
        try:
            issues.append(assemble.load_issue(path))
        except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
            print(f"archive: {path}: {exc}", file=sys.stderr)
            return 2
    index = render_pdf.build_archive(issues, args.out_dir)
    print(f"wrote archive of {len(issues)} issue(s); index at {index}")
    return 0


def _cmd_build_sample(args: argparse.Namespace) -> int:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    report_path = os.path.join(here, "samples", "sample_research_report.json")
    curation_path = os.path.join(here, "samples", "sample_curation.json")
    quiet_report_path = os.path.join(here, "samples", "sample_quiet_report.json")
    quiet_curation_path = os.path.join(here, "samples", "sample_quiet_curation.json")

    os.makedirs(args.out_dir, exist_ok=True)
    report = assemble.load_json(report_path)
    curation = assemble.load_json(curation_path)
    issue = assemble.assemble_issue(report, curation)
    results = gates.validate_issue(issue)
    _print_gates(results)
    if not gates.is_shippable(results):
        print("build-sample: the shipped sample must pass its own gates; refusing", file=sys.stderr)
        return 1

    assemble.save_issue(issue, os.path.join(args.out_dir, issue.slug() + ".json"))
    with open(os.path.join(args.out_dir, issue.slug() + ".txt"), "w", encoding="utf-8") as handle:
        handle.write(render_email.render_plain(issue))
    with open(os.path.join(args.out_dir, issue.slug() + ".html"), "w", encoding="utf-8") as handle:
        handle.write(render_email.render_html(issue))

    issues = [issue]
    if os.path.exists(quiet_report_path) and os.path.exists(quiet_curation_path):
        quiet = assemble.assemble_issue(
            assemble.load_json(quiet_report_path), assemble.load_json(quiet_curation_path)
        )
        quiet_results = gates.validate_issue(quiet)
        if gates.is_shippable(quiet_results):
            assemble.save_issue(quiet, os.path.join(args.out_dir, quiet.slug() + ".json"))
            issues.append(quiet)
        else:
            print("build-sample: quiet-month sample failed gates; skipped", file=sys.stderr)
            _print_gates(quiet_results)

    index = render_pdf.build_archive(issues, os.path.join(args.out_dir, "archive"))
    print(f"sample issue artifacts written to {args.out_dir}; archive index at {index}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compliance_chronicle",
        description="Assemble, validate, and render The Compliance Chronicle monthly issues.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("assemble", help="assemble an issue from a research report + curation")
    p.add_argument("--report", required=True)
    p.add_argument("--curation", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--force", action="store_true", help="write output even if hard gates fail")
    p.set_defaults(func=_cmd_assemble)

    p = sub.add_parser("validate", help="run the publish gates against an assembled issue")
    p.add_argument("issue")
    p.set_defaults(func=_cmd_validate)

    p = sub.add_parser("render-email", help="render plain-text and HTML email bodies")
    p.add_argument("issue")
    p.add_argument("--out-dir", required=True)
    p.set_defaults(func=_cmd_render_email)

    p = sub.add_parser("render-pdf", help="render a text-selectable PDF of one issue")
    p.add_argument("issue")
    p.add_argument("--out", required=True)
    p.set_defaults(func=_cmd_render_pdf)

    p = sub.add_parser("archive", help="build the PDF archive + index from issue JSON files")
    p.add_argument("--issues", nargs="+", required=True)
    p.add_argument("--out-dir", required=True)
    p.set_defaults(func=_cmd_archive)

    p = sub.add_parser("build-sample", help="build the sample issue artifacts from samples/")
    p.add_argument("--out-dir", required=True)
    p.set_defaults(func=_cmd_build_sample)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
