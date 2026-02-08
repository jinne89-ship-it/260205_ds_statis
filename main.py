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

def is_blank_series(s: pd.Series) -> pd.Series:
    """NaN or empty/whitespace-only -> True"""
    return s.isna() | (s.astype(str).str.strip() == "")

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
            [c for c in order if c in base["구분"].dropna().astype(str).str.strip().unique()]
            if order else sorted(base["구분"].dropna().astype(str).str.strip().unique())
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
# Ⅰ. 2025 사업 분석 (✅ 구분 null 제외)
# =====================================================
st.header("Ⅰ. 2025 사업 분석")

# ✅ 2025 분석에서만 구분 null/빈값 제외
fdf_2025 = fdf[~is_blank_series(fdf["구분"])].copy()

if fdf_2025.empty:
    st.info("2025 사업 분석: (구분이 비어있지 않은) 데이터가 없습니다.")
else:
    cat25 = (
        fdf_2025.groupby(["부서", "구분"], as_index=False)["2025예산"]
        .sum()
    )

    # 부서 순서 유지(표시 품질)
    dept_list_25 = [d for d in ["교수학습개발센터", "교육혁신센터"] if d in cat25["부서"].unique()]
    others = sorted([d for d in cat25["부서"].unique() if d not in dept_list_25])
    dept_list_25 = dept_list_25 + others

    for d in dept_list_25:
        st.subheader(f"▣ {d}")
        sub = cat25[cat25["부서"] == d].copy()

        order = get_group_order(d)
        if order:
            # 정렬: 지정 순서에 없는 값은 뒤로(카테고리 NaN 처리)
            sub["구분"] = sub["구분"].astype(str).str.strip()
            sub["구분"] = pd.Categorical(sub["구분"], categories=order, ordered=True)
            sub = sub.sort_values("구분")
            # 혹시 order 밖 값이 들어오면(희박) NaN -> 뒤로 보냄
            sub = pd.concat([sub[~sub["구분"].isna()], sub[sub["구분"].isna()]], ignore_index=True)
        else:
            sub["구분"] = sub["구분"].astype(str).str.strip()
            sub = sub.sort_values("2025예산", ascending=False)

        sub["라벨"] = sub["2025예산"].apply(won)

        left, right = st.columns([1.2, 1])

        with left:
            chart = (
                alt.Chart(sub.dropna(subset=["구분"]))
                .mark_bar()
                .encode(
                    x=alt.X("구분:N", sort=order if order else "-y", title="구분"),
                    y=alt.Y("2025예산:Q", title="2025 예산"),
                    tooltip=["구분:N", alt.Tooltip("2025예산:Q", format=",.0f", title="예산")]
                )
                .properties(height=300)
            )
            labels = chart.mark_text(dy=-8).encode(text="라벨:N")
            st.altair_chart(chart + labels, use_container_width=True)

        with right:
            t = sub.copy()

            # 표 구성: 구분이 null인 행은 이미 제외됨(그래도 방어)
            t = t.dropna(subset=["구분"]).copy()

            total = t["2025예산"].sum()
            if total == 0:
                t["부서내 비율(%)"] = 0.0
            else:
                t["부서내 비율(%)"] = (t["2025예산"] / total * 100).round(1)

            total_row = pd.DataFrame([{
                "구분": "계",
                "2025예산": total,
                "부서내 비율(%)": 100.0 if total > 0 else 0.0
            }])

            t2 = pd.concat([t[["구분", "2025예산", "부서내 비율(%)"]], total_row], ignore_index=True)

            t2["2025예산"] = t2["2025예산"].apply(won)
            t2["부서내 비율(%)"] = t2["부서내 비율(%)"].apply(pct1)

            st.dataframe(
                t2[["구분", "2025예산", "부서내 비율(%)"]],
                use_container_width=True,
                hide_index=True
            )

st.divider()

# =====================================================
# Ⅱ. 2026 사업 계획 (기존 로직 유지)
# =====================================================
st.header("Ⅱ. 2026 사업 계획")

cat26 = fdf.groupby(["부서", "구분"], as_index=False)["2026예산"].sum()

for d in cat26["부서"].unique():
    st.subheader(f"▣ {d}")
    sub = cat26[cat26["부서"] == d].copy()

    order = get_group_order(d)
    if order:
        sub["구분"] = sub["구분"].astype(str).str.strip()
        sub["구분"] = pd.Categorical(sub["구분"], categories=order, ordered=True)
        sub = sub.sort_values("구분")
        sub = pd.concat([sub[~sub["구분"].isna()], sub[sub["구분"].isna()]], ignore_index=True)

    sub["라벨"] = sub["2026예산"].apply(won)

    left, right = st.columns([1.2, 1])

    with left:
        chart = (
            alt.Chart(sub.dropna(subset=["구분"]))
            .mark_bar()
            .encode(
                x=alt.X("구분:N", sort=order if order else "-y", title="구분"),
                y=alt.Y("2026예산:Q", title="2026 예산"),
                tooltip=["구분:N", alt.Tooltip("2026예산:Q", format=",.0f", title="예산")]
            )
            .properties(height=300)
        )
        labels = chart.mark_text(dy=-8).encode(text="라벨:N")
        st.altair_chart(chart + labels, use_container_width=True)

    with right:
        t = sub.dropna(subset=["구분"]).copy()
        t["2026예산"] = t["2026예산"].apply(won)
        st.dataframe(t[["구분", "2026예산"]], use_container_width=True, hide_index=True)

st.divider()

# =====================================================
# Ⅲ. 2025 → 2026 비교 (기존 로직 유지)
# =====================================================
st.header("Ⅲ. 2025 → 2026 예산 비교")

cmp = budget_by_category(fdf)

for d in cmp["부서"].unique():
    st.subheader(f"▣ {d}")
    sub = cmp[cmp["부서"] == d].copy()

    order = get_group_order(d)
    if order:
        sub["구분"] = sub["구분"].astype(str).str.strip()
        sub["구분"] = pd.Categorical(sub["구분"], categories=order, ordered=True)
        sub = sub.sort_values("구분")
        sub = pd.concat([sub[~sub["구분"].isna()], sub[sub["구분"].isna()]], ignore_index=True)

    left, right = st.columns([1.2, 1])

    with left:
        long = sub.dropna(subset=["구분"]).melt(
            id_vars=["구분"],
            value_vars=["2025예산", "2026예산"],
            var_name="연도",
            value_name="예산"
        )
        chart = (
            alt.Chart(long)
            .mark_bar()
            .encode(
                x=alt.X("구분:N", sort=order if order else "-y", title="구분"),
                y=alt.Y("예산:Q", title="예산"),
                color="연도:N",
                tooltip=["구분:N", "연도:N", alt.Tooltip("예산:Q", format=",.0f", title="예산")]
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)

    with right:
        t = sub.dropna(subset=["구분"]).copy()
        t["2025예산"] = t["2025예산"].apply(won)
        t["2026예산"] = t["2026예산"].apply(won)
        t["예산증감(2026-2025)"] = t["예산증감(2026-2025)"].apply(won)
        st.dataframe(
            t[["구분", "2025예산", "2026예산", "예산증감(2026-2025)"]],
            use_container_width=True,
            hide_index=True
        )
