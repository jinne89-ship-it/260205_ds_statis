import streamlit as st
import pandas as pd
import altair as alt

from utils import (
    load_data,
    group_projects,
    budget_by_category,
    get_group_order,
    is_blank_series,
)

# =====================================================
# Helpers
# =====================================================
def won(x):
    try:
        return f"{int(round(float(x))):,}원"
    except Exception:
        return ""

def pct1(x):
    try:
        return f"{float(x):.1f}%"
    except Exception:
        return ""

def sanitize_text(s):
    if s is None:
        return ""
    return str(s).strip()

# =====================================================
# Page
# =====================================================
st.set_page_config(page_title="2025-2026 사업 대시보드", layout="wide")
st.title("2025-2026 사업(예산·성과·계획) 총장보고 대시보드")

st.markdown(
    """
- 업로드 양식(예): **부서, 구분, 특징, 세부과제명, 추진과제명, 사업코드, 사업명, 목표, 달성, 2025예산, 2026목표, 2026예산** 등  
- **동일 (사업코드+사업명)** 은 자동 그룹핑(예산 합산 / 텍스트는 중복 제거 후 병합)
- **구분 정렬 규칙(고정)**
  - 교수학습개발센터: **교수 → 학습 → 원격 → 성과·조사 → 특화사업**
  - 교육혁신센터: **교과 → 비교과 → 전공설계 → 조사·환류 → 특화사업**
"""
)

uploaded = st.file_uploader("데이터 업로드 (CSV / XLSX)", type=["csv", "xlsx"])
if not uploaded:
    st.info("파일을 업로드하면 2025 분석 → 2026 계획 → 2025-2026 비교를 자동 생성합니다.")
    st.stop()

raw = load_data(uploaded)
dfg = group_projects(raw)

# =====================================================
# Sidebar (연동형 필터)
# =====================================================
with st.sidebar:
    st.header("조회 조건")

    dept_opts = ["(전체)"] + sorted([d for d in dfg["부서"].dropna().unique().tolist() if sanitize_text(d) != ""])
    dept = st.selectbox("부서", dept_opts, index=0)

    base = dfg if dept == "(전체)" else dfg[dfg["부서"] == dept]

    if dept != "(전체)":
        order = get_group_order(dept) or []
        base_cats = [sanitize_text(x) for x in base["구분"].dropna().unique().tolist() if sanitize_text(x) != ""]
        cat_opts = ["(전체)"] + [c for c in order if c in base_cats] + sorted([c for c in base_cats if c not in order])
    else:
        base_cats = [sanitize_text(x) for x in base["구분"].dropna().unique().tolist() if sanitize_text(x) != ""]
        cat_opts = ["(전체)"] + sorted(base_cats)

    cat = st.selectbox("구분", cat_opts, index=0)

    base2 = base if cat == "(전체)" else base[base["구분"] == cat]

    feat_opts = ["(전체)"] + sorted(
        [sanitize_text(x) for x in base2["특징"].dropna().unique().tolist() if sanitize_text(x) != ""]
    )
    feat = st.selectbox("특징", feat_opts, index=0)

# apply filters
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
# Ⅰ. 2025 사업 분석 (구분 null/빈값 제외)
# =====================================================
st.header("Ⅰ. 2025 사업 분석")

fdf_2025 = fdf[~is_blank_series(fdf["구분"])].copy()
if fdf_2025.empty:
    st.info("2025 사업 분석: (구분이 비어있지 않은) 데이터가 없습니다.")
else:
    # -----------------------------
    # (1) 부서-구분별 2025예산 (그래프 → 표)
    # -----------------------------
    cat25 = (
        fdf_2025.groupby(["부서", "구분"], as_index=False)["2025예산"]
        .sum()
    )

    preferred = ["교수학습개발센터", "교육혁신센터"]
    dept_list_25 = [d for d in preferred if d in cat25["부서"].unique().tolist()]
    dept_list_25 += sorted([d for d in cat25["부서"].unique().tolist() if d not in preferred])

    for d in dept_list_25:
        st.subheader(f"▣ {d}")
        sub = cat25[cat25["부서"] == d].copy()
        sub["구분"] = sub["구분"].astype(str).str.strip()

        order = get_group_order(d)
        if order:
            sub["구분"] = pd.Categorical(sub["구분"], categories=order, ordered=True)
            sub = sub.sort_values("구분")
            sub = pd.concat([sub[~sub["구분"].isna()], sub[sub["구분"].isna()]], ignore_index=True)
        else:
            sub = sub.sort_values("2025예산", ascending=False)

        sub_plot = sub.dropna(subset=["구분"]).copy()
        sub_plot["라벨"] = sub_plot["2025예산"].apply(won)

        chart = (
            alt.Chart(sub_plot)
            .mark_bar()
            .encode(
                x=alt.X("구분:N", sort=(order if order else "-y"), title="구분"),
                y=alt.Y("2025예산:Q", title="2025 예산"),
                tooltip=[
                    alt.Tooltip("구분:N", title="구분"),
                    alt.Tooltip("2025예산:Q", format=",.0f", title="예산(원)")
                ],
            )
            .properties(height=320)
        )
        labels = chart.mark_text(dy=-8).encode(text="라벨:N")
        st.altair_chart(chart + labels, use_container_width=True)

        t = sub_plot[["구분", "2025예산"]].copy()
        dept_total = float(t["2025예산"].sum())
        t["부서내 비율(%)"] = (t["2025예산"] / dept_total * 100).round(1) if dept_total > 0 else 0.0

        total_row = pd.DataFrame([{
            "구분": "계",
            "2025예산": dept_total,
            "부서내 비율(%)": 100.0 if dept_total > 0 else 0.0
        }])

        t2 = pd.concat([t, total_row], ignore_index=True)
        t2["2025예산"] = t2["2025예산"].apply(won)
        t2["부서내 비율(%)"] = t2["부서내 비율(%)"].apply(pct1)

        st.dataframe(
            t2[["구분", "2025예산", "부서내 비율(%)"]],
            use_container_width=True,
            hide_index=True
        )
        st.divider()

    # -----------------------------
    # ✅ (2) 사업코드-사업명 기준 2025예산 그룹핑 결과(추가)
    # -----------------------------
    st.subheader("▣ (추가) 2025 사업코드-사업명 기준 예산 집계")

    proj25 = (
        fdf_2025.groupby(["사업코드", "사업명"], as_index=False)["2025예산"]
        .sum()
    )
    proj25["사업코드"] = proj25["사업코드"].astype(str).str.strip()
    proj25["사업명"] = proj25["사업명"].astype(str).str.strip()

    # 정렬: 사업코드 → 사업명
    proj25 = proj25.sort_values(["사업코드", "사업명"], na_position="last").reset_index(drop=True)

    # 표시용 포맷
    proj25_disp = proj25.copy()
    proj25_disp["2025예산"] = proj25_disp["2025예산"].apply(won)

    st.dataframe(
        proj25_disp[["사업코드", "사업명", "2025예산"]],
        use_container_width=True,
        hide_index=True
    )

