from pathlib import Path
import pandas as pd
import streamlit as st

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="볼링 에버리지 분석 대시보드",
    page_icon="🎳",
    layout="wide",
)


# 2. 데이터 정제 및 CSV 안전 로드 함수
def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
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
            if converted.notna().mean() >= 0.7:
                df[col] = converted
            else:
                df[col] = df[col].astype(str).str.strip()
    return df


@st.cache_data
def load_csv_from_path(file_path: Path):
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
    last_error = None

    for enc in encodings:
        for sep in [",", ";", "\t"]:
            try:
                df = pd.read_csv(file_path, encoding=enc, sep=sep)
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


def get_sample_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "선수명": ["김민수", "이서연", "박지훈", "최유진", "정현우", "강다은"],
            "기수": ["25기", "26기", "24기", "27기", "25기", "26기"],
            "게임수": [24, 24, 24, 18, 24, 18],
            "총점": [4985, 4632, 5112, 3456, 4824, 3582],
            "에버리지": [207.7, 193.0, 213.0, 192.0, 201.0, 199.0],
        }
    )


def find_default_col(columns, keywords, fallback_idx=0):
    for kw in keywords:
        for col in columns:
            if kw in col.lower():
                return col
    return columns[fallback_idx] if columns else None


# 3. CSV 파일 탐색
BASE_DIR = Path(__file__).resolve().parent
CANDIDATE_PATHS = [
    BASE_DIR / "data" / "bowling_avg.csv",
    BASE_DIR / "bowling_avg.csv",
    Path("data/bowling_avg.csv"),
    Path("bowling_avg.csv"),
]

df = None
loaded_path = None
error_msg = None

for path in CANDIDATE_PATHS:
    if path.exists():
        df, error_msg = load_csv_from_path(path)
        if df is not None:
            loaded_path = path
            break

# 4. 화면 상단 헤더 및 데이터 소스 처리
st.title("🎳 볼링 에버리지 분석 대시보드")

with st.expander("📂 CSV 파일 직접 업로드 / 데이터 상태 확인", expanded=(df is None)):
    uploaded_file = st.file_uploader(
        "로컬에 있는 bowling_avg.csv 파일을 선택하면 즉시 반영됩니다.",
        type=["csv"],
    )
    if uploaded_file is not None:
        uploaded_df, upload_err = load_csv_from_upload(uploaded_file)
        if uploaded_df is not None:
            df = uploaded_df
            loaded_path = f"업로드 파일 ({uploaded_file.name})"
        else:
            st.error(f"업로드한 파일을 읽지 못했습니다: {upload_err}")

if df is None:
    st.info(
        "저장소에 `data/bowling_avg.csv` 파일이 아직 없어 **샘플 데이터**로 화면을 표시합니다. "
        "위에서 파일을 업로드하거나 GitHub에 `data/bowling_avg.csv`를 추가해 주세요."
    )
    if error_msg:
        st.caption(f"참고 오류 로그: {error_msg}")
    df = get_sample_data()
else:
    st.caption(f"현재 데이터: `{loaded_path}` ({len(df):,}행 × {len(df.columns)}열)")

# 5. 컬럼 자동 인식 및 사이드바 필터
all_cols = list(df.columns)
num_cols = list(df.select_dtypes(include="number").columns)
cat_cols = [c for c in all_cols if c not in num_cols]

if not num_cols:
    st.error("CSV 파일에서 에버리지나 점수로 사용할 숫자 데이터를 찾지 못했습니다.")
    st.dataframe(df)
    st.stop()

with st.sidebar:
    st.header("⚙️ 분석 설정")

    default_name = find_default_col(
        cat_cols if cat_cols else all_cols,
        ["선수", "이름", "성명", "회원", "닉네임", "name", "player"],
    )
    name_col = st.selectbox(
        "선수/구분 컬럼",
        options=all_cols,
        index=all_cols.index(default_name),
    )

    default_metric = find_default_col(
        num_cols,
        ["에버", "avg", "average", "평균", "점수", "score", "총점", "total"],
    )
    metric_col = st.selectbox(
        "기준 점수/에버리지 컬럼",
        options=num_cols,
        index=num_cols.index(default_metric),
    )

    unique_items = df[name_col].dropna().unique().tolist()
    if 1 < len(unique_items) <= 200:
        selected_items = st.multiselect(
            f"{name_col} 선택",
            options=unique_items,
            default=unique_items,
        )
        filtered_df = df[df[name_col].isin(selected_items)].copy()
    else:
        filtered_df = df.copy()

if filtered_df.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

valid_scores = filtered_df[metric_col].dropna()
if valid_scores.empty:
    st.warning(f"'{metric_col}' 컬럼에 유효한 숫자 데이터가 없습니다.")
    st.stop()

# 6. 핵심 요약 지표 (KPI)
avg_score = valid_scores.mean()
max_score = valid_scores.max()
min_score = valid_scores.min()
top_player = filtered_df.loc[valid_scores.idxmax(), name_col]

c1, c2, c3, c4 = st.columns(4)
c1.metric("조회 인원/건수", f"{len(filtered_df):,}건")
c2.metric(f"전체 평균 ({metric_col})", f"{avg_score:.1f}")
c3.metric("최고 기록", f"{max_score:.1f}", delta=f"1위: {top_player}")
c4.metric("최저 기록", f"{min_score:.1f}")

st.divider()

# 7. 탭 화면 구성
tab1, tab2, tab3 = st.tabs(["🏆 순위 및 차트", "📊 항목별 비교", "📋 전체 데이터 조회"])

with tab1:
    if name_col == metric_col:
        ranking_df = filtered_df[[metric_col]].copy()
    else:
        ranking_df = (
            filtered_df.groupby(name_col, as_index=False)[metric_col]
            .mean()
            .sort_values(by=metric_col, ascending=False)
            .reset_index(drop=True)
        )

    ranking_df.insert(0, "순위", ranking_df.index + 1)
    ranking_df[metric_col] = ranking_df[metric_col].round(1)

    col_left, col_right = st.columns([3, 2])
    with col_left:
        st.subheader(f"{name_col}별 {metric_col}")
        if name_col != metric_col:
            st.bar_chart(ranking_df.set_index(name_col)[[metric_col]])
        else:
            st.bar_chart(ranking_df[[metric_col]])

    with col_right:
        st.subheader("순위표")
        st.dataframe(ranking_df, hide_index=True)

with tab2:
    if len(num_cols) >= 2 and name_col not in num_cols:
        st.subheader("숫자 항목 비교")
        selected_cols = st.multiselect(
            "비교할 컬럼 선택",
            options=num_cols,
            default=num_cols,
        )
        if selected_cols:
            compare_df = filtered_df.groupby(name_col)[selected_cols].mean()
            st.line_chart(compare_df)
    else:
        st.info("비교할 수 있는 추가 숫자 컬럼이 없습니다.")

with tab3:
    keyword = st.text_input("검색어 입력", placeholder="선수명, 기수 등 검색")
    view_df = filtered_df.copy()
    if keyword:
        mask = view_df.apply(
            lambda row: row.astype(str).str.contains(keyword, case=False).any(),
            axis=1,
        )
        view_df = view_df[mask]

    st.dataframe(view_df, hide_index=True)

    csv_data = view_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="CSV 파일로 다운로드",
        data=csv_data,
        file_name="bowling_avg_result.csv",
        mime="text/csv",
    )
