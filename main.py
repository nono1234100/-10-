import math
import re
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
from pypdf import PdfReader

st.set_page_config(page_title="KPBA 볼링 에버리지 추이 분석", page_icon="🎳", layout="wide")

EXCLUDE_KEYWORDS = ["선수", "이름", "성명", "회원", "name", "player", "팀", "소속", "구단", "team", "club"]
YEAR_KEYWORDS = ["year", "연도", "년도", "시즌", "season", "날짜", "date"]


def parse_single_pdf(file_source, filename: str) -> list[dict]:
    records = []
    gender = "여자" if "여자" in filename else ("남자" if "남자" in filename else "기타")
    reader = PdfReader(file_source)
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    year_match = re.search(r"(202\d)년", full_text)
    if year_match:
        year = int(year_match.group(1))
    else:
        code_match = re.search(r"(\d{2})1105", filename)
        year = int(f"20{int(code_match.group(1)) - 1}") if code_match else None

    if not year:
        return records

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
    return records


def clean_csv_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.dropna(how="all").dropna(axis=1, how="all").copy()
    df.columns = [str(c).strip() for c in df.columns]

    # 개인정보(선수, 이름, 성명, 회원, 팀, 소속, 구단 등) 컬럼 자동 삭제
    drop_cols = [c for c in df.columns if any(k in c.lower() for k in EXCLUDE_KEYWORDS)]
    if drop_cols:
        df = df.drop(columns=drop_cols)

    for col in df.columns:
        if df[col].dtype == "object":
            s = df[col].astype(str).str.strip().str.replace(",", "", regex=False)
            num = pd.to_numeric(s, errors="coerce")
            df[col] = num if num.notna().mean() >= 0.6 else s

    y_col = next((c for c in df.columns if any(k in c.lower() for k in YEAR_KEYWORDS)), None)
    if y_col:
        extracted = df[y_col].astype(str).str.extract(r"(20\d{2}|19\d{2})", expand=False)
        df["year"] = pd.to_numeric(extracted, errors="coerce")
        if y_col != "year":
            df = df.drop(columns=[y_col])

    return df


def load_csv(source):
    for enc in ["utf-8-sig", "utf-8", "cp949", "euc-kr"]:
        try:
            if hasattr(source, "seek"):
                source.seek(0)
            df = pd.read_csv(source, encoding=enc)
            if not df.empty:
                return clean_csv_data(df)
        except Exception:
            continue
    return None


st.title("🎳 KPBA 프로볼링 에버리지 추이 분석")
st.caption("개인정보(선수명·팀명) 비식별화 처리 | 대회 70% 이상 참가 선수 기준")

# 1. 웹 화면에서 PDF(여러 개 가능) 또는 CSV 직접 업로드 받기
uploaded_files = st.file_uploader(
    "📂 22개 PDF 파일(또는 CSV 파일)을 한꺼번에 드래그해서 올려주세요",
    type=["pdf", "csv"],
    accept_multiple_files=True,
)

df = None

if uploaded_files:
    pdf_records = []
    for f in uploaded_files:
        if f.name.lower().endswith(".pdf"):
            pdf_records.extend(parse_single_pdf(f, f.name))
        elif f.name.lower().endswith(".csv"):
            df = load_csv(f)
    if pdf_records:
        df = pd.DataFrame(pdf_records)
else:
    # 업로드가 없으면 GitHub data 폴더 내 PDF 또는 CSV 자동 탐색
    base_dir = Path(__file__).resolve().parent
    pdf_files = list(base_dir.rglob("*.pdf"))
    if pdf_files:
        pdf_records = []
        for p in pdf_files:
            pdf_records.extend(parse_single_pdf(p, p.name))
        if pdf_records:
            df = pd.DataFrame(pdf_records)

    if df is None or df.empty:
        csv_paths = [base_dir / "data" / "bowling_avg.csv", Path("data/bowling_avg.csv"), Path("bowling_avg.csv")]
        df = next((load_csv(p) for p in csv_paths if p.exists()), None)

if df is None or df.empty:
    st.info("👆 위 `Browse files` 버튼을 누르거나, 가지고 계신 **22개의 PDF 파일을 마우스로 한꺼번에 드래그해서 위 상자에 놓아주세요!**")
    st.stop()

# 연도 정수 변환
if "year" in df.columns and df["year"].notna().any():
    df = df[df["year"].notna()].copy()
    df["year"] = df["year"].astype(int)

# 에버리지 컬럼 찾기
num_cols = [c for c in df.select_dtypes(include="number").columns if c != "year"]
avg_col = next((c for c in num_cols if any(k in c.lower() for k in ["avg", "에버", "평균"])), num_cols[0])

# 성별 컬럼 찾기
gender_col = next((c for c in df.columns if any(k in c.lower() for k in ["gender", "성별"])), None)

# 참가대회수 컬럼 찾기 및 '70% 이상 참가' 필터 적용
tourney_col = next((c for c in num_cols if any(k in c.lower() for k in ["대회", "참가", "tourney", "count"])), None)
if tourney_col:
    group_keys = ["year", gender_col] if gender_col else ["year"]
    max_t = df.groupby(group_keys)[tourney_col].transform("max")
    min_req = (max_t * 0.7).apply(math.ceil)
    df = df[df[tourney_col] >= min_req].copy()
    st.sidebar.success("✅ 대회 70% 이상 참가자 필터 적용됨")

# 사이드바: 성별 필터
if gender_col:
    genders = ["전체"] + sorted(df[gender_col].dropna().unique().tolist())
    sel_gender = st.sidebar.radio("성별 구분", genders)
    if sel_gender != "전체":
        df = df[df[gender_col] == sel_gender]

if df.empty:
    st.error("필터 조건을 만족하는 유효한 데이터가 없습니다.")
    st.stop()

# 연도별 전체 통계 집계
yearly = (
    df.groupby("year", as_index=False)[avg_col]
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
if gender_col:
    st.scatter_chart(
        data=df.assign(연도=df["year"].astype(str) + "년").rename(columns={avg_col: "에버리지", gender_col: "성별"}),
        x="연도",
        y="에버리지",
        color="성별",
    )
else:
    st.scatter_chart(
        data=df.assign(연도=df["year"].astype(str) + "년").rename(columns={avg_col: "에버리지"}),
        x="연도",
        y="에버리지",
    )

# 비식별화 데이터 미리보기 및 다운로드
with st.expander("📋 비식별화 데이터 미리보기 및 CSV 다운로드"):
    st.dataframe(df.sort_values(["year", avg_col], ascending=[True, False]), hide_index=True, use_container_width=True)
    st.download_button(
        "📥 정제된 CSV 다운로드 (개인정보 제외)",
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name="bowling_avg_filtered_clean.csv",
        mime="text/csv",
    )
