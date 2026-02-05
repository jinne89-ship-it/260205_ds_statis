import pandas as pd
import numpy as np
import re

# 표준 컬럼(앱 내부에서 이 이름으로 통일)
REQUIRED_COLS = ["부서", "구분", "사업코드", "사업명", "목표", "달성", "예산", "사용예산", "잔여예산", "담당자"]

# 업로드 파일에서 자주 발생하는 컬럼명 변형(동의어/깨짐) → 표준 컬럼명
COLUMN_ALIASES = {
    # 부서/구분
    "부서명": "부서",
    "담당부서": "부서",

    "구분": "구분",
    "분류": "구분",

    # 사업 관련
    "사업 코드": "사업코드",
    "사업코드": "사업코드",
    "사업코드 ": "사업코드",
    "사업 code": "사업코드",

    "사업 명": "사업명",
    "사업명": "사업명",

    # 목표/달성
    "목표치": "목표",
    "달성치": "달성",

    # 예산
    "총예산": "예산",
    "예 산": "예산",

    "사용 예산": "사용예산",
    "집행예산": "사용예산",
    "집행액": "사용예산",

    "잔여 예산": "잔여예산",
    "잔액": "잔여예산",

    # 담당자
    "담당": "담당자",
    "책임자": "담당자",
}

def _clean_col_name(c: str) -> str:
    """줄바꿈/따옴표/다중공백 제거 + 앞뒤 공백 제거"""
    s = str(c)
    s = s.replace("\n", "").replace("\r", "")
    s = s.replace('"', "").replace("'", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1) 기본 정리
    cleaned = {_clean_col_name(c): c for c in df.columns}  # clean->orig
    df.columns = [_clean_col_name(c) for c in df.columns]

    # 2) 대표적으로 깨지는 케이스: "사업 구분2" 같이 중간 공백이 있는 경우
    #    - 공백 제거한 버전도 매핑 후보로 사용
    col_no_space = {re.sub(r"\s+", "", c): c for c in df.columns}

    # 3) 동의어 매핑 적용
    rename_map = {}
    for c in df.columns:
        key1 = c
        key2 = re.sub(r"\s+", "", c)  # 공백 제거 버전
        # direct match
        if key1 in COLUMN_ALIASES:
            rename_map[c] = COLUMN_ALIASES[key1]
        # no-space match
        elif key2 in COLUMN_ALIASES:
            rename_map[c] = COLUMN_ALIASES[key2]

    df = df.rename(columns=rename_map)

    return df

def _to_number(series: pd.Series) -> pd.Series:
    s = series.astype(str)
    s = s.str.replace(",", "", regex=False)
    s = s.str.replace("원", "", regex=False)
    s = s.str.replace(" ", "", regex=False)
    s = pd.to_numeric(s, errors="coerce").fillna(0)
    return s

