import pandas as pd

# --------------------------------------------------
# 부서별 '구분' 정렬 규칙 (최종 확정)
# --------------------------------------------------
def get_group_order(dept: str):
    """
    부서별 구분 정렬 규칙
    (총장 보고 순서 기준)
    """
    if dept == "교수학습개발센터":
        return [
            "교수",
            "학습",
            "원격",
            "성과·조사",
            "특화사업"
        ]

    if dept == "교육혁신센터":
        return [
            "교과",
            "비교과",
            "전공설계",
            "조사·환류",
            "특화사업"
        ]

    return None


# --------------------------------------------------
# 데이터 로딩
# --------------------------------------------------
def load_data(uploaded):
    if uploaded.name.endswith(".csv"):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)

    # 컬럼명 공백 제거
    df.columns = df.columns.str.strip()

    # 예산 컬럼 숫자 처리
    for col in ["2025예산", "2026예산"]:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", "")
                .str.replace("원", "")
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


# --------------------------------------------------
# 사업코드+사업명 기준 그룹핑
# --------------------------------------------------
def group_projects(df):
    group_cols = ["부서", "구분", "특징", "사업코드", "사업명"]

    agg = {
        "2025예산": "sum",
        "2026예산": "sum",
        "목표": "first",
        "달성": "first",
        "담당자": "first",
        "운영": "first",
        "세부과제명": lambda x: ", ".join(sorted(set(x.dropna()))),
        "추진과제명": lambda x: ", ".join(sorted(set(x.dropna())))
    }

    return (
        df.groupby(group_cols, dropna=False, as_index=False)
        .agg(agg)
    )


# --------------------------------------------------
# 구분별 예산 비교용
# --------------------------------------------------
def budget_by_category(df):
    out = (
        df.groupby(["부서", "구분"], as_index=False)
        .agg({
            "2025예산": "sum",
            "2026예산": "sum"
        })
    )
    out["예산증감(2026-2025)"] = out["2026예산"] - out["2025예산"]
    return out
