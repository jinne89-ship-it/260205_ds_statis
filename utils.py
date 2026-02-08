import pandas as pd
import re
from typing import List, Dict

# -----------------------------
# Column utilities
# -----------------------------
def _norm_col(c: str) -> str:
    """Normalize column names: strip spaces, collapse whitespace, lower."""
    c = str(c).strip()
    c = re.sub(r"\s+", "", c)  # remove all whitespace (handles '2026예산  ' etc.)
    return c.lower()

def _pick_col(df: pd.DataFrame, candidates: List[str]) -> str | None:
    """Return actual column name in df matching any candidate (normalized)."""
    norm_map = {_norm_col(c): c for c in df.columns}
    for cand in candidates:
        key = _norm_col(cand)
        if key in norm_map:
            return norm_map[key]
    return None

def _to_number(x):
    if pd.isna(x):
        return 0.0
    s = str(x).strip()
    if s == "":
        return 0.0
    s = s.replace(",", "")
    s = re.sub(r"[^\d\.\-]", "", s)  # keep digits/dot/minus
    if s in ("", "-", ".", "-."):
        return 0.0
    try:
        return float(s)
    except:
        return 0.0

def is_blank_series(s: pd.Series) -> pd.Series:
    """NaN or empty/whitespace-only -> True"""
    return s.isna() | (s.astype(str).str.strip() == "")

# -----------------------------
# Ordering rules
# -----------------------------
def get_group_order(dept: str) -> List[str] | None:
    if dept == "교수학습개발센터":
        return ["교수", "학습", "원격", "성과·조사", "특화사업"]
    if dept == "교육혁신센터":
        return ["교과", "비교과", "전공설계", "조사·환류", "특화사업"]
    return None

def apply_group_order(df: pd.DataFrame) -> pd.DataFrame:
    """Apply categorical ordering within each department for sorting purposes."""
    out = df.copy()
    if "부서" not in out.columns or "구분" not in out.columns:
        return out

    out["구분"] = out["구분"].astype(str).str.strip()
    # We'll keep sorting at display time, but we can prep category safely
    return out

# -----------------------------
# Loading
# -----------------------------
def load_data(uploaded) -> pd.DataFrame:
    """Read CSV/XLSX and standardize to canonical columns."""
    name = getattr(uploaded, "name", "")
    if name.lower().endswith(".csv"):
        raw = pd.read_csv(uploaded, dtype=str, encoding="utf-8-sig")
    else:
        raw = pd.read_excel(uploaded, dtype=str)

    # strip header whitespace
    raw.columns = [str(c).strip() for c in raw.columns]

    # Canonical columns mapping (candidates)
    mapping_candidates: Dict[str, List[str]] = {
        "부서": ["부서", "dept", "department"],
        "구분": ["구분", "category", "group"],
        "특징": ["특징", "feature"],
        "세부과제명": ["세부과제명", "세부과제", "세부과제명칭"],
        "추진과제명": ["추진과제명", "추진과제", "추진과제명칭"],
        "사업코드": ["사업코드", "사업 코드", "code", "projectcode"],
        "사업명": ["사업명", "프로그램명", "projectname", "name"],
        "목표": ["목표", "2025목표", "2025 목표"],
        "달성": ["달성", "실적", "성과", "2025달성", "2025 달성"],
        "2025예산": ["2025예산", "2025 예산", "예산", "budget2025", "2025budget"],
        "2026목표": ["2026목표", "2026 목표", "목표2026"],
        "2026예산": ["2026예산", "2026 예산", "budget2026", "2026budget"],
        "운영": ["운영", "운영방식", "운영주기"],
        "담당자": ["담당자", "담당", "owner"],
    }

    picked = {}
    for canon, cands in mapping_candidates.items():
        col = _pick_col(raw, cands)
        if col is not None:
            picked[canon] = col

    required = ["부서", "구분", "사업코드", "사업명", "2025예산"]
    missing = [c for c in required if c not in picked]
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {missing} / 현재 컬럼: {list(raw.columns)}")

    # Build standardized DF
    df = pd.DataFrame()
    for canon, col in picked.items():
        df[canon] = raw[col]

    # Clean text
    for c in ["부서", "구분", "특징", "세부과제명", "추진과제명", "사업코드", "사업명", "목표", "달성", "2026목표", "운영", "담당자"]:
        if c in df.columns:
            df[c] = df[c].astype(str).replace({"nan": ""}).str.strip()

    # Numbers
    df["2025예산"] = df["2025예산"].apply(_to_number)
    if "2026예산" in df.columns:
        df["2026예산"] = df["2026예산"].apply(_to_number)
    else:
        df["2026예산"] = 0.0

    # If 2026목표 not present, create empty
    if "2026목표" not in df.columns:
        df["2026목표"] = ""

    # Make sure optional cols exist to simplify code
    for opt in ["특징", "세부과제명", "추진과제명", "목표", "달성", "운영", "담당자"]:
        if opt not in df.columns:
            df[opt] = ""

    return df

