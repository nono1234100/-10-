from pathlib import Path
import pandas as pd
import streamlit as st

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="볼링 에버리지 분석 대시보드", page_icon="🎳", layout="wide"
)


# 2. CSV 파일 안전 로드 함수 (경로·인코딩·구분자 자동 탐색)
@st.cache_data
def load_csv_from_path(file_path: Path):
  encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
  last_error = None

  for enc in encodings:
    for sep in [",", ";", "\t"]:
      try:
        df = pd.read_csv(file_path, encoding=enc, sep=sep)
        # 컬럼이 1개뿐이고 다른 구분자가 포함된 경우 다음 구분자 시도
        if len(df.columns) == 1 and any(
            s in str(df.columns[0]) for s in [",", ";", "\t"]
        ):
          continue
        if not df.empty:
          return clean_dataframe(df), None
      except Exception as e:
        last_error = e
  return None, last_error


def load_csv_from_upload(uploaded_file):
  encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
  last_error = None

  for enc in encodings:
    try:
      uploaded_file.seek(0)
      df = pd.read_csv(uploaded_file, encoding=enc)
      if not df.empty:
        return clean_dataframe(df), None
    except Exception as e:
      last_error = e
  return None, last_error


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
  """공백 제거 및 숫자형 데이터 자동 정제"""
  df = df.dropna(how="all").dropna(axis=1, how="all").copy()
  df.columns = [str(col).strip() for col in df.columns]

  for col in df.columns:
    if df[col].dtype == "object":
      cleaned = (
          df[col]
          .astype(str)
          .str.strip()
          .str.replace(",", "", regex=False)
          .str.replace("점", "", regex=False)
      )
      converted = pd.to_numeric(cleaned, errors="coerce")
      # 결측치를 제외한 값의 70% 이상이 숫자라면 숫자형 컬럼으로 변환
      non_null_ratio = converted.notna().mean()
      if non_null_ratio >= 0.7:
        df[col] = converted
      else:
        df[col] = df[col].astype(str).str.strip()
  return df


def get_sample_data() -> pd.DataFrame:
  """파일이 없을 때 테스트할 수 있는 샘플 데이터"""
  return pd.DataFrame({
      "이름": ["김민수", "이서연", "박지훈", "최유진", "정현우", "강다은"],
      "게임1": [182, 165, 210, 154, 195, 178],
      "게임2": [194, 172, 198, 168, 204, 185],
      "게임3": [188, 180, 215, 162, 189, 190],
      "에버리지": [188.0, 172.3, 207.7, 161.3, 196.0, 184.3],
  })


def find_default_col(columns, keywords, fallback_idx=0):
  for kw in keywords:
    for col in columns:
      if kw in col.lower():
        return col
  return columns[fallback_idx] if columns else None


# 3. 데이터 불러오기 실행
BASE_DIR = Path(__file__).resolve().parent
CANDIDATE_PATHS = [
    BASE_DIR / "data" / "bowling_avg.csv",
    BASE_DIR / "bowling_avg.csv",
    Path("data/bowling_avg.csv"),
    Path("bowling_avg.csv"),
]

df = None
error_msg = None
loaded_path = None

for path in CANDIDATE_PATHS:
  if path.exists():
    df, error_msg = load_csv_from_path(path)
    if df is not None:
      loaded_path = path
      break

# 4. 메인 타이틀 및 데이터 미발견 시 대체 처리
st.title("🎳 볼링 에버리지 분석 대시보드")

if df is None:
  st.warning(
      "`data/bowling_avg.csv` 파일을 자동으로 불러오지 못했습니다. "
      "아래에서 CSV 파일을 직접 업로드하거나 샘플 데이터로 먼저 실행해 보세요."
  )
  if error_msg:
    with st.expander("상세 오류 내용 확인"):
      st.code(str(error_msg))

  col_up, col_sample = st.columns([2, 1])
  with col_up:
    uploaded = st.file_uploader(
        "bowling_avg.csv 파일 업로드", type=["csv"]
    )
    if uploaded is not None:
      df, up_err = load_csv_from_upload(uploaded)
      if df is None:
        st.error(f"업로드한 파일을 읽는 중 오류가 발생했습니다: {up_err}")
  with col_sample:
    st.write("")
    st.write("")
    if st.checkbox("샘플 데이터로 화면 미리보기", value=False):
      df = get_sample_data()
      st.info("현재 샘플 데이터가 표시되고 있습니다.")

  if df is None:
    st.stop()
else:
  st.caption(f"데이터 로드 완료: `{loaded_path}` ({len(df)}행 × {len(df.columns)}열)")

