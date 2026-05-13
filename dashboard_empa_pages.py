from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

SECTIONS = {
    "cobertura": "Cobertura EMPA",
    "nutricion": "Estado nutricional",
    "riesgo": "Factores de riesgo",
    "profesional": "Profesional que realiza EMPA",
    "metodologia": "Metodología",
}

SECTION_FILES = {
    "cobertura": "cobertura_empa_{level}_2023_2025.csv",
    "nutricion": "estado_nutricional_empa_{level}_2023_2025.csv",
    "riesgo": "factores_riesgo_empa_{level}_2023_2025.csv",
    "profesional": "proporcion_profesional_empa_{level}_2023_2025.csv",
}

SEXO_OPTIONS = ["Ambos sexos", "Hombre", "Mujer"]
SEXO_FILE_MAP = {"Hombre": "hombre", "Mujer": "mujer"}

SECTION_DESCRIPTIONS = {
    "cobertura": "Cobertura anual de EMPA sobre población inscrita y validada.",
    "nutricion": "Distribución del estado nutricional en personas con EMPA realizado.",
    "riesgo": "Prevalencia observada de factores de riesgo en personas con EMPA.",
    "profesional": "Participación por profesional que realiza el EMPA.",
}

LEVEL_LABELS = {
    "rm": "Región Metropolitana",
    "servicio_salud": "Servicio de Salud",
    "comuna": "Comuna",
    "establecimiento": "Establecimiento",
}

LEVEL_ORDER = ["rm", "servicio_salud", "comuna", "establecimiento"]

AGE_LABELS = {
    "total_15_mas": "15 y más",

    "15_24": "15 a 24",
    "25_34": "25 a 34",
    "35_44": "35 a 44",
    "45_54": "45 a 54",
    "55_64": "55 a 64",
    "65_mas": "65 y más",
}

AGE_ORDER = list(AGE_LABELS.keys())

TEXT_TOKENS = (
    "nivel_geografico",
    "servicio_salud",
    "comuna",
    "establecimiento",
    "dependencia",
    "tipo_establecimiento",
    "categoria_estado_nutricional",
    "factor_riesgo",
    "profesional",
    "campo",
    "valor",
)

RM_LABEL = "Región Metropolitana"


def _file_path(section: str, level: str, sexo: str | None = None) -> Path:
    filename = SECTION_FILES[section].format(level=level)
    if sexo and sexo in SEXO_FILE_MAP:
        # Insert sexo suffix before the year range to match actual file naming:
        #   cobertura_empa_rm_2023_2025.csv → cobertura_empa_rm_hombre_2023_2025.csv
        filename = re.sub(
            r"(_\d{4}_\d{4}\.csv)$",
            f"_{SEXO_FILE_MAP[sexo]}\\1",
            filename,
        )
    return OUTPUT_DIR / filename


def _is_text_col(column: str) -> bool:
    if column.startswith("Id"):
        return True
    return any(token in column for token in TEXT_TOKENS)


def _clean_text(series: pd.Series) -> pd.Series:
    out = series.fillna("").astype(str).str.strip()
    return out.replace({"nan": "", "None": ""})


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in out.columns:
        if _is_text_col(column):
            out[column] = _clean_text(out[column])
        else:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    if "Ano" in out.columns:
        out["Ano"] = pd.to_numeric(out["Ano"], errors="coerce").astype("Int64")
    return out


@st.cache_data(show_spinner=False)
def load_section_data(section: str, level: str, sexo: str | None = None) -> pd.DataFrame:
    path = _file_path(section, level, sexo)
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, low_memory=False, encoding="utf-8-sig")
    return _normalize_frame(df)


@st.cache_data(show_spinner=False)
def load_metadata() -> pd.DataFrame:
    path = OUTPUT_DIR / "metadata_empa_2023_2025.csv"
    if not path.exists():
        return pd.DataFrame(columns=["campo", "valor"])
    df = pd.read_csv(path, low_memory=False, encoding="utf-8-sig")
    return _normalize_frame(df)


def list_years() -> list[int]:
    df = load_section_data("cobertura", "rm")
    if df.empty or "Ano" not in df.columns:
        return [2025, 2024, 2023]
    years = sorted({int(year) for year in df["Ano"].dropna().tolist()}, reverse=True)
    return years or [2025, 2024, 2023]


def safe_unique(series: pd.Series) -> list[str]:
    if series is None:
        return []
    cleaned = _clean_text(series)
    return sorted({value for value in cleaned.tolist() if value})


