from pathlib import Path
import re
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="KPBA 볼링 에버리지 분석",
    page_icon="🎳",
    layout="wide",
)

TEXT_COL_KEYWORDS = ["선수", "이름", "성명", "기수", "소속", "팀", "회원", "name", "team"]
HEADER_KEYWORDS = ["순위", "선수", "이름", "성명", "기수", "소속", "게임", "총점", "에버", "평균", "avg"]


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """빈 행/열을 제거하고 선수명·기수 등 텍스트 컬럼을 유지하면서 점수 컬럼을 숫자로 변환합니다."""
    df = df.dropna(how="all").dropna(axis=1, how="all").copy()
    df.columns = [str(col).strip() for col in df.columns]

    for col in df.columns:
        col_lower = col.lower()
        is_text_col = any(kw in col_lower for kw in TEXT_COL_KEYWORDS)

        if is_text_col:
            df[col] = df[col].fillna("").astype(str).str.strip()
            continue

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

    # 총점과 게임수가 있고 에버리지 컬럼이 없으면 자동 계산
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
                df = pd.read_csv(file_path, encoding=enc, sep=sep)
                if len(df.columns) == 1 and any(s in str(df.columns[0]) for s in [",", "\t", ";"]):
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
        for sep in [",", "\t", ";"]:
            try:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding=enc, sep=sep)
                if len(df.columns) == 1 and any(s in str(df.columns[0]) for s in [",", "\t", ";"]):
                    continue
                if not df.empty:
                    return clean_dataframe(df), None
            except Exception as e:
                last_error = e
    return None, last_error


def parse_kpba_raw_text(raw_text: str):
    """KPBA 웹사이트나 엑셀에서 복사해 붙여넣은 표 텍스트를 DataFrame으로 변환합니다."""
    lines = [line.strip() for line in raw_text.strip().splitlines() if line.strip()]
    if not lines:
        return None, "입력된 내용이 없습니다."

    rows = []
    for line in lines:
        if "\t" in line:
            parts = [p.strip() for p in line.split("\t")]
        elif "," in line:
            parts = [p.strip() for p in line.split(",")]
        else:
            parts = [p.strip() for p in re.split(r"\s{2,}|\s+", line) if p.strip()]
        rows.append(parts)

    max_cols = max(len(r) for r in rows)
    if max_cols < 2:
        return None, "열(컬럼)을 구분할 수 없습니다. 탭, 쉼표 또는 공백으로 구분된 표 데이터를 붙여넣어 주세요."

    # 행마다 열 개수가 다를 경우 빈 칸으로 패딩
    padded_rows = [r + [""] * (max_cols - len(r)) for r in rows]

    first_row_text = " ".join(padded_rows[0]).lower()
    has_header = any(kw in first_row_text for kw in HEADER_KEYWORDS)

    if has_header:
        headers = [h if h else f"컬럼{i+1}" for i, h in enumerate(padded_rows[0])]
        data_rows = padded_rows[1:]
    else:
        default_headers_map = {
            2: ["선수명", "에버리지"],
            3: ["순위", "선수명", "에버리지"],
            4: ["순위", "기수", "선수명", "에버리지"],
            5: ["순위", "기수", "선수명", "게임수", "에버리지"],
            6: ["순위", "기수", "선수명", "소속", "게임수", "에버리지"],
            7: ["순위", "기수", "선수명", "소속", "게임수", "총점", "에버리지"],
        }
        headers = default_headers_map.get(
            max_cols, [f"컬럼{i+1}" for i in range(max_cols)]
        )
        data_rows = padded_rows

    if not data_rows:
        return None, "헤더 외에 데이터 행이 없습니다."

    df = pd.DataFrame(data_rows, columns=headers)
    return clean_dataframe(df), None


def get_sample_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "순위": [1, 2, 3, 4, 5, 6, 7, 8],
            "기수": ["25기", "9기", "14기", "3기", "18기", "11기", "15기", "22기"],
            "선수명": ["김태영", "박경신", "최원영", "정태화", "강희원", "김수진", "윤여진", "이명훈"],
            "소속": ["팀스톰", "팀브런스윅", "팀에보나이트", "DSD", "팀햄머", "팀로또그립", "팀모티브", "팀트랙"],
            "게임수": [36, 42, 36, 30, 24, 30, 36, 30],
            "총점": [7632, 8736, 7452, 6150, 4920, 6030, 7164, 5940],
            "에버리지": [212.0, 208.0, 207.0, 205.0, 205.0, 201.0, 199.0, 198.0],
        }
    )


def find_col(columns, keywords, fallback_idx=0):
    for kw in keywords:
        for col in columns:
            if kw in col.lower():
                return col
    return columns[fallback_idx] if columns else None


# 1. 저장소 내 CSV 파일 탐색
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

# 2. 메인 타이틀 및 데이터 입력/변환 패널
st.title("🎳 KPBA 볼링 에버리지 분석 대시보드")

