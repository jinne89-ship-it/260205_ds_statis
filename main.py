import streamlit as st
import pandas as pd
import altair as alt

from utils import (
    load_data,
    group_projects,
    apply_group_order,
    budget_by_category,
    budget_by_task,
    get_group_order,
)

# -----------------------------
# Money formatting helpers
# -----------------------------
def won(x) -> str:
    """123000 -> '123,000원' / NaN -> ''"""
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return ""
        v = float(x)
        if pd.isna(v):
            return ""
        return f"{int(round(v)):,.0f}원"
    except Exception:
        return ""

def won_col(df: pd.DataFrame, col: str, new_col: str = None) -> pd.DataFrame:
    """Create formatted string column for money display."""
    out = df.copy()
    if col in out.columns:
        out[new_col or col] = out[col].apply(won)
    return out

def format_money_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Format money columns in dataframe (string display)."""
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].apply(won)
    return out


st.set_page_config(page_title="2025-2026 사업(예산·목표/달성) 대시보드", layout="wide")
st.title("2025-2026 사업(예산·목표/달성) 총장보고 지원 대시보드")

st.markdown(
    """
- 업로드 양식(예): 부서, 구분, 특징, 세부과제명, 추진과제명, 사업코드, 사업명, 목표, 달성, 2025예산, 2026목표, 2026예산(선택) 등  
- 동일 사업코드+사업명은 자동으로 그룹핑(예산 합산 / 과제명은 중복 제거 후 병합)
"""
)

uploaded = st.file_uploader("데이터 파일 업로드 (CSV / XLSX)", type=["csv", "xlsx"])
if not uploaded:
    st.info("파일을 업로드하면 구분별 예산(2025-2026 비교), 목표-달성 비교, 세부/추진과제별 현황을 자동 생성합니다.")
    st.stop()

raw = load_data(uploaded)
dfg = group_projects(raw)
dfg = apply_group_order(dfg)

# -----------------------------
# Sidebar filters (연동형)
# -----------------------------
with st.sidebar:
    st.header("조회 조건")

    dept_opts = ["(전체)"] + sorted([d for d in dfg["부서"].dropna().unique().tolist() if str(d).strip() != ""])
    dept = st.selectbox("부서", dept_opts, index=0)

    base = dfg if dept == "(전체)" else dfg[dfg["부서"] == dept]

    # 구분 옵션(부서 선택에 따라 다르게) + 정렬 규칙 반영
    order = get_group_order(dept) if dept != "(전체)" else None
    if order:
        cat_opts = ["(전체)"] + [c for c in order if c in base["구분"].dropna().unique().tolist()]
    else:
        cat_opts = ["(전체)"] + sorted([c for c in base["구분"].dropna().unique().tolist() if str(c).strip() != ""])
    cat = st.selectbox("구분", cat_opts, index=0)

    base2 = base if cat == "(전체)" else base[base["구분"] == cat]
    feat_opts = ["(전체)"] + sorted([x for x in base2["특징"].dropna().unique().tolist() if str(x).strip() != ""])
    feat = st.selectbox("특징", feat_opts, index=0)

    # ✅ 그래프 금액 라벨 표시 토글(겹침이 부담될 때 끄기)
    show_labels = st.checkbox("그래프 금액 라벨 표시", value=True)

# apply filters
fdf = dfg.copy()
if dept != "(전체)":
    fdf = fdf[fdf["부서"] == dept]
if cat != "(전체)":
    fdf = fdf[fdf["구분"] == cat]
if feat != "(전체)":
    fdf = fdf[fdf["특징"] == feat]

if fdf.empty:
    st.warning("해당 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# -----------------------------
# KPI (예산 합계만) - ✅ 원화 표기
# -----------------------------
total_2025 = float(fdf["2025예산"].sum()) if "2025예산" in fdf.columns else 0.0
total_2026 = float(fdf["2026예산"].sum()) if "2026예산" in fdf.columns else 0.0
delta = total_2026 - total_2025

c1, c2, c3 = st.columns(3)
c1.metric("사업(그룹) 수", int(len(fdf)))
c2.metric("2025예산 합계", won(total_2025))
c3.metric("2026예산 합계", won(total_2026), delta=won(delta))

st.divider()

# =========================================================
# A) 구분별 2025-2026 예산 비교 (정렬 규칙 반영) + ✅ 라벨 원화
# =========================================================
st.subheader("A. 구분별 예산 비교 (2025 vs 2026)")

cat_df = budget_by_category(fdf)

dept_list = sorted([d for d in cat_df["부서"].dropna().unique().tolist() if str(d).strip() != ""])
tabs = st.tabs(dept_list) if len(dept_list) > 1 else [st.container()]

for i, d in enumerate(dept_list):
    with tabs[i] if len(dept_list) > 1 else tabs[0]:
        sub = cat_df[cat_df["부서"] == d].copy()

        # 정렬 순서 강제
        order = get_group_order(d)
        if order:
            sub["구분"] = pd.Categorical(sub["구분"], categories=order, ordered=True)
            sub = sub.sort_values("구분")
        else:
            sub = sub.sort_values("2025예산", ascending=False)

        # long format for altair grouped bar
        long = sub.melt(
            id_vars=["부서", "구분"],
            value_vars=["2025예산", "2026예산"],
            var_name="연도",
            value_name="예산"
        )
        long["예산라벨"] = long["예산"].apply(won)

        base = (
            alt.Chart(long)
            .encode(
                x=alt.X("구분:N", sort=order if order else "-y", title="구분"),
                y=alt.Y("예산:Q", title="예산"),
                color=alt.Color("연도:N"),
                tooltip=[
                    "부서:N",
                    "구분:N",
                    "연도:N",
                    alt.Tooltip("예산:Q", format=",.0f", title="예산(원)")
                ],
            )
        )

        bars = base.mark_bar()

        if show_labels:
            labels = base.mark_text(dy=-8).encode(text="예산라벨:N")
            chart = (bars + labels).properties(height=320)
        else:
            chart = bars.properties(height=320)

        st.altair_chart(chart, use_container_width=True)

        # ✅ 표 금액도 원화 표시
        sub_show = sub[["구분", "2025예산", "2026예산", "예산증감(2026-2025)"]].copy()
        sub_show = format_money_cols(sub_show, ["2025예산", "2026예산", "예산증감(2026-2025)"])
        st.dataframe(sub_show, use_container_width=True, hide_index=True)

st.divider()

# =========================================================
# B) 목표-달성 (2025) + 2025-2026 비교  + ✅ 표 금액 원화
# =========================================================
st.subheader("B. 목표-달성 현황 및 2025-2026 비교")

cols = [
    "부서", "구분", "특징",
    "세부과제명", "추진과제명",
    "사업코드", "사업명",
    "목표", "달성", "2025완료율(%)",
    "2026목표", "2026달성", "2026완료율(%)",
    "2025예산", "2026예산", "예산증감(2026-2025)",
    "담당자", "운영"
]
cols = [c for c in cols if c in fdf.columns]  # 혹시 일부 컬럼이 없을 때 방어
show = fdf[cols].copy()

if "2025완료율(%)" in show.columns:
    show["2025완료율(%)"] = pd.to_numeric(show["2025완료율(%)"], errors="coerce").round(1)
if "2026완료율(%)" in show.columns:
    show["2026완료율(%)"] = pd.to_numeric(show["2026완료율(%)"], errors="coerce").round(1)

# 테이블 정렬(부서 내 구분 순서 유지)
if dept != "(전체)":
    order = get_group_order(dept)
    if order and "구분" in show.columns:
        show["구분"] = pd.Categorical(show["구분"], categories=order, ordered=True)

sort_cols = [c for c in ["부서", "구분", "사업코드", "사업명"] if c in show.columns]
if sort_cols:
    show = show.sort_values(sort_cols, na_position="last")

# ✅ 금액 컬럼 원화 포맷
money_cols_b = [c for c in ["2025예산", "2026예산", "예산증감(2026-2025)"] if c in show.columns]
show_disp = format_money_cols(show, money_cols_b)

st.dataframe(show_disp, use_container_width=True, hide_index=True)

st.divider()

# =========================================================
# C) 세부과제명 / 세부과제명-추진과제명 기준 예산 비교 + ✅ 라벨/표 원화
# =========================================================
st.subheader("C. 세부과제명 및 세부과제명-추진과제명 예산 비교(2025 vs 2026)")

task_df = budget_by_task(fdf).copy()

# 빈 값 제거(표시 품질)
task_df = task_df[
    (task_df["세부과제명"].astype(str).str.strip() != "")
    | (task_df["추진과제명"].astype(str).str.strip() != "")
]
task_df = task_df.sort_values("2025예산", ascending=False)

top_n = st.slider("표시할 상위 항목 수(2025예산 기준)", min_value=5, max_value=50, value=15, step=5)

top_task = task_df.head(top_n).copy()
top_task["라벨"] = top_task["세부과제명"].fillna("").astype(str).str.strip()
top_task["라벨"] = top_task["라벨"].where(top_task["라벨"] != "", "(세부과제명 없음)")
top_task["라벨"] = top_task["라벨"] + " / " + top_task["추진과제명"].fillna("").astype(str).str.strip()

long2 = top_task.melt(
    id_vars=["부서", "라벨"],
    value_vars=["2025예산", "2026예산"],
    var_name="연도",
    value_name="예산"
)
long2["예산라벨"] = long2["예산"].apply(won)

base2 = (
    alt.Chart(long2)
    .encode(
        y=alt.Y("라벨:N", sort="-x", title="세부과제명 / 추진과제명"),
        x=alt.X("예산:Q", title="예산"),
        color=alt.Color("연도:N"),
        tooltip=[
            "부서:N",
            "라벨:N",
            "연도:N",
            alt.Tooltip("예산:Q", format=",.0f", title="예산(원)")
        ]
    )
)

bars2 = base2.mark_bar()

if show_labels:
    # 가로막대라 dx로 오른쪽에
    labels2 = base2.mark_text(dx=6).encode(text="예산라벨:N")
    chart2 = (bars2 + labels2).properties(height=420)
else:
    chart2 = bars2.properties(height=420)

st.altair_chart(chart2, use_container_width=True)

# ✅ 표 금액도 원화 표시
tbl = top_task[["부서", "세부과제명", "추진과제명", "2025예산", "2026예산", "예산증감(2026-2025)"]].copy()
tbl = format_money_cols(tbl, ["2025예산", "2026예산", "예산증감(2026-2025)"])
st.dataframe(tbl, use_container_width=True, hide_index=True)
