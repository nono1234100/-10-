import pypdf
import re
import os
import pandas as pd

files_meta = [
    ("2015에버리지랭킹.pdf", 2015, "auto"),
    ("에버리지 남자.pdf", 2016, "남자"),
    ("에버리지 여자.pdf", 2016, "여자"),
    ("에버리지 남자 (1).pdf", 2017, "남자"),
    ("에버리지 여자 (1).pdf", 2017, "여자"),
    ("에버리지 남자 (2).pdf", 2018, "남자"),
    ("에버리지 여자 (2).pdf", 2018, "여자"),
    ("에버리지 남자 (3).pdf", 2019, "남자"),
    ("에버리지 여자 (3).pdf", 2019, "여자"),
    ("[KPBA-2021] 에버리지 남자_211216.pdf", 2021, "남자"),
    ("[KPBA-2021] 에버리지 여자_211216.pdf", 2021, "여자"),
    ("KPBA 2022 에버리지 남자랭킹 221216.pdf", 2022, "남자"),
    ("KPBA 2022 에버리지 여자랭킹 221216.pdf", 2022, "여자"),
    ("KPBA 에버리지 랭킹 남자 240118.pdf", 2023, "남자"),
    ("KPBA 에버리지 랭킹 여자 240118.pdf", 2023, "여자"),
    ("KPBA 에버리지 랭킹 남자 241213.pdf", 2024, "남자"),
    ("KPBA 에버리지 랭킹 여자 241203.pdf", 2024, "여자"),
    ("KPBA 에버리지 랭킹 남자 260106.pdf", 2025, "남자"),
    ("KPBA 에버리지 랭킹 여자 251121.pdf", 2025, "여자"),
]

# Inspect the structure of lines in a few files to see how pypdf extracts rows
for fname in ["2015에버리지랭킹.pdf", "에버리지 남자.pdf", "[KPBA-2021] 에버리지 남자_211216.pdf", "KPBA 2022 에버리지 남자랭킹 221216.pdf", "KPBA 에버리지 랭킹 남자 241213.pdf"]:
    reader = pypdf.PdfReader(fname)
    print(f"=== {fname} (pages: {len(reader.pages)}) ===")
    for p_idx, page in enumerate(reader.pages):
        lines = page.extract_text().split('\n')
        print(f"  Page {p_idx+1}: {len(lines)} lines | sample: {lines[:4]}")
