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
    """123000000 -> '123,000,000원' / NaN -> ''"""
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return ""
        v = float(x)
        if pd.isna(v):
            return ""
        return f"{int(round(v)):,.0f}원"
    except Exception:
        return ""

def format_money_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Format money columns as won strings for display tables."""
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].apply(won)
    return out


# -----------------------------
# Page
# -----------------------------
st.set_page_config(page_title="2025-2026 사업(예산·목표/달성) 대시보드", layout="wide")
st.title("2025-2026 사업(예산·목표/달성) 총장보고 지원 대시보드")

st.markdown(
    """
- 업로드 양식(예): 부서, 구분, 특징, 세부과제명, 추진과제명, 사업코드, 사업명, 목표, 달성, 2025예산, 2026목표, 2026예산(선택)
- 동일 **사업코드+사업명**은 자동으로 그룹핑(예산 합산 / 과제명은 중복 제거 후 병합)
- 보고 흐름: **2025 사업(성과 중심) → 2026 사업(계획) → 2025-2026 비교(변화 설명)**
"""
)

uploaded = st.file_uploader("데이터 파일 업로드 (CSV / XLSX)", type=["csv", "xlsx"])
if not uploaded:
    st.info("파일을 업로드하면 2025 집중 분석(예산/목표-달성/과제별) 후, 2026 계획 및 2025-2026 비교를 자동 생성합니다.")
    st.stop()

# -----------------------------
# Load & Group
# -----------------------------
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

    order = get_group_order(dept) if dept != "(전체)" else None
    if order:
        cat_opts = ["(전체)"] + [c for c in order if c in base["구분"].dropna().unique().tolist()]
    else:
        cat_opts = ["(전체)"] + sorted([c for c in base["구분"].dropna().unique().tolist() if str(c).strip() != ""])
    cat = st.selectbox("구분", cat_opts, index=0)

    base2 = base if cat == "(전체)" else base[base["구분"] == cat]
    feat_opts = ["(전체)"] + sorted([x for x in base2["특징"].dropna().unique().tolist() if str(x).strip() != ""])
    feat = st.selectbox("특징", feat_opts, index=0)

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
# KPI (2025 중심 + 2026 참고)
# -----------------------------
total_2025 = float(fdf["2025예산"].sum()) if "2025예산" in fdf.columns else 0.0
total_2026 = float(fdf["2026예산"].sum()) if "2026예산" in fdf.columns else 0.0

c1, c2, c3 = st.columns(3)
c1.metric("사업(그룹) 수", int(len(fdf)))
c2.metric("2025 예산 총액", won(total_2025))
c3.metric("2026 예산 총액(참고)", won(total_2026))

st.divider()

# =========================================================
# 1) 2025 사업 집중 분석 (상단)
# =========================================================
st.header("Ⅰ. 2025 사업(성과 중심) 집중 분석")

# ---------------------------------------------------------
# A-1) 2025 구분별 예산 구조
# ---------------------------------------------------------
st.subheader("A-1. 2025 구분별 예산 구조")

cat_2025 = (
    fdf.groupby(["부서", "구분"], as_index=False)["2025예산"]
    .sum()
)

dept_list_2025 = sorted([d for d in cat_2025["부서"].dropna().unique().tolist() if str(d).strip() != ""])
tabs_2025 = st.tabs(dept_list_2025) if len(dept_list_2025) > 1 else [st.container()]

for i, d in enumerate(dept_list_2025):
    with tabs_2025[i] if len(dept_list_2025) > 1 else tabs_2025[0]:
        sub = cat_2025[cat_2025["부서"] == d].copy()

        order = get_group_order(d)
        if order:
            sub["구분"] = pd.Categorical(sub["구분"], categories=order, ordered=True)
            sub = sub.sort_values("구분")
        else:
            sub = sub.sort_values("2025예산", ascending=False)

        sub["예산라벨"] = sub["2025예산"].apply(won)

        base = alt.Chart(sub).encode(
            x=alt.X("구분:N", sort=order if order else "-y", title="구분"),
            y=alt.Y("2025예산:Q", title="2025 예산"),
            tooltip=[
                "부서:N",
                "구분:N",
                alt.Tooltip("2025예산:Q", format=",.0f", title="예산(원)")
            ],
        )

        bars = base.mark_bar()

        if show_labels:
            labels = base.mark_text(dy=-8).encode(text="예산라벨:N")
            chart = (bars + labels).properties(height=320)
        else:
            chart = bars.properties(height=320)

        st.altair_chart(chart, use_container_width=True)

        sub_tbl = format_money_cols(sub[["구분", "2025예산"]], ["2025예산"])
        st.dataframe(sub_tbl, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------
# A-2) 2025 목표-달성(완료율) 현황
# ---------------------------------------------------------
st.subheader("A-2. 2025 목표–달성(완료율) 현황")

cols_2025 = [
    "부서", "구분", "특징",
    "세부과제명", "추진과제명",
    "사업코드", "사업명",
    "목표", "달성", "2025완료율(%)",
    "2025예산",
    "담당자", "운영"
]
cols_2025 = [c for c in cols_2025 if c in fdf.columns]
tbl_2025 = fdf[cols_2025].copy()

if "2025완료율(%)" in tbl_2025.columns:
    tbl_2025["2025완료율(%)"] = pd.to_numeric(tbl_2025["2025완료율(%)"], errors="coerce").round(1)

# 정렬(부서 내 구분 순서 유지)
if dept != "(전체)":
    od = get_group_order(dept)
    if od and "구분" in tbl_2025.columns:
        tbl_2025["구분"] = pd.Categorical(tbl_2025["구분"], categories=od, ordered=True)

sort_cols = [c for c in ["부서", "구분", "사업코드", "사업명"] if c in tbl_2025.columns]
if sort_cols:
    tbl_2025 = tbl_2025.sort_values(sort_cols, na_position="last")

tbl_2025_disp = format_money_cols(tbl_2025, ["2025예산"] if "2025예산" in tbl_2025.columns else [])
st.dataframe(tbl_2025_disp, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------
# A-3) 2025 세부과제/추진과제 예산 집중도
# ---------------------------------------------------------
st.subheader("A-3. 2025 세부과제·추진과제별 예산 집중도(Top-N)")

task_df = budget_by_task(fdf).copy()
# 빈 값 제거(표시 품질)
task_df = task_df[
    (task_df["세부과제명"].astype(str).str.strip() != "")
    | (task_df["추진과제명"].astype(str).str.strip() != "")
].copy()

task_df = task_df.sort_values("2025예산", ascending=False)

top_n = st.slider("표시할 상위 항목 수(2025예산 기준)", min_value=5, max_value=50, value=15, step=5)
top_task = task_df.head(top_n).copy()

top_task["라벨"] = top_task["세부과제명"].fillna("").astype(str).str.strip()
top_task["라벨"] = top_task["라벨"].where(top_task["라벨"] != "", "(세부과제명 없음)")
top_task["라벨"] = top_task["라벨"] + " / " + top_task["추진과제명"].fillna("").astype(str).str.strip()
top_task["예산라벨"] = top_task["2025예산"].apply(won)

base3 = (
    alt.Chart(top_task)
    .encode(
        y=alt.Y("라벨:N", sort="-x", title="세부과제명 / 추진과제명"),
        x=alt.X("2025예산:Q", title="2025 예산"),
        tooltip=[
            "부서:N",
            alt.Tooltip("2025예산:Q", format=",.0f", title="예산(원)")
        ],
    )
)

bars3 = base3.mark_bar()

if show_labels:
    labels3 = base3.mark_text(dx=6).encode(text="예산라벨:N")
    chart3 = (bars3 + labels3).properties(height=420)
else:
    chart3 = bars3.properties(height=420)

st.altair_chart(chart3, use_container_width=True)

tbl_task_2025 = top_task[["부서", "세부과제명", "추진과제명", "2025예산"]].copy()
tbl_task_2025 = format_money_cols(tbl_task_2025, ["2025예산"])
st.dataframe(tbl_task_2025, use_container_width=True, hide_index=True)

st.divider()

# =========================================================
# 2) 2026 사업 보고(계획) (아래)
# =========================================================
st.header("Ⅱ. 2026 사업(계획) 보고")

# ---------------------------------------------------------
# B-1) 2026 구분별 예산 구조(계획)
# ---------------------------------------------------------
st.subheader("B-1. 2026 구분별 예산 구조(계획)")

cat_2026 = (
    fdf.groupby(["부서", "구분"], as_index=False)["2026예산"]
    .sum()
)

dept_list_2026 = sorted([d for d in cat_2026["부서"].dropna().unique().tolist() if str(d).strip() != ""])
tabs_2026 = st.tabs(dept_list_2026) if len(dept_list_2026) > 1 else [st.container()]

for i, d in enumerate(dept_list_2026):
    with tabs_2026[i] if len(dept_list_2026) > 1 else tabs_2026[0]:
        sub = cat_2026[cat_2026["부서"] == d].copy()

        order = get_group_order(d)
        if order:
            sub["구분"] = pd.Categorical(sub["구분"], categories=order, ordered=True)
            sub = sub.sort_values("구분")
        else:
            sub = sub.sort_values("2026예산", ascending=False)

        sub["예산라벨"] = sub["2026예산"].apply(won)

        base = alt.Chart(sub).encode(
            x=alt.X("구분:N", sort=order if order else "-y", title="구분"),
            y=alt.Y("2026예산:Q", title="2026 예산(계획)"),
            tooltip=[
                "부서:N",
                "구분:N",
                alt.Tooltip("2026예산:Q", format=",.0f", title="예산(원)")
            ],
        )

        bars = base.mark_bar()

        if show_labels:
            labels = base.mark_text(dy=-8).encode(text="예산라벨:N")
            chart = (bars + labels).properties(height=320)
        else:
            chart = bars.properties(height=320)

        st.altair_chart(chart, use_container_width=True)

        sub_tbl = format_money_cols(sub[["구분", "2026예산"]], ["2026예산"])
        st.dataframe(sub_tbl, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------
# B-2) 2026 목표(가능 시) / 사업 리스트(계획)
# ---------------------------------------------------------
st.subheader("B-2. 2026 사업 리스트(계획)")

cols_2026 = [
    "부서", "구분", "특징",
    "세부과제명", "추진과제명",
    "사업코드", "사업명",
    "2026목표", "2026달성", "2026완료율(%)",
    "2026예산",
    "담당자", "운영"
]
cols_2026 = [c for c in cols_2026 if c in fdf.columns]
tbl_2026 = fdf[cols_2026].copy()

if "2026완료율(%)" in tbl_2026.columns:
    tbl_2026["2026완료율(%)"] = pd.to_numeric(tbl_2026["2026완료율(%)"], errors="coerce").round(1)

# 정렬(부서 내 구분 순서 유지)
if dept != "(전체)":
    od = get_group_order(dept)
    if od and "구분" in tbl_2026.columns:
        tbl_2026["구분"] = pd.Categorical(tbl_2026["구분"], categories=od, ordered=True)

sort_cols = [c for c in ["부서", "구분", "사업코드", "사업명"] if c in tbl_2026.columns]
if sort_cols:
    tbl_2026 = tbl_2026.sort_values(sort_cols, na_position="last")

tbl_2026_disp = format_money_cols(tbl_2026, ["2026예산"] if "2026예산" in tbl_2026.columns else [])
st.dataframe(tbl_2026_disp, use_container_width=True, hide_index=True)

st.divider()

# =========================================================
# 3) 2025-2026 비교(변화 설명) (맨 아래)
# =========================================================
st.header("Ⅲ. 2025 → 2026 비교(예산/목표-달성 변화)")

# ---------------------------------------------------------
# C-1) 구분별 예산 비교 (2025 vs 2026)
# ---------------------------------------------------------
st.subheader("C-1. 구분별 예산 비교 (2025 vs 2026)")

cat_df = budget_by_category(fdf)

dept_list = sorted([d for d in cat_df["부서"].dropna().unique().tolist() if str(d).strip() != ""])
tabs = st.tabs(dept_list) if len(dept_list) > 1 else [st.container()]

for i, d in enumerate(dept_list):
    with tabs[i] if len(dept_list) > 1 else tabs[0]:
        sub = cat_df[cat_df["부서"] == d].copy()

        order = get_group_order(d)
        if order:
            sub["구분"] = pd.Categorical(sub["구분"], categories=order, ordered=True)
            sub = sub.sort_values("구분")
        else:
            sub = sub.sort_values("2025예산", ascending=False)

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

        sub_show = sub[["구분", "2025예산", "2026예산", "예산증감(2026-2025)"]].copy()
        sub_show = format_money_cols(sub_show, ["2025예산", "2026예산", "예산증감(2026-2025)"])
        st.dataframe(sub_show, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------
# C-2) 목표-달성(2025) + 2025-2026 비교 테이블
# ---------------------------------------------------------
st.subheader("C-2. 목표-달성(2025) 및 2025-2026 비교(상세)")

cols = [
    "부서", "구분", "특징",
    "세부과제명", "추진과제명",
    "사업코드", "사업명",
    "목표", "달성", "2025완료율(%)",
    "2026목표", "2026달성", "2026완료율(%)",
    "2025예산", "2026예산", "예산증감(2026-2025)",
    "담당자", "운영"
]
cols = [c for c in cols if c in fdf.columns]
show = fdf[cols].copy()

if "2025완료율(%)" in show.columns:
    show["2025완료율(%)"] = pd.to_numeric(show["2025완료율(%)"], errors="coerce").round(1)
if "2026완료율(%)" in show.columns:
    show["2026완료율(%)"] = pd.to_numeric(show["2026완료율(%)"], errors="coerce").round(1)

if dept != "(전체)":
    od = get_group_order(dept)
    if od and "구분" in show.columns:
        show["구분"] = pd.Categorical(show["구분"], categories=od, ordered=True)

sort_cols = [c for c in ["부서", "구분", "사업코드", "사업명"] if c in show.columns]
if sort_cols:
    show = show.sort_values(sort_cols, na_position="last")

money_cols = [c for c in ["2025예산", "2026예산", "예산증감(2026-2025)"] if c in show.columns]
show_disp = format_money_cols(show, money_cols)

st.dataframe(show_disp, use_container_width=True, hide_index=True)
