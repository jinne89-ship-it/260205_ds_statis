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

# -----------------------------
# Helpers
# -----------------------------
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


# -----------------------------
# Page
# -----------------------------
st.set_page_config(page_title="2025-2026 사업 대시보드", layout="wide")
st.title("2025-2026 사업(예산·성과·계획) 총장보고 대시보드")

uploaded = st.file_uploader("데이터 업로드 (CSV / XLSX)", type=["csv", "xlsx"])
if not uploaded:
    st.info("파일을 업로드하면 2025 분석 → 2026 계획 → 2025-2026 비교가 자동 생성됩니다.")
    st.stop()

raw = load_data(uploaded)
dfg = apply_group_order(group_projects(raw))

# -----------------------------
# Sidebar filters (부서 → 구분 → 특징 연동)
# -----------------------------
with st.sidebar:
    st.header("조회 조건")

    dept_opts = ["(전체)"] + sorted(dfg["부서"].dropna().unique().tolist())
    dept = st.selectbox("부서", dept_opts, index=0)

    base = dfg if dept == "(전체)" else dfg[dfg["부서"] == dept]

    # 구분 옵션: 부서 선택 시 정렬 규칙 반영
    if dept != "(전체)":
        order = get_group_order(dept)
        cat_opts = ["(전체)"] + [c for c in (order or []) if c in base["구분"].unique()]
        if len(cat_opts) == 1:  # 혹시 order에 해당 구분이 없으면 fallback
            cat_opts = ["(전체)"] + sorted(base["구분"].dropna().unique().tolist())
    else:
        order = None
        cat_opts = ["(전체)"] + sorted(base["구분"].dropna().unique().tolist())

    cat = st.selectbox("구분", cat_opts, index=0)

    base2 = base if cat == "(전체)" else base[base["구분"] == cat]

    feat_opts = ["(전체)"] + sorted([x for x in base2["특징"].dropna().unique().tolist() if str(x).strip() != ""])
    feat = st.selectbox("특징", feat_opts, index=0)

# apply filters
fdf = dfg.copy()
if dept != "(전체)":
    fdf = fdf[fdf["부서"] == dept]
if cat != "(전체)":
    fdf = fdf[fdf["구분"] == cat]
if feat != "(전체)":
    fdf = fdf[fdf["특징"] == feat]

if fdf.empty:
    st.warning("해당 조건에 데이터가 없습니다.")
    st.stop()

# -----------------------------
# KPI
# -----------------------------
total_2025 = float(fdf["2025예산"].sum())
total_2026 = float(fdf["2026예산"].sum())

c1, c2, c3 = st.columns(3)
c1.metric("사업 수(그룹)", int(len(fdf)))
c2.metric("2025 예산 총액", won(total_2025))
c3.metric("2026 예산 총액", won(total_2026))

st.divider()


# ======================================================
# Ⅰ. 2025 사업 분석
# ======================================================
st.header("Ⅰ. 2025 사업 분석")

# -----------------------------
# A-1: 2025 구분별 예산 구조 (좌 그래프 | 우 표)
# -----------------------------
st.subheader("A-1. 2025 구분별 예산 구조")

cat25 = (
    fdf.groupby(["부서", "구분"], as_index=False)["2025예산"]
    .sum()
)

for d in cat25["부서"].unique():
    sub = cat25[cat25["부서"] == d].copy()

    # ✅ 정렬 규칙 적용
    order_d = get_group_order(d)
    if order_d:
        sub["구분"] = pd.Categorical(sub["구분"], categories=order_d, ordered=True)
        sub = sub.sort_values("구분")
    else:
        sub = sub.sort_values("2025예산", ascending=False)

    sub["라벨"] = sub["2025예산"].apply(won)

    left, right = st.columns([1.2, 1])
    with left:
        base_chart = (
            alt.Chart(sub)
            .mark_bar()
            .encode(
                x=alt.X("구분:N", sort=order_d if order_d else "-y", title="구분"),
                y=alt.Y("2025예산:Q", title="2025 예산"),
                tooltip=["구분:N", alt.Tooltip("2025예산:Q", format=",.0f", title="예산(원)")]
            )
            .properties(height=320)
        )
        labels = base_chart.mark_text(dy=-8).encode(text="라벨:N")
        st.altair_chart(base_chart + labels, use_container_width=True)

    with right:
        st.dataframe(
            format_money_cols(sub[["구분", "2025예산"]], ["2025예산"]),
            use_container_width=True,
            hide_index=True
        )

st.divider()

# -----------------------------
# A-2: 사업별(사업코드-사업명) 2025예산 계 + 비율
# -----------------------------
st.subheader("A-2. 2025 사업별 예산 비중(사업코드-사업명 기준)")

g25 = (
    fdf.groupby(["사업코드", "사업명"], as_index=False)["2025예산"]
    .sum()
)
tot25 = float(g25["2025예산"].sum()) if len(g25) else 0.0
g25["비율(%)"] = (g25["2025예산"] / tot25 * 100) if tot25 > 0 else 0
g25 = g25.sort_values("2025예산", ascending=False)

# 표 표시용
show25 = g25.copy()
show25["2025예산"] = show25["2025예산"].apply(won)
show25["비율(%)"] = show25["비율(%)"].apply(pct)
st.dataframe(show25, use_container_width=True, hide_index=True)

st.divider()


# ======================================================
# Ⅱ. 2026 사업 계획
# ======================================================
st.header("Ⅱ. 2026 사업 계획")

