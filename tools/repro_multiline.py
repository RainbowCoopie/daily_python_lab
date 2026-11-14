import csv
import pathlib
import sys
import tempfile

sys.path.insert(0, r"C:\Users\25725\Documents\deepseek-harness\default-workspace\daily_python_lab\projects\2026-11-12__xlsafe")
from xlsafe import read_csv  # noqa: E402

tmp = pathlib.Path(tempfile.gettempdir()) / "ml_test.csv"
tmp.write_text('姓名,备注\n张三,"第一行\n第二行"\n', encoding="utf-8")

with open(tmp, newline="", encoding="utf-8") as fh:
    standard = list(csv.DictReader(fh))

print("标准 csv 读法  :", standard)
print("本项目 read_csv :", read_csv(tmp))
print("相等吗          :", standard == read_csv(tmp))
