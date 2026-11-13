# Data Quality Validator

A command-line tool, written in Python and pandas, that scans a CSV file for common
data-quality problems and produces a clear report. Built as a small, testable project
to show practical data-validation skills relevant to data quality and AI-evaluation work,
where checking datasets before they are used matters.

## Features

|Check|What it finds|
|-|-|
|Missing values|Empty cells and whitespace-only cells, per column, with percentages|
|Duplicate rows|Repeated rows across all columns, or on chosen key columns (e.g. `id`)|
|Negative values|Values below zero in any numeric column|
|Constant columns|Columns where every value is identical (usually no information)|
|Unusual values|Statistical outliers using the IQR rule (sensitivity adjustable)|
|Custom range rules|Your own limits, e.g. `age` must be between 0 and 120|

Also included:

* Readable report in the terminal, optionally saved as `.txt` or `.md`
* Clear error messages for missing files, empty files and bad arguments
* Exit codes for scripting: `0` clean, `1` issues found, `2` error
* Unit tests (17) using Python's built-in `unittest`

## Installation

```bash
git clone https://github.com/<your-username>/data-quality-validator.git
cd data-quality-validator
pip install -r requirements.txt
```

Requires Python 3.9+ and pandas 2.0+.

## Usage

```bash
# Basic check
python validator.py sample\_data.csv

# Check duplicates by id, and enforce an age range
python validator.py sample\_data.csv --key id --range age:0:120

# Several range rules, stricter outlier detection, save as Markdown
python validator.py sample\_data.csv -r age:0:120 -r score:0:100 --iqr 1.0 -o report.md
```

|Option|Meaning|
|-|-|
|`csv\_file`|Path to the CSV file|
|`-o`, `--output FILE`|Save the report (`.txt` or `.md`)|
|`-k`, `--key COLUMN \[...]`|Detect duplicates using only these columns|
|`-r`, `--range RULE`|Allowed range as `column:min:max` (repeatable). Leave a side empty for no limit, e.g. `score:0:`|
|`--iqr K`|Outlier sensitivity, default `1.5` (smaller = stricter)|

## Example output

Running `python validator.py sample\_data.csv --key id --range age:0:120` on the included sample file:

```text
Data Quality Report
===================

File:      sample\_data.csv
Rows:      16
Columns:   8 (id, name, age, salary, score, department, country, signup\_date)
Issues:    11

RESULT: issues found.

Missing values
--------------
  \* age: 1 of 16 rows empty (6.2%)
  \* score: 1 of 16 rows empty (6.2%)
  \* signup\_date: 1 of 16 rows empty (6.2%)

Duplicate rows
--------------
  \* (rows): 1 duplicate row(s) on id; CSV line(s): 12

Negative values
---------------
  \* salary: 1 negative value(s), lowest is -48000
  \* score: 1 negative value(s), lowest is -5.0

Constant column
---------------
  \* country: every value is 'Nigeria'

Unusual values (IQR)
--------------------
  \* age: 1 value(s) outside \[19.25, 53.25]: 430.0
  \* salary: 2 value(s) outside \[38875.00, 77875.00]: -48000, 2500000
  \* score: 1 value(s) outside \[75.38, 98.38]: -5.0

Out of allowed range
--------------------
  \* age: 1 value(s) outside \[0.0, 120.0]: 430.0
```

(The real report also includes a "Generated" timestamp line.)

## How the checks work

* **Missing values:** blank and whitespace-only cells are converted to missing on load, then counted per column.
* **Outliers (IQR rule):** a value is flagged if it is below `Q1 - k \* IQR` or above `Q3 + k \* IQR`, where Q1 and Q3 are the 25th and 75th percentiles and `k` is `--iqr`. Columns with fewer than 4 values, or an IQR of 0, are skipped.
* **Duplicates:** the first occurrence is kept; only the extra copies are reported, with their CSV line numbers (line 1 is the header).

## Project structure

```text
data-quality-validator/
├── validator.py          # the tool: checks, report builder, CLI
├── sample\_data.csv       # deliberately messy example data
├── requirements.txt
├── tests/
│   └── test\_validator.py # 17 unit tests
├── LICENSE
└── README.md
```

## Running the tests

```bash
python -m unittest discover -s tests -v
```

## Extending it

Each check is a function that takes a DataFrame and returns a list of `Finding` objects.
To add a check, write a new `check\_...` function and call it in `run\_all\_checks()`.

## Limitations

* Only reads CSV files and loads the whole file into memory.
* Range rules and outlier detection apply to numeric columns only.
* Outlier detection assumes no particular distribution but can flag valid extreme values on small or skewed data, so treat flagged values as things to review, not automatic errors.

## Possible next steps

* Date-format and data-type consistency checks
* Excel and JSON input
* JSON output for use in pipelines
* Configurable rules from a YAML file



\## License



MIT, see \[LICENSE](LICENSE).

