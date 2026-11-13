"""
data-quality-validator
======================
A small command-line tool that scans a CSV file for common data-quality
problems and prints (and optionally saves) a readable report.

Checks performed
----------------
1. Missing values        (empty cells, blank strings)
2. Duplicate rows        (whole row, or only on chosen key columns)
3. Negative values       (any numeric column)
4. Constant columns      (a column with only one distinct value)
5. Unusual values        (statistical outliers using the IQR rule)
6. Custom range rules    (e.g. age must be between 0 and 120)

Exit codes: 0 = no issues, 1 = issues found, 2 = error (bad file/arguments).

Usage examples
--------------
    python validator.py sample_data.csv
    python validator.py sample_data.csv --key id --range age:0:120
    python validator.py sample_data.csv --output report.md
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

EXIT_OK, EXIT_ISSUES, EXIT_ERROR = 0, 1, 2


# ----------------------------------------------------------------------
# Data structure
# ----------------------------------------------------------------------
@dataclass
class Finding:
    """One problem found by a check."""
    check: str    # e.g. "Missing values"
    column: str   # column name, or "(rows)" for row-level problems
    count: int    # how many cells/rows are affected
    detail: str   # human-readable explanation


# ----------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------
def load_data(path: str) -> pd.DataFrame:
    """Read a CSV file and treat blank/whitespace-only cells as missing.

    Raises:
        ValueError: if the file is missing, unreadable, or has no data.
    """
    file = Path(path)
    if not file.is_file():
        raise ValueError(f"File not found: {path}")
    try:
        df = pd.read_csv(file, skipinitialspace=True)
    except pd.errors.EmptyDataError:
        raise ValueError("The file is empty.") from None
    except (pd.errors.ParserError, UnicodeDecodeError) as err:
        raise ValueError(f"Could not read the file as CSV: {err}") from err

    # A cell containing only spaces is really "missing".
    df = df.replace(r"^\s*$", pd.NA, regex=True)
    if df.empty:
        raise ValueError("The file has headers but no data rows.")
    return df


def numeric_columns(df: pd.DataFrame) -> list[str]:
    """Names of numeric columns (booleans are not treated as numbers)."""
    return list(df.select_dtypes(include="number").columns)


# ----------------------------------------------------------------------
# Checks - each takes a DataFrame and returns a list of Finding objects
# ----------------------------------------------------------------------
def check_missing(df: pd.DataFrame) -> list[Finding]:
    """Report columns that contain missing values."""
    findings = []
    for col, n in df.isna().sum().items():
        if n > 0:
            pct = n / len(df) * 100
            findings.append(Finding("Missing values", col, int(n),
                                    f"{n} of {len(df)} rows empty ({pct:.1f}%)"))
    return findings


def check_duplicates(df: pd.DataFrame, subset: list[str] | None = None) -> list[Finding]:
    """Report repeated rows (extra copies after the first one).

    subset: only compare these columns (e.g. ["id"]); None compares all.
    """
    if subset:
        missing = [c for c in subset if c not in df.columns]
        if missing:
            raise ValueError(f"Unknown key column(s): {', '.join(missing)}")
    dup_mask = df.duplicated(subset=subset, keep="first")
    n = int(dup_mask.sum())
    if n == 0:
        return []
    rows = [str(i + 2) for i in df.index[dup_mask]]  # +2: header + 1-based
    scope = f"on {', '.join(subset)}" if subset else "across all columns"
    return [Finding("Duplicate rows", "(rows)", n,
                    f"{n} duplicate row(s) {scope}; CSV line(s): {', '.join(rows)}")]


def check_negative(df: pd.DataFrame) -> list[Finding]:
    """Report numeric columns that contain values below zero."""
    findings = []
    for col in numeric_columns(df):
        n = int((df[col] < 0).sum())
        if n > 0:
            findings.append(Finding("Negative values", col, n,
                                    f"{n} negative value(s), lowest is {df[col].min()}"))
    return findings


def check_constant(df: pd.DataFrame) -> list[Finding]:
    """Report columns where every non-missing value is identical."""
    findings = []
    if len(df) < 2:
        return findings
    for col in df.columns:
        non_null = df[col].dropna()
        if len(non_null) > 0 and non_null.nunique() == 1:
            findings.append(Finding("Constant column", col, len(non_null),
                                    f"every value is '{non_null.iloc[0]}'"))
    return findings


def check_outliers(df: pd.DataFrame, multiplier: float = 1.5) -> list[Finding]:
    """Flag unusual values with the IQR rule.

    A value is an outlier if it is below Q1 - k*IQR or above Q3 + k*IQR,
    where Q1/Q3 are the 25th/75th percentiles and k is `multiplier`.
    Columns with fewer than 4 values or IQR of 0 are skipped.
    """
    findings = []
    for col in numeric_columns(df):
        values = df[col].dropna()
        if len(values) < 4:
            continue
        q1, q3 = values.quantile(0.25), values.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        low, high = q1 - multiplier * iqr, q3 + multiplier * iqr
        odd = values[(values < low) | (values > high)]
        if len(odd) > 0:
            shown = ", ".join(str(v) for v in odd.head(5))
            findings.append(Finding(
                "Unusual values (IQR)", col, len(odd),
                f"{len(odd)} value(s) outside [{low:.2f}, {high:.2f}]: {shown}"))
    return findings


def parse_range_rule(text: str) -> tuple[str, float | None, float | None]:
    """Turn 'age:0:120' into ('age', 0.0, 120.0). Use 'score:0:' for no max."""
    parts = text.split(":")
    if len(parts) != 3 or not parts[0]:
        raise ValueError(f"Bad range rule '{text}'. Use column:min:max, e.g. age:0:120")
    try:
        low = float(parts[1]) if parts[1] else None
        high = float(parts[2]) if parts[2] else None
    except ValueError:
        raise ValueError(f"Min and max in '{text}' must be numbers.") from None
    return parts[0], low, high


def check_ranges(df: pd.DataFrame, rules: list[str]) -> list[Finding]:
    """Check user-defined rules such as 'age:0:120'."""
    findings = []
    for rule in rules:
        col, low, high = parse_range_rule(rule)
        if col not in df.columns:
            raise ValueError(f"Range rule refers to unknown column '{col}'.")
        values = pd.to_numeric(df[col], errors="coerce")
        bad = pd.Series(False, index=df.index)
        if low is not None:
            bad |= values < low
        if high is not None:
            bad |= values > high
        n = int(bad.sum())
        if n > 0:
            shown = ", ".join(str(v) for v in values[bad].head(5))
            findings.append(Finding(
                "Out of allowed range", col, n,
                f"{n} value(s) outside [{low if low is not None else '-inf'}, "
                f"{high if high is not None else '+inf'}]: {shown}"))
    return findings


def run_all_checks(df: pd.DataFrame, key: list[str] | None = None,
                   range_rules: list[str] | None = None,
                   iqr_multiplier: float = 1.5) -> list[Finding]:
    """Run every check and return all findings in one list."""
    findings: list[Finding] = []
    findings += check_missing(df)
    findings += check_duplicates(df, key)
    findings += check_negative(df)
    findings += check_constant(df)
    findings += check_outliers(df, iqr_multiplier)
    findings += check_ranges(df, range_rules or [])
    return findings


# ----------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------
def build_report(df: pd.DataFrame, findings: list[Finding],
                 source: str, markdown: bool = False) -> str:
    """Create the report as plain text or Markdown."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    h1 = (lambda t: f"# {t}") if markdown else (lambda t: f"{t}\n{'=' * len(t)}")
    h2 = (lambda t: f"\n## {t}\n") if markdown else (lambda t: f"\n{t}\n{'-' * len(t)}")
    bullet = "- " if markdown else "  * "

    lines = [h1("Data Quality Report"), "",
             f"File:      {source}", f"Generated: {stamp}",
             f"Rows:      {len(df)}", f"Columns:   {len(df.columns)} "
             f"({', '.join(df.columns)})",
             f"Issues:    {len(findings)}"]
    if markdown:  # Markdown needs two trailing spaces / blank lines to break lines
        lines = [l + "  " if l else l for l in lines]

    if not findings:
        lines += ["", "PASS: no issues found."]
        return "\n".join(lines) + "\n"

    lines += ["", "RESULT: issues found."]
    checks_in_order = list(dict.fromkeys(f.check for f in findings))
    for check in checks_in_order:
        lines.append(h2(check))
        for f in (x for x in findings if x.check == check):
            lines.append(f"{bullet}{f.column}: {f.detail}")
    return "\n".join(lines) + "\n"