def _to_numeric_if_possible(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.replace(",", "", regex=False).str.strip()
    return pd.to_numeric(s, errors="coerce")

def load_data(uploaded_file) -> pd.DataFrame:
    if uploaded_file.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    df = canonicalize_columns(df)

    # 숫자형 변환(컬럼이 있으면만)
    for col in ["예산", "사용예산", "잔여예산"]:
        if col in df.columns:
            df[col] = _to_number(df[col])

    # 목표/달성 수치 변환(있으면만)
    if "목표" in df.columns:
        df["목표_num"] = _to_numeric_if_possible(df["목표"])
    else:
        df["목표_num"] = np.nan

    if "달성" in df.columns:
        df["달성_num"] = _to_numeric_if_possible(df["달성"])
    else:
        df["달성_num"] = np.nan

    # 필수 컬럼 체크
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        # 어떤 컬럼이 들어왔는지 같이 알려주면 수정이 빨라짐
        available = ", ".join(df.columns.tolist())
        raise ValueError(
            f"필수 컬럼이 없습니다: {missing}\n"
            f"현재 파일에 있는 컬럼: [{available}]"
        )

    # 집행률
    df["집행률"] = np.where(df["예산"] > 0, df["사용예산"] / df["예산"] * 100, np.nan)

    # 성과 자동판정
    df["달성판정"] = np.where(
        (df["목표_num"].notna()) & (df["달성_num"].notna()) & (df["목표_num"] > 0),
        np.where(df["달성_num"] >= df["목표_num"], "목표달성", "진행/보완"),
        "정성성과(확인필요)"
    )

    df["집행상태"] = np.select(
        [
            (df["예산"] == 0),
            (df["예산"] > 0) & (df["잔여예산"] == 0),
            (df["예산"] > 0) & (df["사용예산"] == 0),
        ],
        ["예산없음", "집행완료", "미집행"],
        default="부분집행"
    )

    return df

def make_kpi(df: pd.DataFrame) -> dict:
    budget_sum = float(df["예산"].sum())
    spent_sum = float(df["사용예산"].sum())
    remain_sum = float(df["잔여예산"].sum())
    execution_rate = (spent_sum / budget_sum * 100) if budget_sum > 0 else 0.0

    return {
        "n_projects": int(len(df)),
        "budget_sum": budget_sum,
        "spent_sum": spent_sum,
        "remain_sum": remain_sum,
        "execution_rate": execution_rate,
    }

def budget_by_dept_and_category(df: pd.DataFrame) -> pd.DataFrame:
    base = df.groupby(["부서", "구분"], as_index=False)["예산"].sum()
    dept_total = df.groupby("부서", as_index=False)["예산"].sum().rename(columns={"예산": "부서총예산"})
    out = base.merge(dept_total, on="부서", how="left")
    out["예산비율(%)"] = np.where(out["부서총예산"] > 0, out["예산"] / out["부서총예산"] * 100, 0)
    out = out.sort_values(["부서", "예산"], ascending=[True, False]).rename(columns={"예산": "구분예산"})
    out["구분예산"] = out["구분예산"].round(0)
    out["부서총예산"] = out["부서총예산"].round(0)
    out["예산비율(%)"] = out["예산비율(%)"].round(1)
    return out[["부서", "구분", "구분예산", "부서총예산", "예산비율(%)"]]

def program_list_by_group(dept_df: pd.DataFrame, category: str) -> pd.DataFrame:
    d = dept_df[dept_df["구분"] == category].copy()
    cols = ["사업코드", "사업명", "목표", "달성", "예산", "사용예산", "잔여예산", "집행률", "달성판정", "집행상태", "담당자"]
    for c in cols:
        if c not in d.columns:
            d[c] = np.nan
    d = d[cols].sort_values("예산", ascending=False)
    d["집행률"] = d["집행률"].round(1)
    return d

def top_programs_summary(dept_df: pd.DataFrame, top_n: int = 7):
    d = dept_df.copy()
    ach = np.where(d["달성판정"] == "목표달성", 1.0, 0.0)
    exec_rate = d["집행률"].fillna(0) / 100.0
    budget_scaled = (d["예산"] / (d["예산"].max() if d["예산"].max() > 0 else 1)).fillna(0)
    d["score"] = 0.55 * budget_scaled + 0.25 * exec_rate + 0.20 * ach
    top = d.sort_values("score", ascending=False).head(top_n)

    top_tbl = top[["구분", "사업코드", "사업명", "목표", "달성", "예산", "사용예산", "잔여예산", "집행률", "달성판정", "담당자"]].copy()
    top_tbl["집행률"] = top_tbl["집행률"].round(1)

    total_budget = dept_df["예산"].sum()
    total_spent = dept_df["사용예산"].sum()
    exec_pct = (total_spent / total_budget * 100) if total_budget > 0 else 0

    lines = []
    lines.append(f"총예산 {total_budget:,.0f}원 중 {total_spent:,.0f}원 집행(집행률 {exec_pct:.1f}%).")
    lines.append("주요 성과(자동 추천):")
    for _, r in top.iterrows():
        if pd.notna(r.get("목표_num")) and pd.notna(r.get("달성_num")) and r.get("목표_num", 0) > 0:
            perf = f"목표 {int(r['목표_num'])} 대비 달성 {int(r['달성_num'])}({r['달성판정']})"
        else:
            perf = f"{r['달성판정']}"
        lines.append(f"- [{r['구분']}] {r['사업명']} / 예산 {r['예산']:,.0f}원 / 집행률 {float(r['집행률']):.1f}% / {perf}")

    return top_tbl, "\n".join(lines)
