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

    dept_opts = ["(전체)"] + sorted([d for d in dfg["부서"].dropna().unique().tolist() if d != ""])
    dept = st.selectbox("부서", dept_opts, index=0)

    base = dfg if dept == "(전체)" else dfg[dfg["부서"] == dept]

    # 구분 옵션(부서 선택에 따라 다르게)
    # 정렬 규칙 반영
    order = get_group_order(dept) if dept != "(전체)" else None
    if order:
        cat_opts = ["(전체)"] + [c for c in order if c in base["구분"].unique().tolist()]
    else:
        cat_opts = ["(전체)"] + sorted([c for c in base["구분"].dropna().unique().tolist() if c != ""])
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
    st.warning("해당 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# -----------------------------
# KPI (예산 합계만)
# -----------------------------
total_2025 = float(fdf["2025예산"].sum())
total_2026 = float(fdf["2026예산"].sum())
delta = total_2026 - total_2025

c1, c2, c3 = st.columns(3)
c1.metric("사업(그룹) 수", int(len(fdf)))
c2.metric("2025예산 합계", f"{total_2025:,.0f}")
c3.metric("2026예산 합계", f"{total_2026:,.0f}", delta=f"{delta:,.0f}")

st.divider()

# =========================================================
# A) 구분별 2025-2026 예산 비교 (정렬 규칙 반영)
# =========================================================
st.subheader("A. 구분별 예산 비교 (2025 vs 2026)")

cat_df = budget_by_category(fdf)

# 부서별 탭
dept_list = sorted([d for d in cat_df["부서"].unique().tolist() if d != ""])
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
        long = sub.melt(id_vars=["부서", "구분"], value_vars=["2025예산", "2026예산"], var_name="연도", value_name="예산")
        chart = (
            alt.Chart(long)
            .mark_bar()
            .encode(
                x=alt.X("구분:N", sort=order if order else "-y", title="구분"),
                y=alt.Y("예산:Q", title="예산"),
                color=alt.Color("연도:N"),
                tooltip=["부서:N", "구분:N", "연도:N", alt.Tooltip("예산:Q", format=",")]
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)

        st.dataframe(
            sub[["구분", "2025예산", "2026예산", "예산증감(2026-2025)"]],
            use_container_width=True,
            hide_index=True
        )

st.divider()

# =========================================================
# B) 목표-달성 (2025) + 2025-2026 비교
# =========================================================
st.subheader("B. 목표-달성 현황 및 2025-2026 비교")

# 표시용 컬럼 구성
cols = [
    "부서", "구분", "특징",
    "세부과제명", "추진과제명",
    "사업코드", "사업명",
    "목표", "달성", "2025완료율(%)",
    "2026목표", "2026달성", "2026완료율(%)",
    "2025예산", "2026예산", "예산증감(2026-2025)",
    "담당자", "운영"
]
show = fdf[cols].copy()

# 완료율은 보기 좋게 반올림
show["2025완료율(%)"] = show["2025완료율(%)"].round(1)
show["2026완료율(%)"] = show["2026완료율(%)"].round(1)

# 테이블 정렬(부서 내 구분 순서 유지)
if dept != "(전체)":
    order = get_group_order(dept)
    if order:
        show["구분"] = pd.Categorical(show["구분"], categories=order, ordered=True)
show = show.sort_values(["부서", "구분", "사업코드", "사업명"], na_position="last")

st.dataframe(show, use_container_width=True, hide_index=True)

st.divider()

# =========================================================
# C) 세부과제명 / 세부과제명-추진과제명 기준 예산 비교
# =========================================================
st.subheader("C. 세부과제명 및 세부과제명-추진과제명 예산 비교(2025 vs 2026)")

task_df = budget_by_task(fdf).copy()

# 빈 값 제거(표시 품질)
task_df = task_df[(task_df["세부과제명"].astype(str).str.strip() != "") | (task_df["추진과제명"].astype(str).str.strip() != "")]
task_df = task_df.sort_values("2025예산", ascending=False)

# Top-N 선택
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

chart2 = (
    alt.Chart(long2)
    .mark_bar()
    .encode(
        y=alt.Y("라벨:N", sort="-x", title="세부과제명 / 추진과제명"),
        x=alt.X("예산:Q", title="예산"),
        color=alt.Color("연도:N"),
        tooltip=["부서:N", "라벨:N", "연도:N", alt.Tooltip("예산:Q", format=",")]
    )
    .properties(height=420)
)
st.altair_chart(chart2, use_container_width=True)

st.dataframe(
    top_task[["부서", "세부과제명", "추진과제명", "2025예산", "2026예산", "예산증감(2026-2025)"]],
    use_container_width=True,
    hide_index=True
)