def format_int(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{int(round(float(value))):,}".replace(",", ".")


def format_pct(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.1f}%".replace(".", ",")


def format_pp_delta(current: float | int | None, previous: float | int | None) -> str | None:
    if current is None or previous is None or pd.isna(current) or pd.isna(previous):
        return None
    delta = float(current) - float(previous)
    return f"{delta:+.1f} pp".replace(".", ",")


def slugify(text: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "_", str(text).strip())
    return slug.strip("_") or "vista"


def dataframe_to_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        for sheet_name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return buffer.getvalue()


def selected_scope_label(level: str, filters: dict[str, str | None]) -> str:
    if filters.get("establecimiento"):
        return str(filters["establecimiento"])
    if filters.get("comuna"):
        return str(filters["comuna"])
    if filters.get("servicio_salud"):
        return str(filters["servicio_salud"])
    if level == "rm":
        return RM_LABEL
    return f"Total {LEVEL_LABELS[level].lower()}"


def available_unit_columns(level: str) -> list[str]:
    if level == "servicio_salud":
        return ["servicio_salud_master"]
    if level == "comuna":
        return ["servicio_salud_master", "comuna_master"]
    if level == "establecimiento":
        return [
            "servicio_salud_master",
            "comuna_master",
            "establecimiento_master",
            "tipo_establecimiento_master",
            "dependencia_master",
        ]
    return []


def apply_geo_filters(df: pd.DataFrame, filters: dict[str, str | None]) -> pd.DataFrame:
    out = df.copy()
    mapping = {
        "servicio_salud": "servicio_salud_master",
        "comuna": "comuna_master",
        "establecimiento": "establecimiento_master",
        "dependencia": "dependencia_master",
        "tipo_establecimiento": "tipo_establecimiento_master",
    }
    for key, column in mapping.items():
        value = filters.get(key)
        if value and column in out.columns:
            out = out[out[column].astype(str) == str(value)]
    return out


def render_geo_filters(df: pd.DataFrame, level: str, key_prefix: str) -> dict[str, str | None]:
    filters: dict[str, str | None] = {
        "servicio_salud": None,
        "comuna": None,
        "establecimiento": None,
        "dependencia": None,
        "tipo_establecimiento": None,
    }
    scoped = df.copy()

    if level != "rm" and "servicio_salud_master" in scoped.columns:
        options = safe_unique(scoped["servicio_salud_master"])
        selected = st.selectbox(
            "Servicio de Salud",
            ["(Todos)"] + options,
            key=f"{key_prefix}_ss",
        )
        if selected != "(Todos)":
            filters["servicio_salud"] = selected
            scoped = scoped[scoped["servicio_salud_master"].astype(str) == selected]

    if level in {"comuna", "establecimiento"} and "comuna_master" in scoped.columns:
        options = safe_unique(scoped["comuna_master"])
        selected = st.selectbox(
            "Comuna",
            ["(Todas)"] + options,
            key=f"{key_prefix}_com",
        )
        if selected != "(Todas)":
            filters["comuna"] = selected
            scoped = scoped[scoped["comuna_master"].astype(str) == selected]

    if level == "establecimiento" and "dependencia_master" in scoped.columns:
        options = safe_unique(scoped["dependencia_master"])
        selected = st.selectbox(
            "Dependencia",
            ["(Todas)"] + options,
            key=f"{key_prefix}_dep",
        )
        if selected != "(Todas)":
            filters["dependencia"] = selected
            scoped = scoped[scoped["dependencia_master"].astype(str) == selected]

    if level == "establecimiento" and "tipo_establecimiento_master" in scoped.columns:
        options = safe_unique(scoped["tipo_establecimiento_master"])
        selected = st.selectbox(
            "Tipo de establecimiento",
            ["(Todos)"] + options,
            key=f"{key_prefix}_tipo_est",
        )
        if selected != "(Todos)":
            filters["tipo_establecimiento"] = selected
            scoped = scoped[scoped["tipo_establecimiento_master"].astype(str) == selected]

    if level == "establecimiento" and "establecimiento_master" in scoped.columns:
        options = safe_unique(scoped["establecimiento_master"])
        selected = st.selectbox(
            "Establecimiento",
            ["(Todos)"] + options,
            key=f"{key_prefix}_est",
        )
        if selected != "(Todos)":
            filters["establecimiento"] = selected

    return filters


def coverage_metric_cols(age_key: str) -> tuple[str, str, str]:
    return (
        f"{age_key}_numerador",
        f"{age_key}_denominador",
        f"{age_key}_cobertura_pct",
    )


def aggregate_coverage(df: pd.DataFrame) -> pd.Series:
    values: dict[str, float | int | None] = {}
    for age_key in AGE_ORDER:
        num_col, den_col, pct_col = coverage_metric_cols(age_key)
        numerador = df[num_col].sum() if num_col in df.columns else 0
        denominador = df[den_col].sum() if den_col in df.columns else 0
        values[num_col] = numerador
        values[den_col] = denominador
        values[pct_col] = numerador / denominador * 100 if denominador else pd.NA
    return pd.Series(values)


def aggregate_coverage_by_year(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "Ano" not in df.columns:
        return pd.DataFrame()
    rows = []
    for year, subset in df.groupby("Ano", dropna=False):
        agg = aggregate_coverage(subset).to_dict()
        agg["Ano"] = int(year)
        rows.append(agg)
    return pd.DataFrame(rows).sort_values("Ano")


def age_profile_from_coverage(agg: pd.Series) -> pd.DataFrame:
    rows = []
    for age_key, label in AGE_LABELS.items():
        if age_key == "total_15_mas":
            continue
        _, _, pct_col = coverage_metric_cols(age_key)
        rows.append(
            {
                "Grupo etario": label,
                "Cobertura (%)": agg.get(pct_col, pd.NA),
            }
        )
    return pd.DataFrame(rows)


def summarize_category_section(df: pd.DataFrame, category_col: str, pct_suffix: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[category_col])
    sum_cols = [age_key for age_key in AGE_ORDER if age_key in df.columns]
    sum_cols.extend(
        [f"{age_key}_numerador" for age_key in AGE_ORDER if f"{age_key}_numerador" in df.columns]
    )
    out = df.groupby(category_col, as_index=False, dropna=False)[sum_cols].sum()
    for age_key in AGE_ORDER:
        base_col = f"{age_key}_numerador"
        if age_key in out.columns and base_col in out.columns:
            out[f"{age_key}{pct_suffix}"] = (out[age_key] / out[base_col] * 100).where(out[base_col].gt(0))
    return out


def summarize_category_by_year(df: pd.DataFrame, category_col: str, pct_suffix: str) -> pd.DataFrame:
    if df.empty or "Ano" not in df.columns:
        return pd.DataFrame(columns=["Ano", category_col])
    sum_cols = [age_key for age_key in AGE_ORDER if age_key in df.columns]
    sum_cols.extend(
        [f"{age_key}_numerador" for age_key in AGE_ORDER if f"{age_key}_numerador" in df.columns]
    )
    out = df.groupby(["Ano", category_col], as_index=False, dropna=False)[sum_cols].sum()
    for age_key in AGE_ORDER:
        base_col = f"{age_key}_numerador"
        if age_key in out.columns and base_col in out.columns:
            out[f"{age_key}{pct_suffix}"] = (out[age_key] / out[base_col] * 100).where(out[base_col].gt(0))
    return out.sort_values(["Ano", category_col])


def summarize_professional_section(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["profesional", "total_ambos_sexos", "proporcion_profesional_pct"])
    out = (
        df.groupby("profesional", as_index=False, dropna=False)["total_ambos_sexos"]
        .sum()
        .sort_values("total_ambos_sexos", ascending=False)
    )
    total = out["total_ambos_sexos"].sum()
    if total > 0:
        out["proporcion_profesional_pct"] = out["total_ambos_sexos"] / total * 100
    else:
        out["proporcion_profesional_pct"] = pd.NA
    return out


def summarize_professional_by_year(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "Ano" not in df.columns:
        return pd.DataFrame(columns=["Ano", "profesional", "total_ambos_sexos", "proporcion_profesional_pct"])
    out = (
        df.groupby(["Ano", "profesional"], as_index=False, dropna=False)["total_ambos_sexos"]
        .sum()
        .sort_values(["Ano", "total_ambos_sexos"], ascending=[True, False])
    )
    total_by_year = out.groupby("Ano")["total_ambos_sexos"].transform("sum")
    out["proporcion_profesional_pct"] = (out["total_ambos_sexos"] / total_by_year * 100).where(total_by_year.gt(0))
    return out


def previous_year_value(trend_df: pd.DataFrame, year: int, value_col: str) -> float | None:
    previous = trend_df.loc[trend_df["Ano"].lt(year), ["Ano", value_col]].sort_values("Ano")
    if previous.empty:
        return None
    value = previous.iloc[-1][value_col]
    if pd.isna(value):
        return None
    return float(value)


def make_line_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    color_col: str | None = None,
) -> alt.Chart:
    encodings = {
        "x": alt.X(f"{x_col}:O", title="Año"),
        "y": alt.Y(f"{y_col}:Q", title=None),
        "tooltip": [alt.Tooltip(f"{x_col}:O", title="Año"), alt.Tooltip(f"{y_col}:Q", title="Valor", format=".2f")],
    }
    if color_col:
        encodings["color"] = alt.Color(f"{color_col}:N", title=None)
        encodings["tooltip"].insert(1, alt.Tooltip(f"{color_col}:N", title="Serie"))
    return (
        alt.Chart(df)
        .mark_line(point=True, strokeWidth=3)
        .encode(**encodings)
        .properties(height=320, title=title)
    )


def make_bar_chart(
    df: pd.DataFrame,
    category_col: str,
    value_col: str,
    title: str,
    horizontal: bool = False,
) -> alt.Chart:
    tooltip = [alt.Tooltip(f"{category_col}:N", title="Categoría"), alt.Tooltip(f"{value_col}:Q", title="Valor", format=".2f")]
    if horizontal:
        return (
            alt.Chart(df)
            .mark_bar(cornerRadiusEnd=5)
            .encode(
                y=alt.Y(f"{category_col}:N", sort="-x", title=None),
                x=alt.X(f"{value_col}:Q", title=None),
                tooltip=tooltip,
            )
            .properties(height=max(260, 30 * max(len(df), 1)), title=title)
        )
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
        .encode(
            x=alt.X(f"{category_col}:N", sort=None, title=None),
            y=alt.Y(f"{value_col}:Q", title=None),
            tooltip=tooltip,
        )
        .properties(height=320, title=title)
    )


def display_table(df: pd.DataFrame, percent_cols: list[str] | None = None, int_cols: list[str] | None = None) -> pd.DataFrame:
    out = df.copy()
    for column in percent_cols or []:
        if column in out.columns:
            out[column] = out[column].map(format_pct)
    for column in int_cols or []:
        if column in out.columns:
            out[column] = out[column].map(format_int)
    return out


def rename_geo_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(
        columns={
            "servicio_salud_master": "Servicio de Salud",
            "comuna_master": "Comuna",
            "establecimiento_master": "Establecimiento",
            "dependencia_master": "Dependencia",
            "tipo_establecimiento_master": "Tipo establecimiento",
            "categoria_estado_nutricional": "Categoría",
            "factor_riesgo": "Factor de riesgo",
            "profesional": "Profesional",
            "total_ambos_sexos": "Total EMPA",
            "proporcion_profesional_pct": "Proporción profesional (%)",
        }
    )


def render_download_button(section: str, year: int, scope: str, sheets: dict[str, pd.DataFrame]) -> None:
    excel_bytes = dataframe_to_excel_bytes(sheets)
    st.download_button(
        label="Descargar vista en Excel",
        data=excel_bytes,
        file_name=f"{year}_{slugify(section)}_{slugify(scope)}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def render_home_page() -> None:
    st.title("Dashboard REM EMPA")

    metadata = load_metadata()
    if not metadata.empty:
        fechas = []
        for year in ["2023", "2024", "2025"]:
            row = metadata[metadata["campo"].astype(str).str.strip() == f"fecha_corte_{year}"]
            fecha = str(row.iloc[0]["valor"]) if not row.empty else "N/A"
            fechas.append(f"{year}: {fecha}")
        st.markdown("**Fecha de corte:** " + " | ".join(fechas))

    st.markdown("### Información disponible")
    for key in [k for k in SECTIONS if k != "metodologia"]:
        st.markdown(f"- **{SECTIONS[key]}**: {SECTION_DESCRIPTIONS[key]}")

    st.markdown(
        """
### Cómo navegar
- Usa el menú lateral para seleccionar la sección de interés.
- Filtra por año, nivel geográfico, grupo etario y sexo según corresponda.
- Los gráficos y tablas se actualizan automáticamente con los filtros aplicados.
        """
    )


def render_metodologia_page() -> None:
    st.title("Metodología")
    st.caption("Período cubierto por el dashboard REM EMPA en la Región Metropolitana.")

    metadata = load_metadata()
    if metadata.empty:
        st.error("No se encontró el archivo de metadatos.")
        st.stop()

    meta = dict(zip(metadata["campo"].astype(str).str.strip(), metadata["valor"].astype(str).str.strip()))

    st.markdown("### Período y alcance")
    st.markdown(f"- **Región**: Metropolitana ({meta.get('region_objetivo', 'N/A')})")
    st.markdown(f"- **Período**: {meta.get('periodo', 'N/A')}")
    fechas = []
    for year in ["2023", "2024", "2025"]:
        fecha = meta.get(f"fecha_corte_{year}", "N/A")
        fechas.append(f"{year}: {fecha}")
    st.markdown(f"- **Fechas de corte**: {', '.join(fechas)}")


def render_cobertura_page() -> None:
    st.title("Dashboard REM EMPA · Cobertura")
    st.caption("Cobertura anual de EMPA sobre población inscrita y validada.")

    years = list_years()
    with st.sidebar:
        st.header("Filtros")
        year = st.selectbox("Año", years, index=0, key="cob_year")
        level = st.selectbox(
            "Desagregación",
            LEVEL_ORDER,
            index=0,
            format_func=lambda value: LEVEL_LABELS[value],
            key="cob_level",
        )
        age_key = st.selectbox(
            "Grupo etario",
            AGE_ORDER,
            index=0,
            format_func=lambda value: AGE_LABELS[value],
            key="cob_age",
        )
        sexo = st.selectbox(
            "Sexo",
            SEXO_OPTIONS,
            index=0,
            key="cob_sexo",
        )

    sexo_param = sexo if sexo != "Ambos sexos" else None
    data = load_section_data("cobertura", level, sexo_param)
    if data.empty:
        st.error("No se encontró el archivo de cobertura para el nivel seleccionado.")
        st.stop()

    year_df = data[data["Ano"].eq(year)].copy()
    with st.sidebar:
        st.markdown("---")
        filters = render_geo_filters(year_df, level, "cob")

    filtered_year = apply_geo_filters(year_df, filters)
    filtered_all_years = apply_geo_filters(data, filters)

    if filtered_year.empty:
        st.warning("No hay registros para la combinación seleccionada.")
        st.stop()

    scope = selected_scope_label(level, filters)
    current = aggregate_coverage(filtered_year)
    trend = aggregate_coverage_by_year(filtered_all_years)

    num_col, den_col, pct_col = coverage_metric_cols(age_key)
    previous_pct = previous_year_value(trend, year, pct_col)

    c1, c2, c3 = st.columns(3)
    c1.metric("Cobertura EMPA", format_pct(current.get(pct_col)), delta=format_pp_delta(current.get(pct_col), previous_pct))
    c2.metric("Numerador", format_int(current.get(num_col)))
    c3.metric("Denominador", format_int(current.get(den_col)))
    st.caption("Variación en puntos porcentuales respecto al año anterior")

    left, right = st.columns([1.2, 1])
    with left:
        chart = make_line_chart(
            trend[[col for col in ["Ano", pct_col] if col in trend.columns]].dropna(),
            "Ano",
            pct_col,
            f"Evolución {AGE_LABELS[age_key].lower()}",
        )
        st.altair_chart(chart, use_container_width=True)
    with right:
        age_profile = age_profile_from_coverage(current)
        chart = make_bar_chart(age_profile, "Grupo etario", "Cobertura (%)", f"Perfil por edad · {year}")
        st.altair_chart(chart, use_container_width=True)

    ranking_level = "servicio_salud" if level == "rm" else level
    ranking_df = load_section_data("cobertura", ranking_level, sexo_param)
    ranking_df = ranking_df[ranking_df["Ano"].eq(year)].copy()
    ranking_df = apply_geo_filters(ranking_df, filters)

    view_cols = available_unit_columns(ranking_level)
    ranking_cols = [col for col in view_cols if col in ranking_df.columns] + [num_col, den_col, pct_col]
    ranking_view = ranking_df[ranking_cols].sort_values(pct_col, ascending=False)
    ranking_view = rename_geo_columns(ranking_view).rename(
        columns={
            num_col: "Numerador",
            den_col: "Denominador",
            pct_col: "Cobertura (%)",
        }
    )
    ranking_display = display_table(
        ranking_view,
        percent_cols=["Cobertura (%)"],
        int_cols=["Numerador", "Denominador"],
    )

    st.markdown("### Tabla EMPA Cobertura")
    st.dataframe(ranking_display, use_container_width=True, height=380)

    summary_table = pd.DataFrame(
        {
            "Grupo etario": [AGE_LABELS[item] for item in AGE_ORDER],
            "Numerador": [current.get(f"{item}_numerador") for item in AGE_ORDER],
            "Denominador": [current.get(f"{item}_denominador") for item in AGE_ORDER],
            "Cobertura (%)": [current.get(f"{item}_cobertura_pct") for item in AGE_ORDER],
        }
    )
    summary_display = display_table(summary_table, percent_cols=["Cobertura (%)"], int_cols=["Numerador", "Denominador"])

    with st.expander("Resumen por grupo etario"):
        st.dataframe(summary_display, use_container_width=True, height=320)

    render_download_button(
        "cobertura_empa",
        year,
        scope,
        {
            "ranking": ranking_view,
            "resumen": summary_table,
            "detalle_filtrado": filtered_year,
        },
    )


def render_category_page(
    section: str,
    category_col: str,
    pct_suffix: str,
    title: str,
) -> None:
    st.title(f"Dashboard REM EMPA · {title}")
    st.caption(SECTION_DESCRIPTIONS[section])

    years = list_years()
    with st.sidebar:
        st.header("Filtros")
        year = st.selectbox("Año", years, index=0, key=f"{section}_year")
        level = st.selectbox(
            "Desagregación",
            LEVEL_ORDER,
            index=0,
            format_func=lambda value: LEVEL_LABELS[value],
            key=f"{section}_level",
        )
        age_key = st.selectbox(
            "Grupo etario",
            AGE_ORDER,
            index=0,
            format_func=lambda value: AGE_LABELS[value],
            key=f"{section}_age",
        )
        sexo = st.selectbox(
            "Sexo",
            SEXO_OPTIONS,
            index=0,
            key=f"{section}_sexo",
        )

    sexo_param = sexo if sexo != "Ambos sexos" else None
    data = load_section_data(section, level, sexo_param)
    if data.empty:
        st.error("No se encontró el archivo esperado para la sección seleccionada.")
        st.stop()

    year_df = data[data["Ano"].eq(year)].copy()
    with st.sidebar:
        st.markdown("---")
        filters = render_geo_filters(year_df, level, section)

    filtered_year = apply_geo_filters(year_df, filters)
    filtered_all_years = apply_geo_filters(data, filters)

    if filtered_year.empty:
        st.warning("No hay registros para la combinación seleccionada.")
        st.stop()

    current_summary = summarize_category_section(filtered_year, category_col, pct_suffix)
    trend_summary = summarize_category_by_year(filtered_all_years, category_col, pct_suffix)

    with st.sidebar:
        options = current_summary[category_col].dropna().astype(str).tolist()
        selected_category = st.selectbox(
            "Categoría",
            options,
            index=0,
            key=f"{section}_category",
        )

    current_row = current_summary[current_summary[category_col].astype(str) == selected_category]
    if current_row.empty:
        st.warning("No fue posible resumir la categoría seleccionada.")
        st.stop()
    current_row = current_row.iloc[0]

    scope = selected_scope_label(level, filters)
    pct_col = f"{age_key}{pct_suffix}"
    total_pct_col = f"total_15_mas{pct_suffix}"
    previous_pct = previous_year_value(
        trend_summary[trend_summary[category_col].astype(str) == selected_category],
        year,
        pct_col,
    )

    total_evaluados = current_row.get(f"{age_key}_numerador")

    c1, c2, c3 = st.columns(3)
    c1.metric(selected_category, format_pct(current_row.get(pct_col)), delta=format_pp_delta(current_row.get(pct_col), previous_pct))
    c2.metric("Casos observados", format_int(current_row.get(age_key)))
    c3.metric("Población evaluada", format_int(total_evaluados))
    st.caption("Variación en puntos porcentuales respecto al año anterior")

    composition = current_summary[[category_col, age_key, pct_col]].copy().sort_values(pct_col, ascending=False)
    composition = composition.rename(columns={category_col: "Categoría", age_key: "Casos", pct_col: "Porcentaje"})

    trend_chart_df = trend_summary[trend_summary[category_col].astype(str) == selected_category][["Ano", pct_col]].dropna()
    trend_chart_df = trend_chart_df.rename(columns={pct_col: "Porcentaje"})

    left, right = st.columns([1.15, 1])
    with left:
        chart = make_line_chart(trend_chart_df, "Ano", "Porcentaje", f"Evolución de {selected_category.lower()}")
        st.altair_chart(chart, use_container_width=True)
    with right:
        chart = make_bar_chart(composition, "Categoría", "Porcentaje", f"Distribución {year}")
        st.altair_chart(chart, use_container_width=True)

    ranking_level = "servicio_salud" if level == "rm" else level
    ranking_df = load_section_data(section, ranking_level, sexo_param)
    ranking_df = ranking_df[ranking_df["Ano"].eq(year)].copy()
    ranking_df = apply_geo_filters(ranking_df, filters)
    ranking_df = ranking_df[ranking_df[category_col].astype(str) == selected_category].copy()

    ranking_pct_col = f"{age_key}{pct_suffix}"
    ranking_cols = [col for col in available_unit_columns(ranking_level) if col in ranking_df.columns]
    ranking_cols += [age_key, f"{age_key}_numerador", ranking_pct_col]
    ranking_view = ranking_df[ranking_cols].sort_values(ranking_pct_col, ascending=False)
    ranking_view = rename_geo_columns(ranking_view).rename(
        columns={
            age_key: "Casos",
            f"{age_key}_numerador": "Población evaluada",
            ranking_pct_col: "Porcentaje",
        }
    )
    ranking_display = display_table(
        ranking_view,
        percent_cols=["Porcentaje"],
        int_cols=["Casos", "Población evaluada"],
    )

    table_title = "Tabla Estados nutricionales" if section == "nutricion" else "Tabla Factores de riesgo"
    st.markdown(f"### {table_title}")
    st.dataframe(ranking_display, use_container_width=True, height=380)

    summary_columns = [category_col]
    summary_rename_map = {
        "total_15_mas": "Casos total 15 y más",
        "total_15_mas_numerador": "Población total 15 y más",
        total_pct_col: "Porcentaje total 15 y más",
    }
    summary_percent_cols = ["Porcentaje total 15 y más"]
    summary_int_cols = ["Casos total 15 y más", "Población total 15 y más"]

    if age_key != "total_15_mas":
        summary_columns += [age_key, f"{age_key}_numerador", pct_col]
        summary_rename_map.update(
            {
                age_key: "Casos grupo etario",
                f"{age_key}_numerador": "Población grupo etario",
                pct_col: "Porcentaje grupo etario",
            }
        )
        summary_percent_cols.insert(0, "Porcentaje grupo etario")
        summary_int_cols = ["Casos grupo etario", "Población grupo etario"] + summary_int_cols

    summary_columns += ["total_15_mas", "total_15_mas_numerador", total_pct_col]

    current_display = rename_geo_columns(
        current_summary[summary_columns].rename(columns=summary_rename_map)
    )
    current_display = display_table(
        current_display,
        percent_cols=summary_percent_cols,
        int_cols=summary_int_cols,
    )

    with st.expander("Resumen por categoría"):
        st.dataframe(current_display, use_container_width=True, height=320)

    render_download_button(
        f"{section}_empa",
        year,
        scope,
        {
            "ranking": ranking_view,
            "resumen": current_summary,
            "detalle_filtrado": filtered_year,
        },
    )


def render_professional_page() -> None:
    st.title("Dashboard REM EMPA · Profesional que realiza EMPA")
    st.caption(SECTION_DESCRIPTIONS["profesional"])

    years = list_years()
    with st.sidebar:
        st.header("Filtros")
        year = st.selectbox("Año", years, index=0, key="prof_year")
        level = st.selectbox(
            "Desagregación",
            LEVEL_ORDER,
            index=0,
            format_func=lambda value: LEVEL_LABELS[value],
            key="prof_level",
        )
        sexo = st.selectbox(
            "Sexo",
            SEXO_OPTIONS,
            index=0,
            key="prof_sexo",
        )

    sexo_param = sexo if sexo != "Ambos sexos" else None
    data = load_section_data("profesional", level, sexo_param)
    if data.empty:
        st.error("No se encontró el archivo de profesionales para el nivel seleccionado.")
        st.stop()

    year_df = data[data["Ano"].eq(year)].copy()
    with st.sidebar:
        st.markdown("---")
        filters = render_geo_filters(year_df, level, "prof")

    filtered_year = apply_geo_filters(year_df, filters)
    filtered_all_years = apply_geo_filters(data, filters)

    if filtered_year.empty:
        st.warning("No hay registros para la combinación seleccionada.")
        st.stop()

    current_summary = summarize_professional_section(filtered_year)
    trend_summary = summarize_professional_by_year(filtered_all_years)

    with st.sidebar:
        options = current_summary["profesional"].dropna().astype(str).tolist()
        selected_professional = st.selectbox("Profesional", options, index=0, key="prof_selector")

    current_row = current_summary[current_summary["profesional"].astype(str) == selected_professional]
    if current_row.empty:
        st.warning("No fue posible resumir el profesional seleccionado.")
        st.stop()
    current_row = current_row.iloc[0]

    scope = selected_scope_label(level, filters)
    previous_pct = previous_year_value(
        trend_summary[trend_summary["profesional"].astype(str) == selected_professional],
        year,
        "proporcion_profesional_pct",
    )

    total_empa = current_summary["total_ambos_sexos"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric(selected_professional, format_pct(current_row.get("proporcion_profesional_pct")), delta=format_pp_delta(current_row.get("proporcion_profesional_pct"), previous_pct))
    c2.metric("EMPA del profesional", format_int(current_row.get("total_ambos_sexos")))
    c3.metric("Total EMPA filtrados", format_int(total_empa))
    st.caption("Variación en puntos porcentuales respecto al año anterior")

    distribution = current_summary.rename(
        columns={
            "profesional": "Profesional",
            "proporcion_profesional_pct": "Porcentaje",
            "total_ambos_sexos": "Total EMPA",
        }
    )
    trend_chart_df = trend_summary[trend_summary["profesional"].astype(str) == selected_professional][
        ["Ano", "proporcion_profesional_pct"]
    ].dropna()
    trend_chart_df = trend_chart_df.rename(columns={"proporcion_profesional_pct": "Porcentaje"})

    left, right = st.columns([1.15, 1])
    with left:
        chart = make_line_chart(trend_chart_df, "Ano", "Porcentaje", f"Evolución de {selected_professional.lower()}")
        st.altair_chart(chart, use_container_width=True)
    with right:
        chart = make_bar_chart(distribution, "Profesional", "Porcentaje", f"Participación {year}")
        st.altair_chart(chart, use_container_width=True)

    ranking_level = "servicio_salud" if level == "rm" else level
    ranking_df = load_section_data("profesional", ranking_level, sexo_param)
    ranking_df = ranking_df[ranking_df["Ano"].eq(year)].copy()
    ranking_df = apply_geo_filters(ranking_df, filters)
    ranking_df = ranking_df[ranking_df["profesional"].astype(str) == selected_professional].copy()

    ranking_cols = [col for col in available_unit_columns(ranking_level) if col in ranking_df.columns]
    ranking_cols += ["total_ambos_sexos", "proporcion_profesional_pct"]
    ranking_view = ranking_df[ranking_cols].sort_values("proporcion_profesional_pct", ascending=False)
    ranking_view = ranking_view.rename(
        columns={
            "total_ambos_sexos": "Total EMPA",
            "proporcion_profesional_pct": "Porcentaje",
        }
    )
    ranking_view = rename_geo_columns(ranking_view)
    ranking_display = display_table(ranking_view, percent_cols=["Porcentaje"], int_cols=["Total EMPA"])

    st.markdown("### Tabla Profesionales")
    st.dataframe(ranking_display, use_container_width=True, height=380)

    summary_display = display_table(
        distribution.sort_values("Porcentaje", ascending=False),
        percent_cols=["Porcentaje"],
        int_cols=["Total EMPA"],
    )
    with st.expander("Resumen por profesional"):
        st.dataframe(summary_display, use_container_width=True, height=320)

    render_download_button(
        "profesional_empa",
        year,
        scope,
        {
            "ranking": ranking_view,
            "resumen": current_summary,
            "detalle_filtrado": filtered_year,
        },
    )


def render_section_page(section: str) -> None:
    if section == "cobertura":
        render_cobertura_page()
        return
    if section == "nutricion":
        render_category_page(
            section="nutricion",
            category_col="categoria_estado_nutricional",
            pct_suffix="_distribucion_pct",
            title="Estado nutricional",
        )
        return
    if section == "riesgo":
        render_category_page(
            section="riesgo",
            category_col="factor_riesgo",
            pct_suffix="_prevalencia_pct",
            title="Factores de riesgo",
        )
        return
    if section == "profesional":
        render_professional_page()
        return
    st.error(f"Sección no reconocida: {section}")
    st.stop()