st.divider()

# =====================================================
# Ⅱ. 2026 사업 계획
# =====================================================
st.header("Ⅱ. 2026 사업 계획")

cat26 = (
    fdf.groupby(["부서", "구분"], as_index=False)["2026예산"]
    .sum()
)

preferred = ["교수학습개발센터", "교육혁신센터"]
dept_list_26 = [d for d in preferred if d in cat26["부서"].unique().tolist()]
dept_list_26 += sorted([d for d in cat26["부서"].unique().tolist() if d not in preferred])

for d in dept_list_26:
    st.subheader(f"▣ {d}")
    sub = cat26[cat26["부서"] == d].copy()
    sub["구분"] = sub["구분"].astype(str).str.strip()

    order = get_group_order(d)
    if order:
        sub["구분"] = pd.Categorical(sub["구분"], categories=order, ordered=True)
        sub = sub.sort_values("구분")
        sub = pd.concat([sub[~sub["구분"].isna()], sub[sub["구분"].isna()]], ignore_index=True)
    else:
        sub = sub.sort_values("2026예산", ascending=False)

    sub_plot = sub.dropna(subset=["구분"]).copy()
    sub_plot["라벨"] = sub_plot["2026예산"].apply(won)

    chart = (
        alt.Chart(sub_plot)
        .mark_bar()
        .encode(
            x=alt.X("구분:N", sort=(order if order else "-y"), title="구분"),
            y=alt.Y("2026예산:Q", title="2026 예산"),
            tooltip=[
                alt.Tooltip("구분:N", title="구분"),
                alt.Tooltip("2026예산:Q", format=",.0f", title="예산(원)")
            ],
        )
        .properties(height=320)
    )
    labels = chart.mark_text(dy=-8).encode(text="라벨:N")
    st.altair_chart(chart + labels, use_container_width=True)

    t = sub_plot[["구분", "2026예산"]].copy()
    t["2026예산"] = t["2026예산"].apply(won)
    st.dataframe(t, use_container_width=True, hide_index=True)

    st.divider()

# =====================================================
# Ⅲ. 2025 → 2026 예산 비교
# =====================================================
st.header("Ⅲ. 2025 → 2026 예산 비교")

cmp = budget_by_category(fdf)

dept_list_cmp = [d for d in preferred if d in cmp["부서"].unique().tolist()]
dept_list_cmp += sorted([d for d in cmp["부서"].unique().tolist() if d not in preferred])

for d in dept_list_cmp:
    st.subheader(f"▣ {d}")
    sub = cmp[cmp["부서"] == d].copy()
    sub["구분"] = sub["구분"].astype(str).str.strip()

    order = get_group_order(d)
    if order:
        sub["구분"] = pd.Categorical(sub["구분"], categories=order, ordered=True)
        sub = sub.sort_values("구분")
        sub = pd.concat([sub[~sub["구분"].isna()], sub[sub["구분"].isna()]], ignore_index=True)
    else:
        sub = sub.sort_values("2025예산", ascending=False)

    sub_plot = sub.dropna(subset=["구분"]).copy()

    long = sub_plot.melt(
        id_vars=["구분"],
        value_vars=["2025예산", "2026예산"],
        var_name="연도",
        value_name="예산"
    )

    chart = (
        alt.Chart(long)
        .mark_bar()
        .encode(
            x=alt.X("구분:N", sort=(order if order else "-y"), title="구분"),
            xOffset=alt.XOffset("연도:N"),
            y=alt.Y("예산:Q", title="예산"),
            color=alt.Color("연도:N", title="연도"),
            tooltip=[
                alt.Tooltip("구분:N", title="구분"),
                alt.Tooltip("연도:N", title="연도"),
                alt.Tooltip("예산:Q", format=",.0f", title="예산(원)")
            ],
        )
        .properties(height=340)
    )

    st.altair_chart(chart, use_container_width=True)

    t = sub_plot[["구분", "2025예산", "2026예산", "예산증감(2026-2025)"]].copy()
    t["2025예산"] = t["2025예산"].apply(won)
    t["2026예산"] = t["2026예산"].apply(won)
    t["예산증감(2026-2025)"] = t["예산증감(2026-2025)"].apply(won)
    st.dataframe(t, use_container_width=True, hide_index=True)

    st.divider()
