from pathlib import Path
import re
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="볼링 에버리지 연도별 분석 (2015~)",
    page_icon="🎳",
    layout="wide",
)

# 제외할 컬럼 키워드 (선수이름, 팀명/소속)
EXCLUDE_COL_KEYWORDS = [
    "선수", "이름", "성명", "회원", "닉네임", "name", "player",
    "팀", "소속", "구단", "클럽", "team", "club",
]

YEAR_COL_KEYWORDS = ["연도", "년도", "시즌", "year", "season", "날짜", "일자", "date"]


def extract_year(series: pd.Series) -> pd.Series:
    """문자열이나 날짜에서 4자리 연도(예: 2015)를 추출합니다."""
    extracted = series.astype(str).str.extract(r"(19\d{2}|20\d{2})", expand=False)
    return pd.to_numeric(extracted, errors="coerce")


def prepare_dataframe(raw_df: pd.DataFrame) -> pd.DataFrame:
    """팀명·선수이름 컬럼을 제거하고, 연도 데이터를 정제합니다."""
    df = raw_df.dropna(how="all").dropna(axis=1, how="all").copy()
    df.columns = [str(col).strip() for col in df.columns]

    # 1. 팀명 및 선수이름 관련 컬럼 자동 제거
    cols_to_drop = [
        col for col in df.columns
        if any(kw in col.lower() for kw in EXCLUDE_COL_KEYWORDS)
    ]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    # 2. 연도가 가로(컬럼명)로 펼쳐진 표 형태(예: 2014, 2015, 2016...)인 경우 세로로 변환
    year_header_cols = [
        col for col in df.columns
        if re.fullmatch(r"(19\d{2}|20\d{2})년?", str(col).strip())
    ]
    if len(year_header_cols) >= 3:
        id_cols = [c for c in df.columns if c not in year_header_cols]
        df = df.melt(
            id_vars=id_cols,
            value_vars=year_header_cols,
            var_name="연도",
            value_name="에버리지",
        )

    # 3. 숫자형 컬럼 정제
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
            if converted.notna().mean() >= 0.6:
                df[col] = converted
            else:
                df[col] = df[col].fillna("").astype(str).str.strip()

    # 4. 연도 컬럼 탐지 및 '연도' 컬럼 표준화
    year_col = None
    for kw in YEAR_COL_KEYWORDS:
        for col in df.columns:
            if kw in col.lower():
                year_col = col
                break
        if year_col:
            break

    if year_col is not None:
        years = extract_year(df[year_col])
        if years.notna().any():
            df["연도"] = years.astype("Int64")
            if year_col != "연도":
                df = df.drop(columns=[year_col])

    # 5. 총점과 게임수가 있고 에버리지 컬럼이 없으면 자동 계산
    has_avg = any("에버" in c or "avg" in c.lower() or "평균" in c for c in df.columns)
    game_cols = [c for c in df.columns if "게임" in c or "game" in c.lower()]
    total_cols = [c for c in df.columns if "총점" in c or "total" in c.lower()]

    if not has_avg and game_cols and total_cols:
        g_col, t_col = game_cols[0], total_cols[0]
        if pd.api.types.is_numeric_dtype(df[g_col]) and pd.api.types.is_numeric_dtype(df[t_col]):
            df["에버리지"] = (df[t_col] / df[g_col].replace(0, pd.NA)).round(2)

    return df


@st.cache_data
def load_csv_from_path(file_path: Path):
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
    last_error = None

    for enc in encodings:
        for sep in [",", "\t", ";"]:
            try:
                raw_df = pd.read_csv(file_path, encoding=enc, sep=sep)
                if len(raw_df.columns) == 1 and any(s in str(raw_df.columns[0]) for s in [",", "\t", ";"]):
                    continue
                if not raw_df.empty:
                    return prepare_dataframe(raw_df), None
            except Exception as e:
                last_error = e
    return None, last_error


def load_csv_from_upload(uploaded_file):
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
    last_error = None

    for enc in encodings:
        for sep in [",", "\t", ";"]:
            try:
                uploaded_file.seek(0)
                raw_df = pd.read_csv(uploaded_file, encoding=enc, sep=sep)
                if len(raw_df.columns) == 1 and any(s in str(raw_df.columns[0]) for s in [",", "\t", ";"]):
                    continue
                if not raw_df.empty:
                    return prepare_dataframe(raw_df), None
            except Exception as e:
                last_error = e
    return None, last_error


