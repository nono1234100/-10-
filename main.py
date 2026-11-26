import math
import re
from pathlib import Path
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
        gender = "여자" if "여자" in filename else ("남자" if "남자" in filename else "기타")
        reader = PdfReader(p)
        full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

        year_match = re.search(r"(202\d)년", full_text)
        if year_match:
            year = int(year_match.group(1))
        else:
            code_match = re.search(r"(\d{2})1105", filename)
            year = int(f"20{int(code_match.group(1)) - 1}") if code_match else None

        if not year:
            continue

        for line in full_text.splitlines():
            line = line.strip()
            match = re.match(r"^(\d+)\s+([가-힣a-zA-Z0-9\s]+?)\s+(F?\d+)\s+(.*)$", line)
            if match:
                rest_tokens = match.group(4).split()
                if len(rest_tokens) >= 4:
                    try:
                        tournaments = int(rest_tokens[-4])
                        games = int(rest_tokens[-3])
                        total_pins = int(rest_tokens[-2])
                        avg = float(rest_tokens[-1])

                        # 개인정보(선수명·등록번호·팀명)는 제외하고 수치 데이터만 추출
                        if 100.0 <= avg <= 300.0 and tournaments > 0:
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

    return pd.DataFrame(records)


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

# 사이드바: 성별 필터
genders = ["전체"] + sorted(df["성별"].dropna().unique().tolist())
sel_gender = st.sidebar.radio("성별 구분", genders)
if sel_gender != "전체":
    df = df[df["성별"] == sel_gender]

# 연도별 전체 통계 집계
yearly = (
    df.groupby("year", as_index=False)["에버리지"]
    .agg(전체평균="mean", 중앙값="median", 최고="max", 최저="min", 인원수="count")
    .sort_values("year")
)

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

# 상단: 모든 선수의 연도별 평균 에버리지 추이
col1, col2 = st.columns([3, 2])
with col1:
    st.subheader("📈 모든 선수의 연도별 평균 에버리지 추이")
    chart_df = yearly.assign(연도=yearly["year"].astype(str) + "년").set_index("연도")[["전체평균", "최고", "최저"]]
    st.line_chart(chart_df)

with col2:
    st.subheader("📊 연도별 요약 통계")
    st.dataframe(yearly.round(2), hide_index=True, use_container_width=True)

st.divider()

# 하단: 연도별 선수들의 에버리지 분포
st.subheader("🎯 연도별 선수들의 에버리지 분포 (비식별화)")
st.scatter_chart(
    data=df.assign(연도=df["year"].astype(str) + "년"),
    x="연도",
    y="에버리지",
    color="성별",
)

# 비식별화 데이터 미리보기 및 다운로드
with st.expander("📋 비식별화 데이터 미리보기 및 CSV 다운로드"):
    st.dataframe(df.sort_values(["year", "에버리지"], ascending=[True, False]), hide_index=True, use_container_width=True)
    st.download_button(
        "📥 정제된 CSV 다운로드 (개인정보 제외)",
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name="bowling_avg_filtered_clean.csv",
        mime="text/csv",
    )
