import os
import re
import pandas as pd
import pdfplumber

# PDF 파일 목록과 연도·성별 매핑
FILES_META = [
    ("2015에버리지랭킹.pdf", 2015, "남자"), # 필요시 페이지별 성별 분리
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

def clean_num(val):
    if val is None:
        return ""
    return str(val).replace(",", "").strip()

rows = []

for filename, year, gender in FILES_META:
    if not os.path.exists(filename):
        continue
    with pdfplumber.open(filename) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    cells = [c.replace("\n", " ").strip() if c else "" for c in row]
                    # 첫 번째 셀이 순위(숫자)인 데이터 행만 필터링
                    if not cells or not re.match(r"^\d+$", cells[0]):
                        continue
                    
                    rank = int(cells[0])
                    # 시드 여부('S')가 별도 열에 있는 과거 양식 보정
                    offset = 1 if cells[1] in ("S", "s") else 0
                    # 이름(개인정보) 및 팀명 제외, 라이선스 번호만 추출
                    license_no = cells[2 + offset]
                    
                    # 우측 끝 4개 열: 대회출전횟수, 합계 게임수, 합계 PINFALL, 합계 AVG
                    tail = [c for c in cells[-4:]]
                    if len(tail) == 4:
                        tournaments = clean_num(tail[0])
                        games = clean_num(tail[1])
                        pinfall = clean_num(tail[2])
                        avg = clean_num(tail[3])
                        
                        rows.append({
                            "year": year,
                            "gender": gender,
                            "rank": rank,
                            "license": license_no,
                            "tournaments": tournaments,
                            "games": games,
                            "pinfall": pinfall,
                            "avg": avg
                        })

os.makedirs("data", exist_ok=True)
df = pd.DataFrame(rows)
df.to_csv("data/bowling_avg.csv", index=False, encoding="utf-8-sig")
print(f"저장 완료: 총 {len(df)}행 -> data/bowling_avg.csv")