# -----------------------------
# B-1: 2026 구분별 예산 구조 (좌 그래프 | 우 표)
# -----------------------------
st.subheader("B-1. 2026 구분별 예산 구조")

cat26 = (
    fdf.groupby(["부서", "구분"], as_index=False)["2026예산"]
    .sum()
)

for d in cat26["부서"].unique():
    sub = cat26[cat26["부서"] == d].copy()

    # ✅ 정렬 규칙 적용
    order_d = get_group_order(d)
    if order_d:
        sub["구분"] = pd.Categorical(sub["구분"], categories=order_d, ordered=True)
        sub = sub.sort_values("구분")
    else:
        sub = sub.sort_values("2026예산", ascending=False)

    sub["라벨"] = sub["2026예산"].apply(won)

    left, right = st.columns([1.2, 1])
    with left:
        base_chart = (
            alt.Chart(sub)
            .mark_bar()
            .encode(
                x=alt.X("구분:N", sort=order_d if order_d else "-y", title="구분"),
                y=alt.Y("2026예산:Q", title="2026 예산"),
                tooltip=["구분:N", alt.Tooltip("2026예산:Q", format=",.0f", title="예산(원)")]
            )
            .properties(height=320)
        )
        labels = base_chart.mark_text(dy=-8).encode(text="라벨:N")
        st.altair_chart(base_chart + labels, use_container_width=True)

    with right:
        st.dataframe(
            format_money_cols(sub[["구분", "2026예산"]], ["2026예산"]),
            use_container_width=True,
            hide_index=True
        )

st.divider()

# -----------------------------
# B-2: 사업별(사업코드-사업명) 2026예산 계 + 비율
# -----------------------------
st.subheader("B-2. 2026 사업별 예산 비중(사업코드-사업명 기준)")

g26 = (
    fdf.groupby(["사업코드", "사업명"], as_index=False)["2026예산"]
    .sum()
)
tot26 = float(g26["2026예산"].sum()) if len(g26) else 0.0
g26["비율(%)"] = (g26["2026예산"] / tot26 * 100) if tot26 > 0 else 0
g26 = g26.sort_values("2026예산", ascending=False)

show26 = g26.copy()
show26["2026예산"] = show26["2026예산"].apply(won)
show26["비율(%)"] = show26["비율(%)"].apply(pct)
st.dataframe(show26, use_container_width=True, hide_index=True)

st.divider()


# ======================================================
# Ⅲ. 2025 → 2026 비교
# ======================================================
st.header("Ⅲ. 2025 → 2026 비교")

# -----------------------------
# C-1: 구분별 2025 vs 2026 막대(나란히) + 표 (좌|우)
# -----------------------------
st.subheader("C-1. 구분별 예산 비교(2025 vs 2026)")

cmp = budget_by_category(fdf)

for d in cmp["부서"].unique():
    sub = cmp[cmp["부서"] == d].copy()

    # ✅ 정렬 규칙 적용
    order_d = get_group_order(d)
    if order_d:
        sub["구분"] = pd.Categorical(sub["구분"], categories=order_d, ordered=True)
        sub = sub.sort_values("구분")
    else:
        sub = sub.sort_values("2025예산", ascending=False)

    left, right = st.columns([1.2, 1])
    with left:
        long = sub.melt(
            id_vars=["구분"],
            value_vars=["2025예산", "2026예산"],
            var_name="연도",
            value_name="예산"
        )
        # 라벨(원) 표시: 막대 위 텍스트
        long["라벨"] = long["예산"].apply(won)

        chart = (
            alt.Chart(long)
            .mark_bar()
            .encode(
                x=alt.X("구분:N", sort=order_d if order_d else "-y", title="구분"),
                xOffset="연도:N",
                y=alt.Y("예산:Q", title="예산"),
                color=alt.Color("연도:N", legend=alt.Legend(title="연도")),
                tooltip=["구분:N", "연도:N", alt.Tooltip("예산:Q", format=",.0f", title="예산(원)")]
            )
            .properties(height=340)
        )

        text = (
            alt.Chart(long)
            .mark_text(dy=-8)
            .encode(
                x=alt.X("구분:N", sort=order_d if order_d else "-y"),
                xOffset="연도:N",
                y="예산:Q",
                text="라벨:N"
            )
        )
        st.altair_chart(chart + text, use_container_width=True)

    with right:
        show = sub.copy()
        show = format_money_cols(show, ["2025예산", "2026예산", "예산증감(2026-2025)"])
        st.dataframe(
            show[["구분", "2025예산", "2026예산", "예산증감(2026-2025)"]],
            use_container_width=True,
            hide_index=True
        )

st.divider()

# -----------------------------
# C-2: 사업별(사업코드-사업명) 2025 vs 2026 비교(표)
# -----------------------------
st.subheader("C-2. 사업별 예산 변화(사업코드-사업명 기준)")

cmp2 = (
    fdf.groupby(["사업코드", "사업명"], as_index=False)
    .agg({"2025예산": "sum", "2026예산": "sum"})
)
cmp2["증감(2026-2025)"] = cmp2["2026예산"] - cmp2["2025예산"]
cmp2 = cmp2.sort_values("2025예산", ascending=False)

showcmp2 = format_money_cols(cmp2, ["2025예산", "2026예산", "증감(2026-2025)"])
st.dataframe(showcmp2, use_container_width=True, hide_index=True)
