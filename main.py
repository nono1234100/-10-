from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="KPBA 볼링 에버리지 추이 분석 (2015~)", page_icon="🎳", layout="wide")

EXCLUDE_KEYWORDS = ["선수", "이름", "성명", "회원", "name", "player", "팀", "소속", "구단", "team", "club"]
YEAR_KEYWORDS = ["year", "연도", "년도", "시즌", "season", "날짜", "date"]


def clean_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.dropna(how="all").dropna(axis=1, how="all").copy()
    df.columns = [str(c).strip() for c in df.columns]

    # 1. 개인정보(선수이름, 팀명/소속) 컬럼 자동 삭제
    drop_cols = [c for c in df.columns if any(k in c.lower() for k in EXCLUDE_KEYWORDS)]
    if drop_cols:
        df = df.drop(columns=drop_cols)

    # 2. 숫자형 데이터 정제 (천 단위 쉼표 제거)
    for col in df.columns:
        if df[col].dtype == "object":
            s = df[col].astype(str).str.strip().str.replace(",", "", regex=False)
            num = pd.to_numeric(s, errors="coerce")
            df[col] = num if num.notna().mean() >= 0.6 else s

    # 3. 연도 컬럼 표준화 (year)
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
                return clean_data(df)
        except Exception:
            continue
    return None


st.title("🎳 KPBA 프로볼링 에버리지 추이 분석 (2015~)")
st.caption("개인정보 보호를 위해 선수 이름과 팀명은 자동으로 제거되며, 2015년 이후 기록만 분석합니다.")

base_dir = Path(__file__).resolve().parent
csv_paths = [base_dir / "data" / "bowling_avg.csv", Path("data/bowling_avg.csv"), Path("bowling_avg.csv")]

df = next((load_csv(p) for p in csv_paths if p.exists()), None)

uploaded = st.file_uploader("CSV 파일 직접 업로드 (data/bowling_avg.csv가 없을 때 사용)", type=["csv"])
if uploaded is not None:
    df = load_csv(uploaded)

if df is None:
    st.warning("`data/bowling_avg.csv` 파일을 찾을 수 없습니다. GitHub의 `data/bowling_avg.csv` 경로에 파일을 올리거나 위에서 직접 업로드해 주세요.")
    st.stop()

# 2015년 이후 데이터 필터링
if "year" in df.columns and df["year"].notna().any():
    df = df[df["year"] >= 2015].copy()
    df["year"] = df["year"].astype(int)

if df.empty:
    st.error("2015년 이후 유효한 데이터가 없습니다.")
    st.stop()

# 에버리지 컬럼 찾기
num_cols = [c for c in df.select_dtypes(include="number").columns if c != "year"]
avg_col = next((c for c in num_cols if any(k in c.lower() for k in ["avg", "에버", "평균"])), num_cols[0])

# 성별 필터 (gender 컬럼이 있는 경우)
gender_col = next((c for c in df.columns if any(k in c.lower() for k in ["gender", "성별"])), None)
if gender_col:
    genders = ["전체"] + sorted(df[gender_col].dropna().unique().tolist())
    sel_gender = st.sidebar.radio("성별 구분", genders)
    if sel_gender != "전체":
        df = df[df[gender_col] == sel_gender]

# 연도별 통계 집계
yearly = (
    df.groupby("year", as_index=False)[avg_col]
    .agg(평균="mean", 최고="max", 최저="min", 표본수="count")
    .sort_values("year")
)

# 선형 회귀 분석 및 기준 모델(Baseline) 비교
x = yearly["year"].to_numpy(dtype=float)
y = yearly["평균"].to_numpy(dtype=float)

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

# 추이 그래프 및 요약표
col1, col2 = st.columns([3, 2])
with col1:
    st.subheader("📈 연도별 평균 에버리지 변화 추이")
    chart_df = yearly.assign(연도=yearly["year"].astype(str) + "년").set_index("연도")[["평균", "최고"]]
    st.line_chart(chart_df)

with col2:
    st.subheader("📊 연도별 요약 통계")
    st.dataframe(yearly.round(2), hide_index=True, use_container_width=True)

# 비식별화 데이터 조회 및 다운로드
with st.expander("📋 비식별화 데이터 미리보기 및 CSV 다운로드"):
    st.dataframe(df.sort_values("year"), hide_index=True, use_container_width=True)
    st.download_button(
        "📥 정제된 CSV 다운로드 (이름·팀명 제외)",
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name="bowling_avg_2015_clean.csv",
        mime="text/csv",
    )
# END OF CODE
