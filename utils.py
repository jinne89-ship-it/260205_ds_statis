import pandas as pd
import re
from typing import List, Dict

# =====================================================
# 공통 유틸
# =====================================================
def is_blank_series(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype(str).str.strip() == "")

# =====================================================
# 🔥 부서별 구분 정렬 규칙 (최종 확정)
# =====================================================
def get_group_order(dept: str) -> List[str] | None:
    """
    총장보고 기준 부서별 구분 순서 (최종)
    """
    if dept == "교수학습개발센터":
        return [
            "교수",
            "학습",
            "원격",
            "성과·조사",
            "특화사업",
        ]

    if dept == "교육혁신센터":
        return [
            "교과",
            "비교과",
            "전공설계",
            "조사·환류",
            "특화사업",
        ]

    return None

# =====================================================
# 데이터 로딩
# =====================================================
def load_data(uploaded):
    if uploaded.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded, dtype=str, encoding="utf-8-sig")
    else:
        df = pd.read_excel(uploaded, dtype=str)

    df.columns = df.columns.str.strip()

    def to_num(x):
        if pd.isna(x):
            return 0.0
        s = str(x).replace(",", "").replace("원", "").strip()
        return float(s) if s.replace(".", "", 1).isdigit() else 0.0

    for col in ["2025예산", "2026예산"]:
        if col in df.columns:
            df[col] = df[col].apply(to_num)
        else:
            df[col] = 0.0

    for col in [
        "부서", "구분", "특징", "세부과제명", "추진과제명",
        "사업코드", "사업명", "목표", "달성", "2026목표",
        "운영", "담당자"
    ]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].astype(str).str.strip()

    return df

# =====================================================
# 사업코드+사업명 기준 그룹핑
# =====================================================
def _join_unique(s: pd.Series) -> str:
    vals = []
    for v in s.dropna().astype(str):
        v = v.strip()
        if v and v not in vals:
            vals.append(v)
    return " / ".join(vals)

def group_projects(df: pd.DataFrame) -> pd.DataFrame:
    gcols = ["부서", "구분", "특징", "사업코드", "사업명"]

    agg = {
        "2025예산": "sum",
        "2026예산": "sum",
        "세부과제명": _join_unique,
        "추진과제명": _join_unique,
        "목표": _join_unique,
        "달성": _join_unique,
        "2026목표": _join_unique,
        "운영": _join_unique,
        "담당자": _join_unique,
    }

    return (
        df.groupby(gcols, dropna=False, as_index=False)
          .agg(agg)
    )

# =====================================================
# 비교용 집계
# =====================================================
def budget_by_category(df: pd.DataFrame) -> pd.DataFrame:
    out = (
        df.groupby(["부서", "구분"], as_index=False)
          .agg({"2025예산": "sum", "2026예산": "sum"})
    )
    out["예산증감(2026-2025)"] = out["2026예산"] - out["2025예산"]
    return out
