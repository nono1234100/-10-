from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="KPBA 볼링 에버리지 분석",
    page_icon="🎳",
    layout="wide",
)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """빈 행/열을 제거하고 숫자형 컬럼을 자동으로 정제합니다."""
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
                .str.replace("게임", "", regex=False)
            )
            converted = pd.to_numeric(cleaned, errors="coerce")
            if converted.notna().mean() >= 0.7:
                df[col] = converted
            else:
                df[col] = df[col].astype(str).str.strip()
    return df


@st.cache_data
def load_csv_from_path(file_path: Path):
    """여러 인코딩과 구분자를 순차 시도해 로컬 CSV를 불러옵니다."""
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
    """업로드된 CSV 파일을 안전하게 불러옵니다."""
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
    """CSV 파일이 없을 때 기본으로 표시할 KPBA 샘플 데이터입니다."""
    return pd.DataFrame(
        {
            "선수명": ["김태영", "박경신", "정태화", "최원영", "김수진", "윤여진", "강희원", "이명훈"],
            "기수": ["25기", "9기", "3기", "14기", "11기", "15기", "18기", "22기"],
            "소속": ["팀스톰", "팀브런스윅", "DSD", "팀에보나이트", "팀로또그립", "팀모티브", "팀햄머", "팀트랙"],
            "게임수": [36, 42, 30, 36, 30, 36, 24, 30],
            "총점": [7632, 8736, 6150, 7452, 6030, 7164, 4920, 5940],
            "에버리지": [212.0, 208.0, 205.0, 207.0, 201.0, 199.0, 205.0, 198.0],
        }
    )


def find_col(columns, keywords, fallback_idx=0):
    for kw in keywords:
        for col in columns:
            if kw in col.lower():
                return col
    return columns[fallback_idx] if columns else None


# 1. CSV 파일 자동 탐색
BASE_DIR = Path(__file__).resolve().parent
CANDIDATE_PATHS = [
    BASE_DIR / "data" / "bowling_avg.csv",
    BASE_DIR / "bowling_avg.csv",
    Path("data/bowling_avg.csv"),
    Path("bowling_avg.csv"),
]

df = None
loaded_source = None
error_detail = None

for path in CANDIDATE_PATHS:
    if path.exists():
        df, error_detail = load_csv_from_path(path)
        if df is not None:
            loaded_source = str(path)
            break

# 2. 상단 헤더 및 파일 업로드 영역
st.title("🎳 볼링 에버리지 분석 대시보드")

with st.expander("📂 CSV 파일 업로드 및 데이터 상태", expanded=(df is None)):
    uploaded_file = st.file_uploader(
        "내 컴퓨터의 bowling_avg.csv 파일을 업로드하면 즉시 분석됩니다.",
        type=["csv"],
    )
    if uploaded_file is not None:
        up_df, up_err = load_csv_from_upload(uploaded_file)
        if up_df is not None:
            df = up_df
            loaded_source = f"업로드됨: {uploaded_file.name}"
        else:
            st.error(f"업로드한 파일을 읽지 못했습니다: {up_err}")

if df is None:
    st.info(
        "현재 저장소에 `data/bowling_avg.csv` 파일이 없어 **샘플 데이터**로 표시 중입니다. "
        "위에서 파일을 직접 업로드하거나 GitHub에 `data/bowling_avg.csv`를 올려주세요."
    )
    if error_detail:
        st.caption(f"파일 탐색 참고: {error_detail}")
    df = get_sample_data()
else:
    st.caption(f"데이터 로드 완료: `{loaded_source}` ({len(df):,}행 × {len(df.columns)}열)")

# 3. 컬럼 자동 매핑 및 사이드바 필터
all_cols = list(df.columns)
num_cols = list(df.select_dtypes(include="number").columns)
cat_cols = [c for c in all_cols if c not in num_cols]

if not num_cols:
    st.error("CSV 파일에서 에버리지나 점수로 사용할 숫자형 컬럼을 찾지 못했습니다.")
    st.dataframe(df, use_container_width=True)
    st.stop()

