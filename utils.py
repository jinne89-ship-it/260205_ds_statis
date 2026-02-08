import io
import re
import pandas as pd


# -----------------------------
# 정렬 규칙 (부서별 '구분' 순서)
# -----------------------------
def get_group_order(dept: str):
    """
    부서별 '구분' 정렬 규칙
    """
    if dept == "교수학습개발센터":
        return ["교수", "학습", "원격", "조사", "기타"]

    if dept == "교육혁신센터":
        return ["교과", "비교과", "전공설계", "조사·모니터링단", "기타"]

    return None


# -----------------------------
# 컬럼/값 정리 유틸
# -----------------------------
def _norm_col(s: str) -> str:
    return re.sub(r"\s+", "", str(s)).strip()

def _to_number(x):
    """
    '25,610,070' / ' 30,000,000 ' / '' 등을 숫자로 변환
    """
    if x is None:
        return 0.0
    s = str(x).strip()
    if s == "" or s.lower() in {"nan", "none"}:
        return 0.0
    s = s.replace(",", "")
    # 혹시 "원" 같은 단위가 붙어있으면 제거
    s = re.sub(r"[^\d\.\-]", "", s)
    if s == "" or s == "-" or s == ".":
        return 0.0
    try:
        return float(s)
    except:
        return 0.0


def _ensure_cols(df: pd.DataFrame, required: list[str]):
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {missing}")
    return df


def _normalize_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    구분/부서 등 문자열 값 정리 + 조사·모니터링단 표준화
    """
    out = df.copy()

    for c in ["부서", "구분", "특징", "세부과제명", "추진과제명", "사업코드", "사업명", "운영", "담당자", "목표", "달성", "2026목표"]:
        if c in out.columns:
            out[c] = out[c].astype(str).fillna("").map(lambda x: x.strip())

    # "조사·모니터링단" 표기 흔들림 흡수
    if "구분" in out.columns:
        def fix_group(v: str) -> str:
            v = (v or "").strip()
            if v in {"조사·모니터링단", "조사/모니터링단", "조사-모니터링단", "조사 모니터링단", "조사·모니터링"}:
                return "조사·모니터링단"
            return v
        out["구분"] = out["구분"].map(fix_group)

    return out


# -----------------------------
# 데이터 로드
# -----------------------------
def load_data(uploaded_file) -> pd.DataFrame:
    """
    업로드 파일(CSV/XLSX)을 읽고,
    - 컬럼명 공백 제거/표준화
    - 예산 숫자 변환
    - 필수 컬럼 확인
    """
    name = uploaded_file.name.lower()

    if name.endswith(".csv"):
        raw_bytes = uploaded_file.getvalue()
        # BOM 대응
        s = raw_bytes.decode("utf-8-sig", errors="replace")
        df = pd.read_csv(io.StringIO(s))
    else:
        df = pd.read_excel(uploaded_file)

    # 컬럼명 정리(공백 제거)
    df.columns = [_norm_col(c) for c in df.columns]

    # 업로드 양식에서 "2026예산"이 '2026예산  ' 같이 들어오는 경우 대비
    # 공백 제거로 이미 정리되었지만, 혹시 유사명칭이 있으면 통합
    rename_map = {}
    for c in df.columns:
        if c in {"2026예산", "2026예산 ", "2026예산 ", "2026예산(선택)"}:
            rename_map[c] = "2026예산"
        if c in {"2025예산", "2025예산 "}:
            rename_map[c] = "2025예산"
    if rename_map:
        df = df.rename(columns=rename_map)

    required = ["부서", "구분", "특징", "세부과제명", "추진과제명", "사업코드", "사업명", "목표", "달성", "2025예산", "운영", "담당자"]
    _ensure_cols(df, required)

    # 2026 컬럼은 선택
    if "2026예산" not in df.columns:
        df["2026예산"] = 0
    if "2026목표" not in df.columns:
        df["2026목표"] = ""

    # 숫자 변환
    df["2025예산"] = df["2025예산"].apply(_to_number)
    df["2026예산"] = df["2026예산"].apply(_to_number)

    df = _normalize_values(df)
    return df


# -----------------------------
# 그룹핑(사업코드+사업명 기준)
# -----------------------------
def group_projects(df: pd.DataFrame) -> pd.DataFrame:
    """
    동일 사업코드+사업명 그룹핑:
    - 2025예산/2026예산 합산
    - 세부/추진과제명, 특징, 담당자, 운영 등은 중복 제거 후 병합
    - 목표/달성은 문자열 기반 병합(원본이 숫자형이면 그대로 합산 가능하도록 확장 가능)
    """
    def uniq_join(s: pd.Series) -> str:
        vals = []
        for x in s.astype(str).fillna(""):
            x = x.strip()
            if x and x not in vals:
                vals.append(x)
        return ", ".join(vals)

    g = (
        df.groupby(["부서", "구분", "사업코드", "사업명"], as_index=False)
        .agg({
            "2025예산": "sum",
            "2026예산": "sum",
            "특징": uniq_join,
            "세부과제명": uniq_join,
            "추진과제명": uniq_join,
            "목표": uniq_join,
            "달성": uniq_join,
            "2026목표": uniq_join,
            "담당자": uniq_join,
            "운영": uniq_join,
        })
    )
    return g


def apply_group_order(df: pd.DataFrame) -> pd.DataFrame:
    """
    값 정리(혹시 모를 공백/표기 흔들림 재정리 용도)
    """
    return _normalize_values(df)


# -----------------------------
# 구분별 예산 집계(2025/2026 비교용)
# -----------------------------
def budget_by_category(df: pd.DataFrame) -> pd.DataFrame:
    out = (
        df.groupby(["부서", "구분"], as_index=False)
        .agg({"2025예산": "sum", "2026예산": "sum"})
    )
    out["예산증감(2026-2025)"] = out["2026예산"] - out["2025예산"]
    return out