with st.expander("📂 데이터 불러오기 / KPBA 표 텍스트 CSV 변환기", expanded=(df is None)):
    input_tab1, input_tab2 = st.tabs(["📁 CSV 파일 업로드", "📋 KPBA 원본 표 붙여넣기 (자동 CSV 변환)"])

    with input_tab1:
        uploaded_file = st.file_uploader(
            "컴퓨터에 있는 bowling_avg.csv 파일을 업로드하세요.",
            type=["csv", "txt"],
        )
        if uploaded_file is not None:
            up_df, up_err = load_csv_from_upload(uploaded_file)
            if up_df is not None:
                df = up_df
                loaded_source = f"업로드 파일: {uploaded_file.name}"
            else:
                st.error(f"파일을 읽지 못했습니다: {up_err}")

    with input_tab2:
        st.caption("KPBA 홈페이지 기록실이나 엑셀에서 표 내용을 드래그·복사(Ctrl+C)한 뒤 아래에 붙여넣으세요.")
        pasted_text = st.text_area(
            "KPBA 표 데이터 붙여넣기",
            height=160,
            placeholder="예시:\n순위\t기수\t선수명\t소속\t게임수\t총점\t에버리지\n1\t25기\t김태영\t팀스톰\t36\t7632\t212.0",
        )
        if pasted_text.strip():
            parsed_df, parse_err = parse_kpba_raw_text(pasted_text)
            if parsed_df is not None:
                df = parsed_df
                loaded_source = "직접 붙여넣은 KPBA 데이터 (변환 완료)"
                st.success("KPBA 데이터 변환 완료! 아래 대시보드에서 바로 분석하거나 CSV로 다운로드할 수 있습니다.")
            else:
                st.error(f"변환 오류: {parse_err}")

if df is None:
    st.info(
        "현재 `data/bowling_avg.csv` 파일이 없어 **샘플 데이터**로 화면을 표시 중입니다. "
        "위 패널에서 CSV 파일을 업로드하거나 KPBA 표 데이터를 붙여넣어 보세요."
    )
    if file_error:
        st.caption(f"파일 확인 참고: {file_error}")
    df = get_sample_data()
else:
    st.caption(f"적용된 데이터: `{loaded_source}` ({len(df):,}행 × {len(df.columns)}열)")

# 3. 컬럼 자동 매핑 및 사이드바 필터
all_cols = list(df.columns)
num_cols = list(df.select_dtypes(include="number").columns)
cat_cols = [c for c in all_cols if c not in num_cols]

if not num_cols:
    st.error("에버리지나 점수로 사용할 숫자형 컬럼을 찾지 못했습니다. 데이터 형식을 확인해 주세요.")
    st.dataframe(df, use_container_width=True)
    st.stop()

with st.sidebar:
    st.header("⚙️ 분석 설정")

    default_name = find_col(
        cat_cols if cat_cols else all_cols,
        ["선수", "이름", "성명", "회원", "name", "player"],
    )
    name_col = st.selectbox(
        "선수명 기준 컬럼",
        options=all_cols,
        index=all_cols.index(default_name),
    )

    default_metric = find_col(
        num_cols,
        ["에버", "avg", "average", "평균", "점수", "score", "총점"],
    )
    metric_col = st.selectbox(
        "에버리지/점수 기준 컬럼",
        options=num_cols,
        index=num_cols.index(default_metric),
    )

    filtered_df = df.copy()

    # 기수, 소속 등 그룹 필터 자동 생성
    group_cols = [
        c for c in cat_cols
        if c != name_col and 1 < df[c].nunique() <= 60
    ]
    for g_col in group_cols[:2]:
        options = sorted([x for x in df[g_col].dropna().unique().tolist() if str(x) != ""])
        if options:
            selected = st.multiselect(f"{g_col} 필터", options=options, default=options)
            filtered_df = filtered_df[filtered_df[g_col].isin(selected)]

    # 게임수 기준 슬라이더
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
    st.warning("선택한 필터 조건에 해당하는 선수가 없습니다.")
    st.stop()

valid_scores = filtered_df[metric_col].dropna()
if valid_scores.empty:
    st.warning(f"'{metric_col}' 컬럼에 유효한 숫자 값이 없습니다.")
    st.stop()

# 4. 핵심 요약 지표 (KPI)
avg_val = valid_scores.mean()
max_val = valid_scores.max()
min_val = valid_scores.min()
top_player = filtered_df.loc[valid_scores.idxmax(), name_col]

k1, k2, k3, k4 = st.columns(4)
k1.metric("조회 인원", f"{len(filtered_df):,}명")
k2.metric(f"전체 평균 ({metric_col})", f"{avg_val:.2f}")
k3.metric("최고 기록", f"{max_val:.2f}", delta=f"1위: {top_player}")
k4.metric("최저 기록", f"{min_val:.2f}")

st.divider()

# 5. 분석 탭 구성
tab1, tab2, tab3 = st.tabs(["🏆 순위 및 에버리지 차트", "📊 항목별 비교", "📋 전체 데이터 & CSV 저장"])

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
    ranking_df[metric_col] = ranking_df[metric_col].round(2)

    max_n = len(ranking_df)
    top_n = st.slider(
        "차트에 표시할 상위 인원 수",
        min_value=1,
        max_value=max(1, max_n),
        value=min(20, max_n),
    )
    top_df = ranking_df.head(top_n)

    col_chart, col_table = st.columns([3, 2])
    with col_chart:
        st.subheader(f"상위 {len(top_df)}명 {metric_col}")
        if name_col != metric_col:
            st.bar_chart(top_df.set_index(name_col)[[metric_col]])
        else:
            st.bar_chart(top_df[[metric_col]])

    with col_table:
        st.subheader("순위표")
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
    search_kw = st.text_input("검색어 입력", placeholder="선수명, 기수, 소속 검색")
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
        label="📥 bowling_avg.csv 파일로 다운로드",
        data=csv_bytes,
        file_name="bowling_avg.csv",
        mime="text/csv",
    )