with st.sidebar:
    st.header("⚙️ 분석 옵션")

    default_name = find_col(
        cat_cols if cat_cols else all_cols,
        ["선수", "이름", "성명", "회원", "name", "player"],
    )
    name_col = st.selectbox(
        "선수/이름 컬럼",
        options=all_cols,
        index=all_cols.index(default_name),
    )

    default_metric = find_col(
        num_cols,
        ["에버", "avg", "average", "평균", "점수", "score", "총점"],
    )
    metric_col = st.selectbox(
        "에버리지/점수 컬럼",
        options=num_cols,
        index=num_cols.index(default_metric),
    )

    filtered_df = df.copy()

    # 기수/소속 등 그룹 컬럼이 있으면 자동 필터 제공
    group_candidates = [
        c for c in cat_cols
        if c != name_col and 1 < df[c].nunique() <= 50
    ]
    if group_candidates:
        group_col = group_candidates[0]
        group_options = sorted(df[group_col].dropna().unique().tolist())
        selected_groups = st.multiselect(
            f"{group_col} 필터",
            options=group_options,
            default=group_options,
        )
        filtered_df = filtered_df[filtered_df[group_col].isin(selected_groups)]

    # 게임수 컬럼이 있으면 최소 게임수 필터 제공
    game_col = find_col(num_cols, ["게임", "경기", "game"], fallback_idx=-1)
    if game_col and game_col != metric_col and filtered_df[game_col].notna().any():
        min_g = int(filtered_df[game_col].min())
        max_g = int(filtered_df[game_col].max())
        if min_g < max_g:
            cut_g = st.slider(
                f"최소 {game_col} 기준",
                min_value=min_g,
                max_value=max_g,
                value=min_g,
            )
            filtered_df = filtered_df[filtered_df[game_col] >= cut_g]

if filtered_df.empty:
    st.warning("선택한 필터 조건에 맞는 데이터가 없습니다.")
    st.stop()

valid_scores = filtered_df[metric_col].dropna()
if valid_scores.empty:
    st.warning(f"'{metric_col}' 컬럼에 유효한 숫자 값이 없습니다.")
    st.stop()

# 4. 핵심 요약 지표 (KPI)
avg_val = valid_scores.mean()
max_val = valid_scores.max()
min_val = valid_scores.min()
top_name = filtered_df.loc[valid_scores.idxmax(), name_col]

k1, k2, k3, k4 = st.columns(4)
k1.metric("조회 데이터 수", f"{len(filtered_df):,}건")
k2.metric(f"전체 평균 ({metric_col})", f"{avg_val:.1f}")
k3.metric("최고 기록", f"{max_val:.1f}", delta=f"1위: {top_name}")
k4.metric("최저 기록", f"{min_val:.1f}")

st.divider()

# 5. 메인 분석 탭
tab1, tab2, tab3 = st.tabs(["🏆 순위 및 에버리지 차트", "📊 다중 항목 비교", "📋 전체 데이터 조회"])

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

    max_top = len(ranking_df)
    top_n = st.slider(
        "차트에 표시할 상위 인원 수",
        min_value=1,
        max_value=max(1, max_top),
        value=min(20, max_top),
    )
    top_df = ranking_df.head(top_n)

    col_chart, col_table = st.columns([3, 2])
    with col_chart:
        st.subheader(f"상위 {len(top_df)}명 {metric_col} 차트")
        if name_col != metric_col:
            st.bar_chart(top_df.set_index(name_col)[[metric_col]])
        else:
            st.bar_chart(top_df[[metric_col]])

    with col_table:
        st.subheader("전체 순위표")
        st.dataframe(ranking_df, hide_index=True, use_container_width=True)

with tab2:
    if len(num_cols) >= 2 and name_col not in num_cols:
        st.subheader("항목별 수치 비교")
        selected_num = st.multiselect(
            "비교할 숫자 컬럼 선택",
            options=num_cols,
            default=num_cols[: min(3, len(num_cols))],
        )
        if selected_num:
            comp_df = filtered_df.groupby(name_col)[selected_num].mean().head(30)
            st.line_chart(comp_df)
    else:
        st.info("비교할 수 있는 추가 숫자 컬럼이 없습니다.")

with tab3:
    search_kw = st.text_input("검색어 입력", placeholder="선수명, 기수, 소속 등 검색")
    table_df = filtered_df.copy()
    if search_kw:
        mask = table_df.apply(
            lambda r: r.astype(str).str.contains(search_kw, case=False).any(),
            axis=1,
        )
        table_df = table_df[mask]

    st.dataframe(table_df, hide_index=True, use_container_width=True)

    csv_bytes = table_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="조회 결과 CSV 다운로드",
        data=csv_bytes,
        file_name="bowling_avg_filtered.csv",
        mime="text/csv",
    )