def find_col(columns, keywords, exclude=None):
    exclude = exclude or []
    for kw in keywords:
        for col in columns:
            if col in exclude:
                continue
            if kw in col.lower():
                return col
    candidates = [c for c in columns if c not in exclude]
    return candidates[0] if candidates else None


# 1. 저장소의 bowling_avg.csv 파일 탐색
BASE_DIR = Path(__file__).resolve().parent
CANDIDATE_PATHS = [
    BASE_DIR / "data" / "bowling_avg.csv",
    BASE_DIR / "bowling_avg.csv",
    Path("data/bowling_avg.csv"),
    Path("bowling_avg.csv"),
]

df = None
loaded_source = None
file_error = None

for path in CANDIDATE_PATHS:
    if path.exists():
        df, file_error = load_csv_from_path(path)
        if df is not None:
            loaded_source = str(path)
            break

# 2. 상단 타이틀 및 파일 업로드
st.title("🎳 볼링 에버리지 분석 (2015년 이후)")

with st.expander("📂 CSV 파일 불러오기 / 교체하기", expanded=(df is None)):
    uploaded_file = st.file_uploader(
        "bowling_avg.csv 파일을 업로드하면 팀명·선수이름을 제외하고 2015년부터 분석합니다.",
        type=["csv", "txt"],
    )
    if uploaded_file is not None:
        up_df, up_err = load_csv_from_upload(uploaded_file)
        if up_df is not None:
            df = up_df
            loaded_source = f"업로드 파일: {uploaded_file.name}"
        else:
            st.error(f"파일을 읽지 못했습니다: {up_err}")

if df is None:
    st.warning(
        "`data/bowling_avg.csv` 파일을 찾을 수 없습니다. "
        "GitHub 저장소의 `data/bowling_avg.csv` 경로에 파일을 올리거나 위에서 직접 업로드해 주세요."
    )
    if file_error:
        st.caption(f"상세 메시지: {file_error}")
    st.stop()

st.caption(f"데이터 출처: `{loaded_source}` (팀명·선수이름 자동 제외 적용됨)")

# 3. 2015년 이후 데이터 필터링 및 사이드바 설정
num_cols = list(df.select_dtypes(include="number").columns)
metric_candidates = [c for c in num_cols if c != "연도"]

if not metric_candidates:
    st.error("분석할 에버리지 또는 점수 숫자 컬럼을 찾지 못했습니다.")
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.stop()

with st.sidebar:
    st.header("⚙️ 조회 설정")

    default_metric = find_col(
        metric_candidates,
        ["에버", "avg", "average", "평균", "점수", "score", "총점"],
    )
    metric_col = st.selectbox(
        "분석할 에버리지/점수 컬럼",
        options=metric_candidates,
        index=metric_candidates.index(default_metric),
    )

    filtered_df = df.copy()

    # 2015년 이후 데이터 범위 고정 및 연도 슬라이더
    if "연도" in filtered_df.columns and filtered_df["연도"].notna().any():
        filtered_df = filtered_df[filtered_df["연도"] >= 2015].copy()

        if filtered_df.empty:
            st.warning("파일에 2015년 이후 데이터가 없습니다.")
            st.stop()

        min_year = int(filtered_df["연도"].min())
        max_year = int(filtered_df["연도"].max())

        if min_year < max_year:
            year_range = st.slider(
                "조회 연도 범위 (2015년~)",
                min_value=min_year,
                max_value=max_year,
                value=(min_year, max_year),
            )
            filtered_df = filtered_df[
                (filtered_df["연도"] >= year_range[0])
                & (filtered_df["연도"] <= year_range[1])
            ]
        else:
            st.info(f"조회 연도: {min_year}년")
    else:
        st.warning("CSV 파일에서 '연도' 컬럼을 찾지 못해 전체 기간 데이터를 표시합니다.")

    # 기수·부문 등 남아있는 범주형 컬럼이 있으면 추가 필터 제공
    cat_cols = [
        c for c in filtered_df.columns
        if c not in num_cols and 1 < filtered_df[c].nunique() <= 50
    ]
    for c_col in cat_cols[:2]:
        opts = sorted([x for x in filtered_df[c_col].dropna().unique().tolist() if str(x) != ""])
        if opts:
            sel = st.multiselect(f"{c_col} 필터", options=opts, default=opts)
            filtered_df = filtered_df[filtered_df[c_col].isin(sel)]

