from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="볼링 에버리지 분석", layout="wide")


def load_csv_safely(file_source):
  """여러 인코딩을 순차적으로 시도해 CSV를 안전하게 불러옵니다."""
  encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
  last_error = None

  for enc in encodings:
    try:
      if hasattr(file_source, "seek"):
        file_source.seek(0)
      df = pd.read_csv(file_source, encoding=enc)
      if not df.empty:
        return df, None
    except Exception as e:
      last_error = e

  return None, last_error


# 현재 .py 파일이 있는 폴더를 기준으로 data/bowling_avg.csv 경로 설정
BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "bowling_avg.csv"

st.title("🎳 볼링 에버리지 분석")

df = None
error_detail = None

if CSV_PATH.exists():
  df, error_detail = load_csv_safely(CSV_PATH)
else:
  error_detail = f"해당 경로에 파일이 없습니다 -> {CSV_PATH}"

# 기본 경로에서 읽지 못한 경우 구체적 원인 안내 및 직접 업로드 지원
if df is None:
  st.error(f"파일을 읽을 수 없습니다. 원인: {error_detail}")
  uploaded_file = st.file_uploader(
      "bowling_avg.csv 파일을 직접 업로드해 보세요", type=["csv"]
  )
  if uploaded_file is not None:
    df, error_detail = load_csv_safely(uploaded_file)
    if df is None:
      st.error(f"업로드한 파일도 읽을 수 없습니다: {error_detail}")

if df is not None:
  st.success(f"데이터 로드 성공 ({len(df)}행 × {len(df.columns)}열)")
  st.dataframe(df, use_container_width=True)
