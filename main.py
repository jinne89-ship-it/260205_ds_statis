import streamlit as st
import pandas as pd
import altair as alt

from utils import (
    load_data,
    group_projects,
    budget_by_category,
    get_group_order,
)

# =====================================================
# Helper
# =====================================================
def won(x):
    try:
        return f"{int(round(float(x))):,}원"
    except:
        return ""

def pct1(x):
    try:
        return f"{x:.1f}%"
    except:
        return ""

# =====================================================
# Page
# =====================================================
st.set_page_config(page_title="2025-2026 사업 대시보드", layout="wide")
st.title("2025-2026 사업(예산·성과·계획) 총장보고 대시보드")

uploaded = st.file_uploader("데이터 업로드 (CSV / XLSX)", type=["csv", "xlsx"])
if not uploaded:
    st.stop()

raw = load_data(uploaded)
dfg = group_projects(raw)

# =====================================================
# Sidebar
# =====================================================
with st.sidebar:
    st.header("조회 조건")

    dept = st.selectbox(
        "부서",
        ["(전체)"] + sorted(dfg["부서"].dropna().unique())
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

    base2 = base if cat == "(전체)" else base[base["구분"] == cat]

    feat = st.selectbox(
        "특징",
        ["(전체)"] + sorted(
            [x for x in base2["특징"].dropna().unique() if str(x).strip() != ""]
        )
    )

fdf = base2 if feat == "(전체)" else base2[base2["특징"] == feat]
if fdf.empty:
    st.warning("해당 조건에 데이터가 없습니다.")
    st.stop()

# =====================================================
# KPI
# =====================================================
c1, c2, c3 = st.columns(3)
c1.metric("사업 수", fdf[["사업코드", "사업명"]].drop_duplicates().shape[0])
c2.metric("2025 예산", won(fdf["2025예산"].sum()))
c3.metric("2026 예산", won(fdf["2026예산"].sum()))

st.divider()

# =====================================================
# Ⅰ. 2025 사업 분석
# =====================================================
st.header("Ⅰ. 2025 사업 분석")

cat25 = fdf.groupby(["부서", "구분"], as_index=False)["2025예산"].sum()

for d in cat25["부서"].unique():
    st.subheader(f"▣ {d}")
    sub = cat25[cat25["부서"] == d].copy()

    order = get_group_order(d)
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
                x=alt.X("구분:N", sort=order, title="구분"),
                y="2025예산:Q",
                tooltip=["구분:N", alt.Tooltip("2025예산:Q", format=",.0f")]
            )
        )
        labels = chart.mark_text(dy=-8).encode(text="라벨:N")
        st.altair_chart(chart + labels, use_container_width=True)

    with right:
        t = sub.copy()
        total = t["2025예산"].sum()
        t["부서내 비율(%)"] = (t["2025예산"] / total * 100).round(1)

        t = pd.concat([t, pd.DataFrame([{
            "구분": "계",
            "2025예산": total,
            "부서내 비율(%)": 100.0
        }])])

        t["2025예산"] = t["2025예산"].apply(won)
        t["부서내 비율(%)"] = t["부서내 비율(%)"].apply(pct1)

        st.dataframe(
            t[["구분", "2025예산", "부서내 비율(%)"]],
            use_container_width=True,
            hide_index=True
        )

st.divider()

# =====================================================
# Ⅱ. 2026 사업 계획
# =====================================================
st.header("Ⅱ. 2026 사업 계획")

cat26 = fdf.groupby(["부서", "구분"], as_index=False)["2026예산"].sum()

for d in cat26["부서"].unique():
    st.subheader(f"▣ {d}")
    sub = cat26[cat26["부서"] == d].copy()

    order = get_group_order(d)
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
                x=alt.X("구분:N", sort=order, title="구분"),
                y="2026예산:Q",
                tooltip=["구분:N", alt.Tooltip("2026예산:Q", format=",.0f")]
            )
        )
        labels = chart.mark_text(dy=-8).encode(text="라벨:N")
        st.altair_chart(chart + labels, use_container_width=True)

    with right:
        sub["2026예산"] = sub["2026예산"].apply(won)
        st.dataframe(sub[["구분", "2026예산"]], use_container_width=True, hide_index=True)
