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
                if not
