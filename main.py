import streamlit as st
import pandas as pd
import altair as alt

from utils import (
    load_data,
    group_projects,
    apply_group_order,
    budget_by_category,
    get_group_order,
)

# =============================
# Helpers
# =============================
def won(x):
    try:
        if pd.isna(x):
            return ""
        return f"{int(round(float(x))):,}원"
    except:
        return ""

def pct(x):
    try:
        return f"{x:.1f}%"
    except:
        return ""

def format_money_cols(df, cols):
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].apply(won)
    return out


# =============================
# Page
# =============================
st.set_page_config(page_title="2025-2026 사업 대시보드", layout="wide")
st.title("2025-2026 사업(예산·성과·계획) 총장보고 대시보드")

uploaded = st.file_uploader("데이터 업로드 (CSV / XLSX)", type=["csv", "xlsx"])
if not uploaded:
    st.stop()

raw = load_data(uploaded)
dfg = apply_group_order(group_projects(raw))

# =============================
# Sidebar filters
# =============================
with st.sidebar:
    st.header("조회 조건")

    dept = st.selectbox(
        "부서",
        ["(전체)"] + sorted(dfg["부서"].dropna().unique().tolist())
    )

    base = dfg if dept == "(전체)" else dfg[dfg["부서"] == dept]

    order = get_group_order(dept) if dept != "(전체)" else None
    cat = st.selectbox(
        "구분",
        ["(전체)"] + (
            [c for c in order if c in base["구분"].unique()]
            if order else sorted(base["구분"].dropna().unique())
        )
    )

    fdf = base if cat == "(전체)" else base[base["구분"] == cat]

if fdf.empty:
    st.warning("해당 조건에 데이터가 없습니다.")
    st.stop()

# =============================
# KPI
# =============================
total_2025 = fdf["2025예산"].sum()
total_2026 = fdf["2026예산"].sum()

c1, c2, c3 = st.columns(3)
c1.metric("2025 사업 수", fdf[["사업코드","사업명"]].drop_duplicates().shape[0])
c2.metric("2025 예산 총액", won(total_2025))
c3.metric("2026 예산 총액", won(total_2026))

st.divider()

# ======================================================
# A-1. 2025 구분별 예산 구조 (그래프 | 표)
# ======================================================
st.header("Ⅰ. 2025 사업 분석")
st.subheader("A-1. 2025 구분별 예산 구조")

cat25 = (
    fdf.groupby(["부서","구분"], as_index=False)["2025예산"]
    .sum()
)

for d in cat25["부서"].unique():
    sub = cat25[cat25["부서"] == d]

    if order:
        sub["구분"] = pd.Categorical(sub["구분"], categories=order, ordered=True)
        sub = sub.sort_values("구분")

    sub["라벨"] = sub["2025예산"].apply(won)

    left, right = st.columns([1.2, 1])

    with left:
        chart = (
            alt.Chart(sub)
            .mark_bar()
            .encode(
                x="구분:N",
                y="2025예산:Q",
                tooltip=["구분:N", alt.Tooltip("2025예산:Q", format=",.0f", title="예산")]
            )
        )
        labels = chart.mark_text(dy=-8).encode(text="라벨:N")
        st.altair_chart(chart + labels, use_container_width=True)

    with right:
        st.dataframe(
            format_money_cols(sub[["구분","2025예산"]], ["2025예산"]),
            use_container_width=True,
            hide_index=True
        )

st.divider()

# ======================================================
# A-2. 2025 사업코드-사업명 기준 예산 비중
# ======================================================
st.subheader("A-2. 2025 사업별 예산 비중(사업코드-사업명 기준)")

g25 = (
    fdf.groupby(["사업코드","사업명"], as_index=False)["2025예산"]
    .sum()
)
g25["비율(%)"] = g25["2025예산"] / g25["2025예산"].sum() * 100
g25 = g25.sort_values("2025예산", ascending=False)

