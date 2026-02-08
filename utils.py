import pandas as pd
import numpy as np
import re

# -----------------------------
# Category Orders
# -----------------------------
ORDER_CTL = ["교수", "학습", "원격", "조사", "기타"]
ORDER_EIC = ["교과", "비교과", "전공설계", "조사·모니터링단", "기타"]

def get_group_order(dept: str):
    if dept and "교수학습개발센터" in dept:
        return ORDER_CTL
    if dept and "교육혁신센터" in dept:
        return ORDER_EIC
    return None

# -----------------------------
# Column cleaning / aliasing
# -----------------------------
def _clean_col_name(c: str) -> str:
    s = str(c)
    s = s.replace("\n", "").replace("\r", "")
    s = s.replace('"', "").replace("'", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s

COLUMN_ALIASES = {
    # budgets
    "2025 예산": "2025예산",
    "2025예산": "2025예산",
    "25예산": "2025예산",
    "2026 예산": "2026예산",
    "2026예산": "2026예산",
    "26예산": "2026예산",

    # optional achievement/target in 2026
    "2026 목표": "2026목표",
    "2026목표": "2026목표",
    "2026 달성": "2026달성",
    "2026달성": "2026달성",

    # tasks
    "세부 과제명": "세부과제명",
    "세부과제명": "세부과제명",
    "추진 과제명": "추진과제명",
    "추진과제명": "추진과제명",
}

def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [_clean_col_name(c) for c in df.columns]

    # also try no-space matching
    rename_map = {}
    for c in df.columns:
        c_ns = re.sub(r"\s+", "", c)
        if c in COLUMN_ALIASES:
            rename_map[c] = COLUMN_ALIASES[c]
        elif c_ns in COLUMN_ALIASES:
            rename_map[c] = COLUMN_ALIASES[c_ns]
    df = df.rename(columns=rename_map)
    return df

# -----------------------------
# Type helpers
# -----------------------------
def _to_number(series: pd.Series) -> pd.Series:
    s = series.astype(str)
    s = s.str.replace(",", "", regex=False)
    s = s.str.replace("원", "", regex=False)
    s = s.str.strip()
    return pd.to_numeric(s, errors="coerce").fillna(0)

def _to_numeric_or_nan(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.replace(",", "", regex=False).str.strip()
    return pd.to_numeric(s, errors="coerce")

def _uniq_join(series: pd.Series, sep=" · ") -> str:
    vals = [str(x).strip() for x in series.dropna().tolist() if str(x).strip() != ""]
    if not vals:
        return ""
    # preserve order while unique
    seen = set()
    out = []
    for v in vals:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return sep.join(out)

# -----------------------------
# Load
# -----------------------------
REQUIRED_COLS = ["부서", "구분", "사업코드", "사업명", "2025예산"]

OPTIONAL_COLS = [
    "특징", "세부과제명", "추진과제명", "목표", "달성",
    "2026목표", "2026달성",
    "사업구분", "사업운영", "세목코드", "세목명", "운영", "담당자"
]

def load_data(uploaded_file) -> pd.DataFrame:
    if uploaded_file.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    df = canonicalize_columns(df)

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        available = ", ".join(df.columns.tolist())
        raise ValueError(
            f"필수 컬럼이 없습니다: {missing}\n"
            f"현재 파일에 있는 컬럼: [{available}]"
        )

    # ensure optional cols exist
    for c in OPTIONAL_COLS:
        if c not in df.columns:
            df[c] = np.nan

    # numeric budgets
    df["2025예산"] = _to_number(df["2025예산"])
    if "2026예산" in df.columns:
        df["2026예산"] = _to_number(df["2026예산"])
    else:
        df["2026예산"] = 0

    # numeric targets/achievements when possible
    df["_목표_num"] = _to_numeric_or_nan(df["목표"])
    df["_달성_num"] = _to_numeric_or_nan(df["달성"])
    df["_2026목표_num"] = _to_numeric_or_nan(df["2026목표"])
    df["_2026달성_num"] = _to_numeric_or_nan(df["2026달성"])

    # clean text columns
    for c in ["부서", "구분", "특징", "세부과제명", "추진과제명", "사업코드", "사업명", "담당자"]:
        df[c] = df[c].astype(str).replace("nan", "").str.strip()

    return df

# -----------------------------
# Grouping: 사업코드+사업명 동일하면 합치기
# -----------------------------
def group_projects(df: pd.DataFrame) -> pd.DataFrame:
    gcols = ["부서", "구분", "특징", "사업코드", "사업명"]

    agg = {
        "2025예산": "sum",
        "2026예산": "sum",
        # task names -> unique join
        "세부과제명": lambda s: _uniq_join(s),
        "추진과제명": lambda s: _uniq_join(s),
        "담당자": lambda s: _uniq_join(s),
        "운영": lambda s: _uniq_join(s),
        "사업구분": lambda s: _uniq_join(s),
        "사업운영": lambda s: _uniq_join(s),
        "세목코드": lambda s: _uniq_join(s),
        "세목명": lambda s: _uniq_join(s),
    }

    # 목표/달성은 숫자면 합산, 아니면 텍스트 유지
    agg["_목표_num"] = "sum"
    agg["_달성_num"] = "sum"
    agg["_2026목표_num"] = "sum"
    agg["_2026달성_num"] = "sum"

    # 텍스트 목표/달성(원문)도 남겨두되, 여러 개면 합쳐 표시
    agg["목표"] = lambda s: _uniq_join(s)
    agg["달성"] = lambda s: _uniq_join(s)
    agg["2026목표"] = lambda s: _uniq_join(s)
    agg["2026달성"] = lambda s: _uniq_join(s)

    out = df.groupby(gcols, as_index=False).agg(agg)

    # 완료율(숫자형일 때만)
    out["2025완료율(%)"] = np.where(out["_목표_num"] > 0, out["_달성_num"] / out["_목표_num"] * 100, np.nan)
    out["2026완료율(%)"] = np.where(out["_2026목표_num"] > 0, out["_2026달성_num"] / out["_2026목표_num"] * 100, np.nan)

    # 예산 증감
    out["예산증감(2026-2025)"] = out["2026예산"] - out["2025예산"]

    return out

# -----------------------------
# Ordering helper (구분 정렬 규칙)
# -----------------------------
def apply_group_order(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # dept별로 다른 순서 적용: dept 단위로 카테고리 캐스팅 후 concat
    parts = []
    for dept, sub in df.groupby("부서", dropna=False):
        order = get_group_order(dept)
        if order:
            sub["구분"] = pd.Categorical(sub["구분"], categories=order, ordered=True)
            sub = sub.sort_values(["구분", "사업코드", "사업명"], na_position="last")
        else:
            sub = sub.sort_values(["구분", "사업코드", "사업명"], na_position="last")
        parts.append(sub)

    out = pd.concat(parts, ignore_index=True)
    return out

# -----------------------------
# Summary tables for charts
# -----------------------------
def budget_by_category(df_grouped: pd.DataFrame) -> pd.DataFrame:
    out = df_grouped.groupby(["부서", "구분"], as_index=False)[["2025예산", "2026예산"]].sum()
    out["예산증감(2026-2025)"] = out["2026예산"] - out["2025예산"]
    return out

def budget_by_task(df_grouped: pd.DataFrame) -> pd.DataFrame:
    out = df_grouped.groupby(["부서", "세부과제명", "추진과제명"], as_index=False)[["2025예산", "2026예산"]].sum()
    out["예산증감(2026-2025)"] = out["2026예산"] - out["2025예산"]
    return out


def won(x) -> str:
    try:
        v = float(x)
        if pd.isna(v):
            return ""
        return f"{int(round(v)):,.0f}원"
    except Exception:
        return ""
