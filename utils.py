import pandas as pd
import numpy as np

REQUIRED_COLS = ["부서", "구분", "사업코드", "사업명", "목표", "달성", "예산", "사용예산", "잔여예산", "담당자"]

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # 공백/개행/따옴표 등 정리
    df = df.copy()
    df.columns = [str(c).strip().replace("\n", "").replace("\r", "") for c in df.columns]

    # 흔한 변형 컬럼명 보정(필요시 추가)
    rename_map = {
        "사용 예산": "사용예산",
        "잔여 예산": "잔여예산",
        "사업 코드": "사업코드",
        "사업 명": "사업명",
    }
    for k, v in rename_map.items():
        if k in df.columns and v not in df.columns:
            df = df.rename(columns={k: v})
    return df

def _to_number(series: pd.Series) -> pd.Series:
    # "1,234,000", "2000000원" 등 처리
    s = series.astype(str).str.replace(",", "", regex=False)
    s = s.str.replace("원", "", regex=False).str.strip()
    s = pd.to_numeric(s, errors="coerce")
    return s.fillna(0)

def _to_numeric_if_possible(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.replace(",", "", regex=False).str.strip()
    s = pd.to_numeric(s, errors="coerce")
    return s

def load_data(uploaded_file) -> pd.DataFrame:
    if uploaded_file.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    df = _normalize_columns(df)

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {missing}")

    # 숫자형 정리
    for col in ["예산", "사용예산", "잔여예산"]:
        df[col] = _to_number(df[col])

    # 목표/달성은 숫자면 수치로, 아니면 NaN 유지
    df["목표_num"] = _to_numeric_if_possible(df["목표"])
    df["달성_num"] = _to_numeric_if_possible(df["달성"])

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
        [
            "예산없음",
            "집행완료",
            "미집행",
        ],
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
    out = out.sort_values(["부서", "예산"], ascending=[True, False])

    out = out.rename(columns={"예산": "구분예산"})
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

    # 보기 좋게 포맷용 라운딩
    d["집행률"] = d["집행률"].round(1)
    return d

def top_programs_summary(dept_df: pd.DataFrame, top_n: int = 7):
    d = dept_df.copy()

    # 우선순위 점수: 예산(가중) + 달성판정(가중) + 집행률(가중)
    ach = np.where(d["달성판정"] == "목표달성", 1.0, 0.0)
    exec_rate = d["집행률"].fillna(0) / 100.0
    budget_scaled = (d["예산"] / (d["예산"].max() if d["예산"].max() > 0 else 1)).fillna(0)

    d["score"] = 0.55 * budget_scaled + 0.25 * exec_rate + 0.20 * ach
    top = d.sort_values("score", ascending=False).head(top_n)

    top_tbl = top[["구분", "사업코드", "사업명", "목표", "달성", "예산", "사용예산", "잔여예산", "집행률", "달성판정", "담당자"]].copy()
    top_tbl["집행률"] = top_tbl["집행률"].round(1)

    # 총장 보고용 서술문 생성
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

    narrative = "\n".join(lines)
    return top_tbl, narrative