def save_report(report: str, path: str) -> None:
    """Write the report to disk (must end in .txt or .md)."""
    if Path(path).suffix.lower() not in (".txt", ".md"):
        raise ValueError("Output file must end in .txt or .md")
    try:
        Path(path).write_text(report, encoding="utf-8")
    except OSError as err:
        raise ValueError(f"Could not write report: {err}") from err


# ----------------------------------------------------------------------
# Command line
# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Validate a CSV file for common data-quality problems.")
    p.add_argument("csv_file", help="path to the CSV file to check")
    p.add_argument("-o", "--output", metavar="FILE",
                   help="save the report to FILE (.txt or .md)")
    p.add_argument("-k", "--key", nargs="+", metavar="COLUMN",
                   help="check duplicates on these columns only (e.g. id)")
    p.add_argument("-r", "--range", action="append", default=[], metavar="RULE",
                   help="allowed range as column:min:max (repeatable), e.g. age:0:120")
    p.add_argument("--iqr", type=float, default=1.5, metavar="K",
                   help="outlier sensitivity; smaller = stricter (default 1.5)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        df = load_data(args.csv_file)
        findings = run_all_checks(df, args.key, args.range, args.iqr)
        markdown = bool(args.output) and Path(args.output).suffix.lower() == ".md"
        report = build_report(df, findings, args.csv_file, markdown=False)
        print(report)
        if args.output:
            save_report(build_report(df, findings, args.csv_file, markdown), args.output)
            print(f"Report saved to {args.output}")
    except ValueError as err:
        print(f"Error: {err}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_ISSUES if findings else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