# -----------------------------
# Grouping logic (사업코드+사업명 기준)
# -----------------------------
def _join_unique(series: pd.Series) -> str:
    vals = []
    for v in series.dropna().astype(str).map(lambda x: x.strip()):
        if v == "" or v.lower() == "nan":
            continue
        if v not in vals:
            vals.append(v)
    return " / ".join(vals)

def group_projects(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group by (부서, 구분, 특징, 사업코드, 사업명).
    - budgets summed
    - text fields: unique-joined
    """
    gcols = ["부서", "구분", "특징", "사업코드", "사업명"]
    for c in gcols:
        if c not in df.columns:
            df[c] = ""

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

    out = (
        df.groupby(gcols, dropna=False, as_index=False)
          .agg(agg)
    )

    # compute completion rate if numeric-like (optional; we keep as reference)
    # If 목표/달성이 숫자면 계산, 아니면 NaN
    def _num_or_nan(s: str):
        s2 = str(s).strip().replace(",", "")
        if re.fullmatch(r"-?\d+(\.\d+)?", s2):
            return float(s2)
        return float("nan")

    out["목표_num"] = out["목표"].apply(_num_or_nan)
    out["달성_num"] = out["달성"].apply(_num_or_nan)
    out["2025완료율(%)"] = (out["달성_num"] / out["목표_num"] * 100).where(out["목표_num"].notna() & (out["목표_num"] != 0))
    out.drop(columns=["목표_num", "달성_num"], inplace=True)

    return out

# -----------------------------
# Aggregations for charts/tables
# -----------------------------
def budget_by_category(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return per (부서, 구분) sums + delta.
    """
    tmp = df.groupby(["부서", "구분"], as_index=False).agg({"2025예산": "sum", "2026예산": "sum"})
    tmp["예산증감(2026-2025)"] = tmp["2026예산"] - tmp["2025예산"]
    return tmp

def category_share_table(df: pd.DataFrame, year_col: str) -> pd.DataFrame:
    """
    For each dept-category: sum and share within department.
    Also add '계' row per department.
    """
    base = df.groupby(["부서", "구분"], as_index=False).agg({year_col: "sum"})
    out_rows = []
    for dept, sub in base.groupby("부서"):
        sub2 = sub.copy()
        total = float(sub2[year_col].sum())
        if total > 0:
            sub2["부서내 비율(%)"] = (sub2[year_col] / total * 100).round(1)
        else:
            sub2["부서내 비율(%)"] = 0.0

        out_rows.append(sub2)

        out_rows.append(pd.DataFrame([{
            "부서": dept,
            "구분": "계",
            year_col: total,
            "부서내 비율(%)": 100.0 if total > 0 else 0.0
        }]))

    out = pd.concat(out_rows, ignore_index=True)
    return out
