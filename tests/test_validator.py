"""Unit tests. Run from the project folder with:  python -m unittest discover -s tests -v"""
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import validator as v


def frame(**cols):
    return pd.DataFrame(cols)


class TestChecks(unittest.TestCase):
    def test_missing_values_counted(self):
        df = frame(a=[1, None, 3], b=["x", "y", "z"])
        result = v.check_missing(df)
        self.assertEqual(len(result), 1)
        self.assertEqual((result[0].column, result[0].count), ("a", 1))

    def test_no_missing_values(self):
        self.assertEqual(v.check_missing(frame(a=[1, 2])), [])

    def test_duplicates_all_columns(self):
        df = frame(a=[1, 1, 2], b=["x", "x", "y"])
        self.assertEqual(v.check_duplicates(df)[0].count, 1)

    def test_duplicates_on_key_only(self):
        df = frame(id=[1, 1, 2], b=["x", "DIFFERENT", "y"])
        self.assertEqual(v.check_duplicates(df), [])           # rows differ
        self.assertEqual(v.check_duplicates(df, ["id"])[0].count, 1)

    def test_unknown_key_column_raises(self):
        with self.assertRaises(ValueError):
            v.check_duplicates(frame(a=[1]), ["nope"])

    def test_negative_values(self):
        result = v.check_negative(frame(a=[1, -2, -3], b=[1, 2, 3]))
        self.assertEqual([(f.column, f.count) for f in result], [("a", 2)])

    def test_constant_column(self):
        result = v.check_constant(frame(a=[5, 5, 5], b=[1, 2, 3]))
        self.assertEqual([f.column for f in result], ["a"])

    def test_outlier_detected(self):
        df = frame(a=[10, 11, 12, 10, 11, 12, 500])
        result = v.check_outliers(df)
        self.assertEqual(result[0].count, 1)

    def test_outlier_skips_tiny_columns(self):
        self.assertEqual(v.check_outliers(frame(a=[1, 2, 1000])), [])

    def test_range_rule(self):
        df = frame(age=[20, 30, 200, -1])
        self.assertEqual(v.check_ranges(df, ["age:0:120"])[0].count, 2)

    def test_range_rule_open_ended(self):
        df = frame(score=[1, 2, -5])
        self.assertEqual(v.check_ranges(df, ["score:0:"])[0].count, 1)

    def test_bad_range_rules_raise(self):
        for bad in ["age", "age:x:5", ":0:5"]:
            with self.assertRaises(ValueError):
                v.parse_range_rule(bad)
        with self.assertRaises(ValueError):
            v.check_ranges(frame(a=[1]), ["missing:0:5"])


class TestLoadingAndCli(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).parent / "_tmp"
        self.tmp.mkdir(exist_ok=True)

    def tearDown(self):
        for f in self.tmp.glob("*"):
            f.unlink()
        self.tmp.rmdir()

    def write(self, name, text):
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_missing_file(self):
        with self.assertRaises(ValueError):
            v.load_data("does_not_exist.csv")

    def test_empty_file(self):
        with self.assertRaises(ValueError):
            v.load_data(self.write("empty.csv", ""))

    def test_blank_strings_become_missing(self):
        df = v.load_data(self.write("blank.csv", "a,b\n1,  \n2,x\n"))
        self.assertEqual(int(df["b"].isna().sum()), 1)

    def test_exit_codes(self):
        clean = self.write("clean.csv", "a,b\n1,x\n2,y\n3,z\n")
        dirty = self.write("dirty.csv", "a,b\n1,x\n,y\n3,z\n")
        self.assertEqual(v.main([clean]), v.EXIT_OK)
        self.assertEqual(v.main([dirty]), v.EXIT_ISSUES)
        self.assertEqual(v.main(["nope.csv"]), v.EXIT_ERROR)

    def test_save_report_markdown_and_bad_extension(self):
        dirty = self.write("dirty.csv", "a,b\n1,x\n,y\n3,z\n")
        out = str(self.tmp / "r.md")
        v.main([dirty, "-o", out])
        self.assertTrue(Path(out).read_text(encoding="utf-8").startswith("# Data Quality Report"))
        self.assertEqual(v.main([dirty, "-o", str(self.tmp / "r.pdf")]), v.EXIT_ERROR)


if __name__ == "__main__":
    unittest.main()
