import os
import streamlit as st
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score, mean_absolute_error

st.set_page_config(page_title="프로볼링 10년 에버리지 분석", layout="wide")
st.title("🎳 지난 10년간 한국 프로볼링 평균 에버리지는 올랐는가?")

# 1. 안전한 파일 경로 찾기 및 CSV 읽기 (인코딩/구분자/깨진 줄 방어)
base_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(base_dir, "data", "bowling_avg.csv")

def load_data(path):
    for enc in ["utf-8", "cp949", "euc-kr"]:
        try:
            # sep=None, engine='python'으로 쉼표/탭 구분자 자동 인식, on_bad_lines='skip'으로 깨진 줄 건너뛰기
            return pd.read_csv(path, encoding=enc, sep=None, engine="python", on_bad_lines="skip")
        except Exception:
            continue
    return None

df = load_data(csv_path)

if df is None or df.empty:
    st.error("`data/bowling_avg.csv` 파일을 읽을 수 없습니다. 파일 경로와 내용을 확인해 주세요.")
    st.stop()

# 2. 열 이름 공백 제거 및 데이터 전처리
df.columns = [str(c).strip() for c in df.columns]

st.subheader("1. 원본 데이터 미리보기")
st.dataframe(df.head(10), use_container_width=True)

# 사용자가 CSV 열 이름을 자유롭게 선택할 수 있도록 사이드바 제공 (KeyError 방지)
st.sidebar.header("⚙️ 분석 열 및 전처리 설정")
cols = list(df.columns)

year_col = st.sidebar.selectbox("연도 열 선택", cols, index=0)
avg_col = st.sidebar.selectbox("에버리지 열 선택", cols, index=len(cols) - 1)

# 숫자 변환 함수 (천 단위 쉼표 ',' 제거 후 숫자로 변환)
def to_numeric_clean(series):
    return pd.to_numeric(series.astype(str).str.replace(",", "").str.strip(), errors="coerce")

clean_df = pd.DataFrame()
clean_df["연도"] = to_numeric_clean(df[year_col])
clean_df["에버리지"] = to_numeric_clean(df[avg_col])

# 게임수 열이 있다면 규정 게임수 필터링 옵션 제공
game_candidates = [c for c in cols if "게임" in c or "game" in c.lower()]
if game_candidates:
    game_col = st.sidebar.selectbox("게임수 열 선택 (선택사항)", ["사용 안 함"] + cols, index=cols.index(game_candidates[0]) + 1)
    if game_col != "사용 안 함":
        clean_df["게임수"] = to_numeric_clean(df[game_col])
        min_games = st.sidebar.slider("최소 규정 게임수 필터", 0, 100, 30)
        clean_df = clean_df[clean_df["게임수"] >= min_games]

# 결측치 및 비정상 연도 제거
clean_df = clean_df.dropna(subset=["연도", "에버리지"])
clean_df = clean_df[(clean_df["연도"] >= 2000) & (clean_df["연도"] <= 2030)]
clean_df["연도"] = clean_df["연도"].astype(int)

if len(clean_df) < 2:
    st.warning("전처리 후 남은 유효한 데이터가 2개 미만입니다. 사이드바에서 '연도'와 '에버리지' 열이 올바르게 선택되었는지 확인해 주세요.")
    st.stop()

# 3. 선형 회귀 모델 및 베이스라인(평균 모델) 비교
X = clean_df[["연도"]]
y = clean_df["에버리지"]

# 베이스라인: 모든 연도를 전체 평균값으로 예측
baseline_pred = np.full(len(y), y.mean())
baseline_mae = mean_absolute_error(y, baseline_pred)
baseline_r2 = r2_score(y, baseline_pred)  # 항상 0.0

# 선형 회귀 모델 학습
model = LinearRegression()
model.fit(X, y)
y_pred = model.predict(X)

model_mae = mean_absolute_error(y, y_pred)
model_r2 = r2_score(y, y_pred)
slope = model.coef_[0]

# 4. 분석 결과 및 평가지표 출력
st.subheader("2. 회귀 분석 결과 및 베이스라인 비교")

col1, col2, col3, col4 = st.columns(4)
col1.metric("연도별 에버리지 기울기", f"{slope:+.4f} 점/년")
col2.metric("회귀 모델 R² (결정계수)", f"{model_r2:.4f}", delta=f"베이스라인 대비 {model_r2 - baseline_r2:+.4f}")
col3.metric("회귀 모델 MAE (평균절대오차)", f"{model_mae:.3f}", delta=f"{model_mae - baseline_mae:+.3f} (낮을수록 우수)", delta_color="inverse")
col4.metric("분석 대상 데이터 수", f"{len(clean_df)} 건")

# 5. 연도별 평균 추이 그래프
st.subheader("3. 연도별 평균 에버리지 변화 추이")
yearly_avg = clean_df.groupby("연도", as_index=False)["에버리지"].mean()
yearly_avg["회귀 추세선"] = model.predict(yearly_avg[["연도"]])

chart_df = yearly_avg.set_index("연도")[["에버리지", "회귀 추세선"]]
st.line_chart(chart_df)

with st.expander("📋 연도별 요약 통계표 보기"):
    summary = clean_df.groupby("연도")["에버리지"].agg(["count", "mean", "std", "min", "max"]).reset_index()
    summary.columns = ["연도", "선수 수(명)", "평균 에버리지", "표준편차", "최솟값", "최댓값"]
    st.dataframe(summary, use_container_width=True)
