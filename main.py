import streamlit as st
import pandas as pd
import altair as alt

from utils import (
    load_data,
    group_projects,
    budget_by_category,
    category_share_table,
    get_group_order,
    is_blank_series,
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
        return f"{float(x):.1f}%"
    except:
        return ""

def sort_by_order(sub: pd.DataFrame, dept: str, col: str = "구분") -> pd.DataFrame:
    """Sort by department-specific order; unknowns go last."""
    order = get_group_order(dept)
    out = sub.copy()
    out[col] = out[col].astype(str).str.strip()
    if order:
        out[col] = pd.Categorical(out[col], categories=order, ordered=True)
        out = out.sort_values(col)
        out = pd.concat([out[~out[col].isna()], out[out[col].isna()]], ignore_index=True)
        # restore as string for display
        out[col] = out[col].astype(str).replace("nan", "")
    else:
        out = out.sort_values(col)
    return out

# =====================================================
# Page
# =====================================================
st.set_page_config(page_title="2025-2026 사업 대시보드", layout="wide")
st.title("2025-2026 사업(예산·성과·계획) 총장보고 대시보드")

st.caption("업로드 후, 조회조건(부서/구분/특징)에 따라 2025 분석 → 2026 계획 → 2025-2026 비교를 자동 생성합니다.")

uploaded = st.file_uploader("데이터 업로드 (CSV / XLSX)", type=["csv", "xlsx"])
if not uploaded:
    st.stop()

raw = load_data(uploaded)
dfg = group_projects(raw)

# =====================================================
# Sidebar: filters
# =====================================================
with st.sidebar:
    st.header("조회 조건")

    dept_opts = ["(전체)"] + sorted([d for d in dfg["부서"].dropna().unique().tolist() if str(d).strip() != ""])
    dept = st.selectbox("부서", dept_opts, index=0)

    base = dfg if dept == "(전체)" else dfg[dfg["부서"] == dept]

    # 구분 옵션은 부서 선택에 따라 + 순서 반영
    if dept == "(전체)":
        cat_opts = ["(전체)"] + sorted([c for c in base["구분"].dropna().unique().tolist() if str(c).strip() != ""])
    else:
        order = get_group_order(dept)
        cats_in = [c for c in base["구분"].dropna().astype(str).str.strip().unique().tolist() if c != ""]
        if order:
            cat_opts = ["(전체)"] + [c for c in order if c in cats_in] + sorted([c for c in cats_in if c not in order])
        else:
            cat_opts = ["(전체)"] + sorted(cats_in)

    cat = st.selectbox("구분", cat_opts, index=0)

    base2 = base if cat == "(전체)" else base[base["구분"] == cat]

    feat_opts = ["(전체)"] + sorted([x for x in base2["특징"].dropna().unique().tolist() if str(x).strip() != ""])
    feat = st.selectbox("특징", feat_opts, index=0)

# Apply filters
fdf = base2 if feat == "(전체)" else base2[base2["특징"] == feat]
if fdf.empty:
    st.warning("해당 조건에 데이터가 없습니다.")
    st.stop()

# =====================================================
# KPI
# =====================================================
k1, k2, k3 = st.columns(3)
k1.metric("사업 수(그룹)", fdf[["사업코드", "사업명"]].drop_duplicates().shape[0])
k2.metric("2025 예산 합계", won(fdf["2025예산"].sum()))
k3.metric("2026 예산 합계", won(fdf["2026예산"].sum()))
st.divider()

# =====================================================
# Ⅰ. 2025 사업 분석 (구분 null 제외, 그래프→표 세로)
# =====================================================
st.header("Ⅰ. 2025 사업 분석")

# ✅ 2025 분석에서만 구분 null/빈값 제외
fdf_2025 = fdf[~is_blank_series(fdf["구분"])].copy()

if fdf_2025.empty:
    st.info("2025 사업 분석: (구분이 비어있지 않은) 데이터가 없습니다.")
else:
    cat25 = fdf_2025.groupby(["부서", "구분"], as_index=False)["2025예산"].sum()

    # 부서 표시 순서(대표 2개 우선)
    dept_list = [d for d in ["교수학습개발센터", "교육혁신센터"] if d in cat25["부서"].unique()]
    dept_list += sorted([d for d in cat25["부서"].unique() if d not in dept_list])

    for d in dept_list:
        st.subheader(f"▣ {d}")

        sub = cat25[cat25["부서"] == d].copy()
        sub = sort_by_order(sub, d, "구분")

        # 그래프 라벨
        sub["라벨"] = sub["2025예산"].apply(won)

        # ---------- (1) 그래프 ----------
        chart = (
            alt.Chart(sub[sub["구분"].astype(str).str.strip() != ""])
            .mark_bar()
            .encode(
                x=alt.X("구분:N", title="구분"),
                y=alt.Y("2025예산:Q", title="2025 예산"),
                tooltip=["구분:N", alt.Tooltip("2025예산:Q", format=",.0f", title="예산")]
            )
            .properties(height=320)
        )
        labels = chart.mark_text(dy=-8).encode(text="라벨:N")
        st.altair_chart(chart + labels, use_container_width=True)

        # ---------- (2) 표 (계 + 부서내 비율 소수점 1자리) ----------
        t = sub[sub["구분"].astype(str).str.strip() != ""].copy()
        total = float(t["2025예산"].sum())
        if total > 0:
            t["부서내 비율(%)"] = (t["2025예산"] / total * 100).round(1)
        else:
            t["부서내 비율(%)"] = 0.0

        total_row = pd.DataFrame([{
            "구분": "계",
            "2025예산": total,
            "부서내 비율(%)": 100.0 if total > 0 else 0.0
        }])

        t2 = pd.concat([t[["구분", "2025예산", "부서내 비율(%)"]], total_row], ignore_index=True)
        t2["2025예산"] = t2["2025예산"].apply(won)
        t2["부서내 비율(%)"] = t2["부서내 비율(%)"].apply(pct1)

        st.dataframe(t2, use_container_width=True, hide_index=True)

        st.markdown("---")

st.divider()

# =====================================================
# Ⅱ. 2026 사업 계획 (그래프→표 세로)
# =====================================================
st.header("Ⅱ. 2026 사업 계획")

cat26 = fdf.groupby(["부서", "구분"], as_index=False)["2026예산"].sum()

dept_list2 = [d for d in ["교수학습개발센터", "교육혁신센터"] if d in cat26["부서"].unique()]
dept_list2 += sorted([d for d in cat26["부서"].unique() if d not in dept_list2])

for d in dept_list2:
    st.subheader(f"▣ {d}")
    sub = cat26[cat26["부서"] == d].copy()
    sub = sort_by_order(sub, d, "구분")
    sub["라벨"] = sub["2026예산"].apply(won)

    # 그래프
    chart = (
        alt.Chart(sub[sub["구분"].astype(str).str.strip() != ""])
        .mark_bar()
        .encode(
            x=alt.X("구분:N", title="구분"),
            y=alt.Y("2026예산:Q", title="2026 예산"),
            tooltip=["구분:N", alt.Tooltip("2026예산:Q", format=",.0f", title="예산")]
        )
        .properties(height=320)
    )
    labels = chart.mark_text(dy=-8).encode(text="라벨:N")
    st.altair_chart(chart + labels, use_container_width=True)

    # 표: 부서 내 비율도 함께(원하시면 제거 가능)
    t = sub[sub["구분"].astype(str).str.strip() != ""].copy()
    total = float(t["2026예산"].sum())
    if total > 0:
        t["부서내 비율(%)"] = (t["2026예산"] / total * 100).round(1)
    else:
        t["부서내 비율(%)"] = 0.0

    total_row = pd.DataFrame([{
        "구분": "계",
        "2026예산": total,
        "부서내 비율(%)": 100.0 if total > 0 else 0.0
    }])

    t2 = pd.concat([t[["구분", "2026예산", "부서내 비율(%)"]], total_row], ignore_index=True)
    t2["2026예산"] = t2["2026예산"].apply(won)
    t2["부서내 비율(%)"] = t2["부서내 비율(%)"].apply(pct1)

    st.dataframe(t2, use_container_width=True, hide_index=True)
    st.markdown("---")

st.divider()

# =====================================================
# Ⅲ. 2025 → 2026 예산 비교 (막대 2개 나란히 + 표 오른쪽)
# =====================================================
st.header("Ⅲ. 2025 → 2026 예산 비교")

cmp = budget_by_category(fdf)

dept_list3 = [d for d in ["교수학습개발센터", "교육혁신센터"] if d in cmp["부서"].unique()]
dept_list3 += sorted([d for d in cmp["부서"].unique() if d not in dept_list3])

for d in dept_list3:
    st.subheader(f"▣ {d}")
    sub = cmp[cmp["부서"] == d].copy()
    sub["예산증감(2026-2025)"] = sub["2026예산"] - sub["2025예산"]
    sub = sort_by_order(sub, d, "구분")

    left, right = st.columns([1.2, 1])

    with left:
        long = sub[sub["구분"].astype(str).str.strip() != ""].melt(
            id_vars=["구분"],
            value_vars=["2025예산", "2026예산"],
            var_name="연도",
            value_name="예산"
        )
        long["라벨"] = long["예산"].apply(won)

        chart = (
            alt.Chart(long)
            .mark_bar()
            .encode(
                x=alt.X("구분:N", title="구분"),
                y=alt.Y("예산:Q", title="예산"),
                color=alt.Color("연도:N"),
                xOffset="연도:N",
                tooltip=["구분:N", "연도:N", alt.Tooltip("예산:Q", format=",.0f", title="예산")]
            )
            .properties(height=340)
        )
        labels = (
            alt.Chart(long)
            .mark_text(dy=-8)
            .encode(
                x=alt.X("구분:N"),
                xOffset="연도:N",
                y=alt.Y("예산:Q"),
                text="라벨:N",
                color=alt.value("black")
            )
        )
        st.altair_chart(chart + labels, use_container_width=True)

    with right:
        t = sub[sub["구분"].astype(str).str.strip() != ""].copy()
        t["2025예산"] = t["2025예산"].apply(won)
        t["2026예산"] = t["2026예산"].apply(won)
        t["예산증감(2026-2025)"] = t["예산증감(2026-2025)"].apply(won)

        st.dataframe(
            t[["구분", "2025예산", "2026예산", "예산증감(2026-2025)"]],
            use_container_width=True,
            hide_index=True
        )

    st.markdown("---")