show25 = g25.copy()
show25["2025예산"] = show25["2025예산"].apply(won)
show25["비율(%)"] = show25["비율(%)"].apply(pct)

st.dataframe(show25, use_container_width=True, hide_index=True)

st.divider()

# ======================================================
# B-1. 2026 구분별 예산 구조 (그래프 | 표)
# ======================================================
st.header("Ⅱ. 2026 사업 계획")
st.subheader("B-1. 2026 구분별 예산 구조")

cat26 = (
    fdf.groupby(["부서","구분"], as_index=False)["2026예산"]
    .sum()
)

for d in cat26["부서"].unique():
    sub = cat26[cat26["부서"] == d]

    if order:
        sub["구분"] = pd.Categorical(sub["구분"], categories=order, ordered=True)
        sub = sub.sort_values("구분")

    sub["라벨"] = sub["2026예산"].apply(won)

    left, right = st.columns([1.2, 1])

    with left:
        chart = (
            alt.Chart(sub)
            .mark_bar()
            .encode(
                x="구분:N",
                y="2026예산:Q",
                tooltip=["구분:N", alt.Tooltip("2026예산:Q", format=",.0f", title="예산")]
            )
        )
        labels = chart.mark_text(dy=-8).encode(text="라벨:N")
        st.altair_chart(chart + labels, use_container_width=True)

    with right:
        st.dataframe(
            format_money_cols(sub[["구분","2026예산"]], ["2026예산"]),
            use_container_width=True,
            hide_index=True
        )

st.divider()

# ======================================================
# B-2. 2026 사업별 예산 비중
# ======================================================
st.subheader("B-2. 2026 사업별 예산 비중(사업코드-사업명 기준)")

g26 = (
    fdf.groupby(["사업코드","사업명"], as_index=False)["2026예산"]
    .sum()
)
g26["비율(%)"] = g26["2026예산"] / g26["2026예산"].sum() * 100
g26 = g26.sort_values("2026예산", ascending=False)

show26 = g26.copy()
show26["2026예산"] = show26["2026예산"].apply(won)
show26["비율(%)"] = show26["비율(%)"].apply(pct)

st.dataframe(show26, use_container_width=True, hide_index=True)

st.divider()

# ======================================================
# C-1. 2025 vs 2026 구분별 비교 (그래프 | 표)
# ======================================================
st.header("Ⅲ. 2025 → 2026 비교")
st.subheader("C-1. 구분별 예산 비교")

cmp = budget_by_category(fdf)

for d in cmp["부서"].unique():
    sub = cmp[cmp["부서"] == d]

    left, right = st.columns([1.2, 1])

    with left:
        long = sub.melt(
            id_vars=["구분"],
            value_vars=["2025예산","2026예산"],
            var_name="연도",
            value_name="예산"
        )
        chart = (
            alt.Chart(long)
            .mark_bar()
            .encode(
                x="구분:N",
                y="예산:Q",
                color="연도:N",
                tooltip=["구분:N","연도:N",alt.Tooltip("예산:Q",format=",.0f")]
            )
        )
        st.altair_chart(chart, use_container_width=True)

    with right:
        show = sub.copy()
        show = format_money_cols(show, ["2025예산","2026예산","예산증감(2026-2025)"])
        st.dataframe(
            show[["구분","2025예산","2026예산","예산증감(2026-2025)"]],
            use_container_width=True,
            hide_index=True
        )

st.divider()

# ======================================================
# C-2. 사업별 2025-2026 예산 비교
# ======================================================
st.subheader("C-2. 사업별 예산 변화(사업코드-사업명 기준)")

cmp2 = (
    fdf.groupby(["사업코드","사업명"], as_index=False)
    .agg({"2025예산":"sum","2026예산":"sum"})
)
cmp2["증감"] = cmp2["2026예산"] - cmp2["2025예산"]

showcmp = cmp2.copy()
showcmp = format_money_cols(showcmp, ["2025예산","2026예산","증감"])

st.dataframe(showcmp, use_container_width=True, hide_index=True)
