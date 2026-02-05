import streamlit as st
import pandas as pd
from utils import (
    load_data,
    make_kpi,
    budget_by_dept_and_category,
    program_list_by_group,
    top_programs_summary,
)

st.set_page_config(page_title="2025 혁신사업 예산·성과 대시보드", layout="wide")
st.title("2025 사업(예산·성과) 총장보고 지원 대시보드")

st.markdown(
    """
- 입력 파일: CSV 또는 Excel(xlsx)
- 필수 컬럼(대소문자 무관): 부서, 구분, 사업코드, 사업명, 목표, 달성, 예산, 사용예산, 잔여예산, 담당자
- (있으면 활용) 사업구분, 사업운영, 세목코드, 세목명, 이후일정, 진행내용 등
"""
)

uploaded = st.file_uploader("데이터 파일 업로드 (CSV / XLSX)", type=["csv", "xlsx"])
if not uploaded:
    st.info("파일을 업로드하면 부서별/구분별 예산 비율과 구분별 사업 리스트, 성과 요약을 자동 생성합니다.")
    st.stop()

df = load_data(uploaded)

# -----------------------------
# Sidebar Filters (연동형)
# -----------------------------
with st.sidebar:
    st.header("조회 조건")

    dept_opts = ["(전체)"] + sorted(df["부서"].dropna().unique().tolist())
    dept = st.selectbox("부서", dept_opts, index=0)

    # ✅ dept 선택에 따라 cat 후보를 바꿔줌
    if dept == "(전체)":
        cat_base = df
    else:
        cat_base = df[df["부서"] == dept]

    cat_opts = ["(전체)"] + sorted(cat_base["구분"].dropna().unique().tolist())
    cat = st.selectbox("구분", cat_opts, index=0)

    show_zero_budget = st.checkbox("예산=0 포함", value=False)

# -----------------------------
# Apply filters
# -----------------------------
fdf = df.copy()
if dept != "(전체)":
    fdf = fdf[fdf["부서"] == dept]
if cat != "(전체)":
    fdf = fdf[fdf["구분"] == cat]
if not show_zero_budget:
    fdf = fdf[fdf["예산"] > 0]

# -----------------------------
# KPI (필터 반영)
# -----------------------------
kpi = make_kpi(fdf)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("사업 수", kpi["n_projects"])
c2.metric("총예산", f"{kpi['budget_sum']:,.0f}")
c3.metric("사용예산", f"{kpi['spent_sum']:,.0f}")
c4.metric("잔여예산", f"{kpi['remain_sum']:,.0f}")
c5.metric("집행률", f"{kpi['execution_rate']:.1f}%")

st.divider()

# =========================================================
# ✅ NEW: 전체 사업 대비 "구분별 예산 비율" 도표 (필터 반영)
# =========================================================
st.subheader("A-0. 전체(조회조건 기준) 사업 대비 구분별 예산 비율")

# cat까지 특정하면 구분이 1개가 될 수 있으니, 도표는 (전체)/(부서) 수준에서 보는 게 유용
chart_base = df.copy()
if dept != "(전체)":
    chart_base = chart_base[chart_base["부서"] == dept]
if not show_zero_budget:
    chart_base = chart_base[chart_base["예산"] > 0]

by_cat = (
    chart_base.groupby("구분", as_index=False)["예산"].sum()
    .sort_values("예산", ascending=False)
)
total_budget = float(by_cat["예산"].sum())
by_cat["비율(%)"] = (by_cat["예산"] / total_budget * 100).round(1) if total_budget > 0 else 0

# 도표 2종(막대 + 파이) 중 택1/택2
left, right = st.columns([1, 1])

with left:
    st.caption("구분별 예산 총액(막대)")
    st.bar_chart(by_cat.set_index("구분")["예산"])

with right:
    st.caption("구분별 예산 비율(파이)")
    # streamlit 내장 chart는 pie가 없어서 altair 없이 표+막대 추천
    # 파이를 꼭 원하면 altair 추가 가능(아래 4) 참고
    st.dataframe(by_cat[["구분", "예산", "비율(%)"]], use_container_width=True, hide_index=True)

st.divider()

# -----------------------------
# A) Budget ratio table (필터 반영 버전)
# -----------------------------
st.subheader("A. 부서별·구분별 예산 총액 및 비율(예산 기준)")

# ✅ 표도 필터 반영: (전체면 전체, 부서 선택이면 해당 부서만)
ratio_base = df if dept == "(전체)" else df[df["부서"] == dept]
if not show_zero_budget:
    ratio_base = ratio_base[ratio_base["예산"] > 0]

ratio_df = budget_by_dept_and_category(ratio_base)
st.dataframe(ratio_df, use_container_width=True, hide_index=True)

st.divider()

# -----------------------------
# B) Program list by group (필터 반영)
# -----------------------------
st.subheader("B. 구분별 사업 리스트(성과 포함)")

# ✅ 탭도 조회 조건에 따라 달라지도록
dept_list = sorted(fdf["부서"].dropna().unique().tolist())
if not dept_list:
    st.warning("해당 조건에 해당하는 데이터가 없습니다.")
    st.stop()

group_tabs = st.tabs(dept_list)

for i, dept_name in enumerate(dept_list):
    with group_tabs[i]:
        dept_df = fdf[fdf["부서"] == dept_name].copy()

        cats = sorted(dept_df["구분"].dropna().unique().tolist())
        if not cats:
            st.info("해당 부서에 표시할 구분 데이터가 없습니다.")
        else:
            for cat_name in cats:
                st.markdown(f"### ▣ {cat_name}")
                tbl = program_list_by_group(dept_df, cat_name)
                st.dataframe(tbl, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("C. 총장 보고용 성과 요약(자동 추천 Top 7)")
        top_tbl, narrative = top_programs_summary(dept_df, top_n=7)
        st.dataframe(top_tbl, use_container_width=True, hide_index=True)
        st.markdown("**요약 문장(복사해서 보고서에 붙여넣기)**")
        st.code(narrative, language="text")
