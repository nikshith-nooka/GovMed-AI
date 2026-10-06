#!/usr/bin/env python3
"""Check that every decimal number and percentage in the paper is backed by the rigor report.

Each number shown in paper/main.tex (body only: preamble and bibliography are skipped;
comments, \\cite, \\label, \\ref, \\href, \\url, graphics options and dimensions are ignored)
must equal some numeric leaf of results/rigor_report.json once that leaf is rounded to the
number's shown precision, either as-is or as a percentage (value * 100). Signs are ignored.

Add ``% numcheck:ignore`` to a line to whitelist it (e.g. decoding parameters, citations
of other work). Exits 1 if any number is unmatched.

    uv run python -m scripts.check_paper_numbers
    uv run python -m scripts.check_paper_numbers --integers   # also check integers >= 10
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

IGNORE_MARK = "numcheck:ignore"
BODY_START = re.compile(r"\\begin\{document\}")
BODY_END = re.compile(r"\\begin\{thebibliography\}|\\bibliography\{|\\printbibliography|\\end\{document\}")
COMMENT = re.compile(r"(?<!\\)%.*$")
# Commands whose arguments are identifiers or layout, not results.
STRIP = [
    re.compile(r"\\(?:cite[a-z]*|label|ref|eqref|autoref|cref|Cref|pageref|url|input|include|bibliographystyle)\*?"
               r"(?:\[[^\]]*\])?\{[^}]*\}"),
    re.compile(r"\\href\{[^}]*\}"),
    re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{[^}]*\}"),
    re.compile(r"\\(?:begin|end)\{[^}]*\}(?:\[[^\]]*\])?(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})?"),
    re.compile(r"\\(?:setlength|addtolength|fontsize|vspace|hspace|resizebox|scalebox|rule|arraystretch|"
               r"renewcommand|setcounter|multicolumn|multirow|columnwidth|linewidth|textwidth)\*?"
               r"(?:\{[^{}]*\})*"),
    re.compile(r"[-+]?\d*\.?\d+\s*(?:\\(?:linewidth|columnwidth|textwidth|textheight|baselineskip)|pt|em|ex|cm|mm|in)\b"),
    re.compile(r"doi:\s*\S+|10\.\d{4,}/\S+"),
    # Hyphenated identifiers such as model names ("Llama-3.2-11B", "gpt-oss-120b").
    re.compile(r"\b[A-Za-z][\w]*(?:-[\w.]*\d[\w.]*)+"),
]
NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d+)(\s*\\?%)?")


def body_lines(tex: str) -> Iterable[Tuple[int, str]]:
    lines = tex.splitlines()
    start = next((i + 1 for i, line in enumerate(lines) if BODY_START.search(line)), 0)
    for i in range(start, len(lines)):
        if BODY_END.search(lines[i]):
            break
        yield i + 1, lines[i]


def extract_numbers(line: str, integers: bool = False) -> List[Tuple[str, float, int, bool]]:
    """[(shown text, value, decimals, is_percent)] for the numbers to verify on one source line."""
    if IGNORE_MARK in line:
        return []
    text = COMMENT.sub("", line)
    for pattern in STRIP:
        text = pattern.sub(" ", text)
    found = []
    for m in NUMBER.finditer(text):
        raw, pct = m.group(1), bool(m.group(2))
        value = float(raw.replace(",", ""))
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        if not pct and decimals == 0:
            if not integers or value < 10 or 1900 <= value <= 2100:
                continue  # plain integers are counts, years, section numbers: opt-in only
        found.append((m.group(0).strip(), value, decimals, pct))
    return found


def numeric_leaves(obj: Any) -> List[float]:
    out: List[float] = []
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(numeric_leaves(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(numeric_leaves(v))
    return out


def matches(value: float, decimals: int, leaves: Iterable[float]) -> bool:
    tol = 0.5 * 10 ** -decimals + 1e-9
    target = abs(value)
    return any(abs(abs(leaf) - target) <= tol or abs(abs(leaf) * 100 - target) <= tol for leaf in leaves)


def check(tex: str, report: Any, integers: bool = False) -> List[Tuple[int, str, str]]:
    """Unmatched numbers as (line_no, shown, stripped line)."""
    leaves = sorted(set(numeric_leaves(report)))
    unmatched = []
    for no, line in body_lines(tex):
        for shown, value, decimals, _ in extract_numbers(line, integers):
            if not matches(value, decimals, leaves):
                unmatched.append((no, shown, line.strip()))
    return unmatched


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tex", default="paper/main.tex")
    parser.add_argument("--report", default="results/rigor_report.json,results/rigor_report_medqa.json",
                        help="Comma-separated report files; a number may come from any of them")
    parser.add_argument("--integers", action="store_true", help="Also check plain integers >= 10 (not years)")
    args = parser.parse_args(argv)

    tex = Path(args.tex).read_text(encoding="utf-8")
    paths = [p for p in args.report.split(",") if p and Path(p).exists()]
    report = {p: json.loads(Path(p).read_text(encoding="utf-8")) for p in paths}
    unmatched = check(tex, report, args.integers)
    total = sum(len(extract_numbers(line, args.integers)) for _, line in body_lines(tex))
    for no, shown, line in unmatched:
        context = line if len(line) <= 110 else line[:107] + "..."
        print(f"{args.tex}:{no}: {shown!r} not found in {args.report}\n    {context}")
    print(f"\n{total - len(unmatched)}/{total} numbers matched; {len(unmatched)} unmatched."
          + ("" if unmatched else " All paper numbers are backed by the report."))
    return 1 if unmatched else 0


if __name__ == "__main__":
    sys.exit(main())
