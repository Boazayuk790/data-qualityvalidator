# Data Quality Validator

A practical Python tool for checking the quality of CSV datasets.

It detects common data issues such as:
- Missing values
- Duplicate rows
- Unexpected data types
- Negative values in numeric columns
- Constant (single-value) columns
- Basic range problems

Designed for data quality checks and as a foundation for AI evaluation / data validation workflows.

## Features
- Clear and readable validation report
- Works with any CSV file
- Command-line support
- Lightweight (only requires pandas)
- Easy to extend

## Requirements
- Python 3.9+
- pandas

## Installation

```bash
git clone [https://github.com/Boazayuk790/data-quality-validator.git](https://github.com/Boazayuk790/data-quality-validator.git)
cd data-quality-validator
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

Usage
Basic usage (uses the sample file):
BASH
python validator.py
• Copy
Check your own CSV file:
BASH
python validator.py path/to/your/file.csv
• Copy
Example Output
• Copy
== Data Quality Report ===
File: sample_data.csv
Shape: 6 rows × 5 columns
Missing Values:
- name: 1 missing
- age: 1 missing
Duplicate rows: 1
Warnings:
- Column
'age' contains unusual values (max
= 150)
- Column
- Column
'score' contains negative values
'id' looks good
Validation finished.
•ll LTE 91)
Project Structure
Сору
data-quality-validator/ validator.py sample_data.cSv
requirements.txt
• gitignore
README.md
Future Improvements
• Support for Excel and JSON
• Configurable rules (required columns, allowed ranges)
• Export report to Markdown/HTML
• Simple Al text quality checks
• Unit tests
Author
Boaz Lawrence Ayuk
GitHub: Boazayuk790