# 5. 컬럼 자동 매핑 및 사이드바 설정
all_cols = list(df.columns)
num_cols = list(df.select_dtypes(include="number").columns)
cat_cols = [c for c in all_cols if c not in num_cols]

if not num_cols:
  st.error(
      "CSV 파일에서 점수나 에버리지로 사용할 숫자형 컬럼을 찾지 못했습니다."
  )
  st.dataframe(df, use_container_width=True)
  st.stop()

with st.sidebar:
  st.header("⚙️ 분석 설정")

  default_name = find_default_col(
      cat_cols if cat_cols else all_cols,
      ["이름", "선수", "회원", "성명", "닉네임", "name", "player"],
  )
  name_col = st.selectbox(
      "이름/구분 기준 컬럼",
      options=all_cols,
      index=all_cols.index(default_name),
  )

  default_avg = find_default_col(
      num_cols,
      ["에버", "avg", "average", "평균", "점수", "score", "총점", "total"],
  )
  metric_col = st.selectbox(
      "분석할 점수/에버리지 컬럼",
      options=num_cols,
      index=num_cols.index(default_avg),
  )

  # 필터링 (이름 컬럼이 범주형일 경우)
  unique_names = df[name_col].dropna().unique().tolist()
  if 1 < len(unique_names) <= 100:
    selected_names = st.multiselect(
        f"{name_col} 필터", options=unique_names, default=unique_names
    )
    filtered_df = df[df[name_col].isin(selected_names)].copy()
  else:
    filtered_df = df.copy()

if filtered_df.empty:
  st.warning("선택된 필터 조건에 해당하는 데이터가 없습니다.")
  st.stop()

# 6. 핵심 요약 지표 (KPI)
valid_scores = filtered_df[metric_col].dropna()
avg_val = valid_scores.mean()
max_val = valid_scores.max()
min_val = valid_scores.min()

max_row = filtered_df.loc[valid_scores.idxmax()]
max_owner = max_row[name_col]

k1, k2, k3, k4 = st.columns(4)
k1.metric("총 기록 수", f"{len(filtered_df):,}건")
k2.metric(f"전체 평균 ({metric_col})", f"{avg_val:.1f}점")
k3.metric("최고 기록", f"{max_val:.1f}점", delta=f"{max_owner}")
k4.metric("최저 기록", f"{min_val:.1f}점")

st.divider()

# 7. 탭 구성 (순위/차트, 게임별 비교, 원본 데이터)
tab1, tab2, tab3 = st.tabs(
    ["🏆 순위 및 에버리지 차트", "📊 게임별 점수 비교", "📋 전체 데이터 조회"]
)

with tab1:
  # 동일 인물이 여러 번 등장할 수 있으므로 평균 기준 집계
  ranking_df = (
      filtered_df.groupby(name_col, as_index=False)[metric_col]
      .mean()
      .sort_values(by=metric_col, ascending=False)
      .reset_index(drop=True)
  )
  ranking_df.insert(0, "순위", ranking_df.index + 1)
  ranking_df[metric_col] = ranking_df[metric_col].round(1)

  col_chart, col_table = st.columns([3, 2])
  with col_chart:
    st.subheader(f"{name_col}별 {metric_col} 비교")
    chart_data = ranking_df.set_index(name_col)[[metric_col]]
    st.bar_chart(chart_data, use_container_width=True)

  with col_table:
    st.subheader("순위표")
    st.dataframe(ranking_df, hide_index=True, use_container_width=True)

with tab2:
  if len(num_cols) >= 2:
    st.subheader("숫자 항목별 비교 추이")
    selected_num_cols = st.multiselect(
        "비교할 점수 컬럼 선택", options=num_cols, default=num_cols
    )
    if selected_num_cols:
      compare_df = filtered_df.groupby(name_col)[selected_num_cols].mean()
      st.line_chart(compare_df, use_container_width=True)
  else:
    st.info(
        "비교할 수 있는 추가 게임 점수 컬럼(예: 게임1, 게임2, 게임3)이 없습니다."
    )

with tab3:
  search_text = st.text_input("검색어 입력 (이름, 날짜 등)", "")
  display_df = filtered_df.copy()
  if search_text:
    mask = display_df.apply(
        lambda row: row.astype(str)
        .str.contains(search_text, case=False)
        .any(),
        axis=1,
    )
    display_df = display_df[mask]

  st.dataframe(display_df, use_container_width=True)

  csv_bytes = display_df.to_csv(index=False).encode("utf-8-sig")
  st.download_button(
      label="현재 조회 결과 CSV 다운로드",
      data=csv_bytes,
      file_name="bowling_avg_filtered.csv",
      mime="text/csv",
  )
