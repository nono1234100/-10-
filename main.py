import math
import re
from pathlib import Path
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from pypdf import PdfReader

st.set_page_config(page_title="KPBA 볼링 에버리지 추이 분석", page_icon="🎳", layout="wide")


@st.cache_data
def load_all_pdfs() -> pd.DataFrame:
    base_dir = Path(__file__).resolve().parent
    pdf_files = list(base_dir.rglob("*.pdf"))
    records = []

    for p in pdf_files:
        filename = p.name
        reader = PdfReader(p)
        full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

        # 파일명 또는 본문 첫 페이지에서 성별 판별 ('기타' 방지)
        header_text = filename + " " + (reader.pages[0].extract_text() or "")[:300]
        if "여자" in header_text:
            gender = "여자"
        elif "남자" in header_text:
            gender = "남자"
        else:
            gender = "기타"

        # 1. 본문에서 2010~2029년 연도 추출
        year_match = re.search(r"(20[12]\d)\s*년", full_text)
        if year_match:
            year = int(year_match.group(1))
        else:
            # 2. 파일명에서 연도 추출
            full_year_match = re.search(r"(20[12]\d)", filename)
            if full_year_match:
                year = int(full_year_match.group(1))
            else:
                code_match = re.search(r"(\d{2})1105", filename)
                if code_match:
                    yy = int(code_match.group(1))
                    year = 2000 + yy if yy >= 26 else 2000 + yy - 1
                else:
                    year = None

        if not year:
            continue

        # 3. 모든 연도 양식을 포괄하는 유연한 데이터 추출
        for line in full_text.splitlines():
            line = line.strip()
            if not re.match(r"^\d+\s+", line):
                continue

            tokens = line.split()
            if len(tokens) >= 6:
                try:
                    tournaments = int(tokens[-4].replace(",", ""))
                    games = int(tokens[-3].replace(",", ""))
                    total_pins = int(tokens[-2].replace(",", ""))
                    avg = float(tokens[-1].replace(",", ""))

                    if 100.0 <= avg <= 300.0 and tournaments > 0 and games > 0:
                        calc_avg = total_pins / games
                        if abs(calc_avg - avg) <= 0.1:
                            records.append({
                                "year": year,
                                "성별": gender,
                                "참가대회수": tournaments,
                                "총게임수": games,
                                "총핀": total_pins,
                                "에버리지": avg,
                            })
                except ValueError:
                    continue

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.drop_duplicates(subset=["year", "성별", "총게임수", "총핀"])
    return df


st.title("🎳 KPBA 프로볼링 에버리지 추이 분석")
st.caption("개인정보(선수명·팀명) 비식별화 처리 | 대회 70% 이상 참가 선수 기준")

df = load_all_pdfs()

if df.empty:
    st.warning("GitHub의 `data` 폴더에 PDF 파일이 아직 없습니다. `data` 폴더에 22개 PDF 파일을 올려주세요.")
    st.stop()

# 대회 70% 이상 참가자 필터 적용
max_t = df.groupby(["year", "성별"])["참가대회수"].transform("max")
min_req = (max_t * 0.7).apply(math.ceil)
df = df[df["참가대회수"] >= min_req].copy()
st.sidebar.success("✅ 대회 70% 이상 참가자 필터 적용됨")

# 사이드바: 성별 필터 ('기타' 제외하고 표시)
valid_genders = [g for g in sorted(df["성별"].dropna().unique().tolist()) if g != "기타"]
genders = ["전체"] + valid_genders
sel_gender = st.sidebar.radio("성별 구분", genders)
if sel_gender != "전체":
    df = df[df["성별"] == sel_gender]

# 연도별 전체 통계 집계
yearly = (
    df.groupby("year", as_index=False)["에버리지"]
    .agg(전체평균="mean", 중앙값="median", 최고="max", 최저="min", 인원수="count")
    .sort_values("year")
)
yearly["연도"] = yearly["year"].astype(str) + "년"
yearly["평균라벨"] = yearly["전체평균"].map(lambda v: f"{v:.2f}")

# 선형 회귀 분석
x = yearly["year"].to_numpy(dtype=float)
y = yearly["전체평균"].to_numpy(dtype=float)

if len(x) >= 2:
    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept
    mae_model = float(np.mean(np.abs(y - y_pred)))
    mae_baseline = float(np.mean(np.abs(y - np.mean(y))))
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
else:
    slope, r2, mae_model, mae_baseline = 0.0, 0.0, 0.0, 0.0

# 핵심 지표 출력
c1, c2, c3, c4 = st.columns(4)
c1.metric("분석 기간", f"{int(x.min())} ~ {int(x.max())}년", f"총 {len(df):,}건")
c2.metric("연평균 변화량 (기울기)", f"{slope:+.3f} 점/년")
c3.metric("회귀 모델 설명력 (R²)", f"{r2:.3f}")
c4.metric("예측 오차 (MAE)", f"{mae_model:.2f}점", f"기준모델 대비 {mae_model - mae_baseline:+.2f}점")

st.divider()

# 상단: Y축 확대 + 점수 라벨이 적용된 연도별 평균 에버리지 추이 그래프
col1, col2 = st.columns([3, 2])
with col1:
    st.subheader("📈 연도별 평균 에버리지 변화 추이 (확대 뷰)")

    y_min = math.floor(yearly["전체평균"].min() - 2)
    y_max = math.ceil(yearly["전체평균"].max() + 2)

    base = alt.Chart(yearly).encode(
        x=alt.X("연도:N", title="연도", axis=alt.Axis(labelAngle=0))
    )

    line = base.mark_line(
        color="#1f77b4",
        strokeWidth=3,
        point=alt.OverlayMarkDef(color="#1f77b4", size=90, filled=True)
    ).encode(
        y=alt.Y(
            "전체평균:Q",
            title="평균 에버리지",
            scale=alt.Scale(domain=[y_min, y_max], zero=False
