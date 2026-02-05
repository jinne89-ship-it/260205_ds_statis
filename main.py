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
    st.info("좌측에서 파일을 업로드하면 부서별/구분별 예산 비율과 구분별 사업 리스트, 성과 요약을 자동 생성합니다.")
    st.stop()

df = load_data(uploaded)

# -----------------------------
# Filters
# -----------------------------
with st.sidebar:
    st.header("필터")
    dept_opts = ["(전체)"] + sorted(df["부서"].dropna().unique().tolist())
    cat_opts = ["(전체)"] + sorted(df["구분"].dropna().unique().tolist())

    dept = st.selectbox("부서", dept_opts, index=0)
    cat = st.selectbox("구분", cat_opts, index=0)

    show_zero_budget = st.checkbox("예산=0 포함", value=False)

fdf = df.copy()
if dept != "(전체)":
    fdf = fdf[fdf["부서"] == dept]
if cat != "(전체)":
    fdf = fdf[fdf["구분"] == cat]
if not show_zero_budget:
    fdf = fdf[fdf["예산"] > 0]

# -----------------------------
# KPI
# -----------------------------
kpi = make_kpi(fdf)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("사업 수", kpi["n_projects"])
c2.metric("총예산", f"{kpi['budget_sum']:,.0f}")
c3.metric("사용예산", f"{kpi['spent_sum']:,.0f}")
c4.metric("잔여예산", f"{kpi['remain_sum']:,.0f}")
c5.metric("집행률", f"{kpi['execution_rate']:.1f}%")

st.divider()

# -----------------------------
# A) Budget ratio table
# -----------------------------
st.subheader("A. 부서별·구분별 예산 총액 및 비율(예산 기준)")
ratio_df = budget_by_dept_and_category(df)
st.dataframe(ratio_df, use_container_width=True, hide_index=True)

# -----------------------------
# B) Program list by group
# -----------------------------
st.subheader("B. 구분별 사업 리스트(성과 포함)")
group_tabs = st.tabs(sorted(df["부서"].dropna().unique().tolist()))

for i, dept_name in enumerate(sorted(df["부서"].dropna().unique().tolist())):
    with group_tabs[i]:
        dept_df = df[df["부서"] == dept_name].copy()

        # 구분별 표를 여러 개로 분리해서 보여주기
        cats = sorted(dept_df["구분"].dropna().unique().tolist())
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