if filtered_df.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
    st.stop()

valid_scores = filtered_df[metric_col].dropna()
if valid_scores.empty:
    st.warning(f"'{metric_col}' 컬럼에 유효한 숫자 값이 없습니다.")
    st.stop()

# 4. 핵심 요약 지표 (KPI)
avg_val = valid_scores.mean()
max_val = valid_scores.max()
min_val = valid_scores.min()

if "연도" in filtered_df.columns and filtered_df["연도"].notna().any():
    y_start = int(filtered_df["연도"].min())
    y_end = int(filtered_df["연도"].max())
    period_label = f"{y_start}년 ~ {y_end}년" if y_start != y_end else f"{y_start}년"
    max_year_val = filtered_df.loc[valid_scores.idxmax(), "연도"]
    max_delta = f"{max_year_val}년 기록"
else:
    period_label = "전체 기간"
    max_delta = None

k1, k2, k3, k4 = st.columns(4)
k1.metric("조회 기간", period_label, delta=f"총 {len(filtered_df):,}건")
k2.metric(f"평균 ({metric_col})", f"{avg_val:.2f}")
k3.metric("최고 기록", f"{max_val:.2f}", delta=max_delta)
k4.metric("최저 기록", f"{min_val:.2f}")

st.divider()

# 5. 분석 탭 구성
tab1, tab2, tab3 = st.tabs(["📈 연도별 에버리지 추이", "📊 항목별 비교", "📋 데이터 표 & 다운로드"])

with tab1:
    if "연도" in filtered_df.columns and filtered_df["연도"].notna().any():
        yearly_df = (
            filtered_df.groupby("연도", as_index=False)[metric_col]
            .agg(평균="mean", 최고="max", 최저="min", 데이터수="count")
            .sort_values(by="연도", ascending=True)
        )
        yearly_df["평균"] = yearly_df["평균"].round(2)
        yearly_df["최고"] = yearly_df["최고"].round(2)
        yearly_df["최저"] = yearly_df["최저"].round(2)
        yearly_df["연도_표시"] = yearly_df["연도"].astype(str) + "년"

        col_chart, col_table = st.columns([3, 2])
        with col_chart:
            st.subheader(f"연도별 {metric_col} 추이 (2015년~)")
            chart_df = yearly_df.set_index("연도_표시")[["평균", "최고"]]
            st.line_chart(chart_df, use_container_width=True)

        with col_table:
            st.subheader("연도별 요약표")
            display_yearly = yearly_df[["연도_표시", "평균", "최고", "최저", "데이터수"]].rename(
                columns={"연도_표시": "연도"}
            )
            st.dataframe(display_yearly, hide_index=True, use_container_width=True)
    else:
        st.subheader(f"{metric_col} 분포")
        st.bar_chart(filtered_df[metric_col].reset_index(drop=True), use_container_width=True)

with tab2:
    if len(metric_candidates) >= 2:
        st.subheader("연도별 세부 수치 비교")
        selected_cols = st.multiselect(
            "비교할 항목 선택",
            options=metric_candidates,
            default=metric_candidates[: min(3, len(metric_candidates))],
        )
        if selected_cols and "연도" in filtered_df.columns:
            comp_df = (
                filtered_df.groupby("연도")[selected_cols]
                .mean()
                .sort_index()
            )
            comp_df.index = comp_df.index.astype(str) + "년"
            st.bar_chart(comp_df, use_container_width=True)
    else:
        st.info("비교할 수 있는 추가 숫자 컬럼이 없습니다.")

with tab3:
    st.subheader("필터링된 데이터 (팀명·선수이름 제외, 2015년 이후)")
    display_df = filtered_df.copy()
    if "연도" in display_df.columns:
        display_df = display_df.sort_values(by="연도", ascending=False)

    st.dataframe(display_df, hide_index=True, use_container_width=True)

    csv_bytes = display_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 정제된 CSV 다운로드 (2015년~)",
        data=csv_bytes,
        file_name="bowling_avg_2015_onwards.csv",
        mime="text/csv",
    )
