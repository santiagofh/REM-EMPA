from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
CONFIG_PATH = DATA_DIR / "diccionario_rem_empa_2023_2025.json"

A02_HOMBRE_COLS = [f"Col{i:02d}" for i in range(2, 30, 2)]
A02_MUJER_COLS = [f"Col{i:02d}" for i in range(3, 30, 2)]
A02_PUEBLOS_ORIGINARIOS_COLS = ["Col30", "Col31"]
A02_MIGRANTES_COLS = ["Col32", "Col33"]


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def to_int_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0).astype("int64")


def code_text(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .replace({"nan": "", "None": ""})
    )


def build_master_lookup(master_path: Path) -> pd.DataFrame:
    cols = [
        "EstablecimientoCodigoAntiguo",
        "EstablecimientoCodigo",
        "EstablecimientoCodigoMadreNuevo",
        "RegionCodigo",
        "SeremiSaludCodigo_ServicioDeSaludCodigo",
        "SeremiSaludGlosa_ServicioDeSaludGlosa",
        "TipoEstablecimientoGlosa",
        "EstablecimientoGlosa",
        "DependenciaAdministrativa",
        "NivelAtencionEstabglosa",
        "ComunaCodigo",
        "ComunaGlosa",
        "EstadoFuncionamiento",
    ]
    master = pd.read_csv(master_path, sep=";", dtype=str, usecols=cols)
    for col in [
        "EstablecimientoCodigoAntiguo",
        "EstablecimientoCodigo",
        "EstablecimientoCodigoMadreNuevo",
        "RegionCodigo",
        "SeremiSaludCodigo_ServicioDeSaludCodigo",
        "ComunaCodigo",
    ]:
        master[col] = code_text(master[col])

    current_codes = master.assign(IdEstablecimiento_lookup=master["EstablecimientoCodigo"])
    old_codes = master.assign(IdEstablecimiento_lookup=master["EstablecimientoCodigoAntiguo"])
    lookup = pd.concat([current_codes, old_codes], ignore_index=True)
    lookup = lookup[lookup["IdEstablecimiento_lookup"].ne("")]
    lookup = lookup.drop_duplicates("IdEstablecimiento_lookup")
    lookup["es_aps"] = (
        lookup["NivelAtencionEstabglosa"].fillna("").str.contains("Primario", case=False, na=False)
    )
    return lookup


def age_group_sum(df: pd.DataFrame, columns: list[str], output_col: str) -> None:
    existing_cols = [col for col in columns if col in df.columns]
    if not existing_cols:
        df[output_col] = 0
        return
    df[output_col] = df[existing_cols].sum(axis=1)


def add_a02_derived_columns(df: pd.DataFrame, config: dict, has_age_detail: bool = True) -> pd.DataFrame:
    age_map = config["rem_a02"]["grupos_etarios_solicitados"]
    sex_age_map = config["rem_a02"]["grupos_etarios_sexo"]

    df["total_15_mas"] = df["Col01"]
    if has_age_detail:
        df["total_hombres"] = df[A02_HOMBRE_COLS].sum(axis=1)
        df["total_mujeres"] = df[A02_MUJER_COLS].sum(axis=1)
        df["pueblos_originarios"] = df[A02_PUEBLOS_ORIGINARIOS_COLS].sum(axis=1)
        df["migrantes"] = df[A02_MIGRANTES_COLS].sum(axis=1)

        for group_key, group_config in age_map.items():
            age_group_sum(df, group_config["columns"], group_key)

        for group_key, group_config in sex_age_map.items():
            age_group_sum(df, group_config["hombres"], f"{group_key}_hombres")
            age_group_sum(df, group_config["mujeres"], f"{group_key}_mujeres")
    else:
        df["total_hombres"] = df["Col02"]
        df["total_mujeres"] = df["Col03"]
        df["pueblos_originarios"] = df["Col04"]
        df["migrantes"] = df["Col05"]
        for group_key in age_map:
            df[group_key] = 0
        for group_key in sex_age_map:
            df[f"{group_key}_hombres"] = 0
            df[f"{group_key}_mujeres"] = 0

    return df


def load_year_data(year: str, serie_path: Path, valid_codes: set[str], region_code: str) -> pd.DataFrame:
    usecols = [
        "Mes",
        "IdServicio",
        "Ano",
        "IdEstablecimiento",
        "CodigoPrestacion",
        "IdRegion",
        "IdComuna",
    ] + [f"Col{i:02d}" for i in range(1, 34)]

    chunks = []
    for chunk in pd.read_csv(
        serie_path,
        sep=";",
        dtype=str,
        usecols=usecols,
        chunksize=250_000,
        encoding="utf-8-sig",
    ):
        filtered = chunk[
            chunk["CodigoPrestacion"].isin(valid_codes) & chunk["IdRegion"].astype(str).str.strip().eq(region_code)
        ].copy()
        if filtered.empty:
            continue
        filtered["Ano"] = year
        chunks.append(filtered)

    if not chunks:
        return pd.DataFrame(columns=usecols)
    return pd.concat(chunks, ignore_index=True)


def prepare_filtered_detail(config: dict) -> pd.DataFrame:
    rem_config = config["rem_a02"]
    input_paths = config["input_paths"]
    region_code = config["region_objetivo"]

    valid_codes = set(rem_config["seccion_a_profesional"]["codigos"])
    valid_codes.update(rem_config["seccion_b_estado_nutricional"]["codigos"])
    valid_codes.update(rem_config["seccion_c_factores_riesgo"]["codigos"])
    valid_codes.update(rem_config["seccion_d_factores_laboratorio"]["codigos"])

    frames = []
    for year, raw_path in input_paths["series_a"].items():
        env_var = f"SERIE_A_{year}_PATH"
        serie_path = Path(os.environ.get(env_var, raw_path))
        df_year = load_year_data(year, serie_path, valid_codes, region_code)
        if not df_year.empty:
            frames.append(df_year)

    if not frames:
        raise FileNotFoundError("No fue posible cargar registros REM A02 para 2023, 2024 y 2025.")

    detail = pd.concat(frames, ignore_index=True)
    for col in ["Mes", "Ano", "IdServicio", "IdRegion", "IdComuna"]:
        detail[col] = to_int_series(detail[col])
    detail["IdEstablecimiento"] = code_text(detail["IdEstablecimiento"])
    detail["CodigoPrestacion"] = code_text(detail["CodigoPrestacion"])
    for col in [f"Col{i:02d}" for i in range(1, 34)]:
        detail[col] = to_int_series(detail[col])

    master = build_master_lookup(Path(input_paths["maestro_establecimientos"]))
    detail = detail.merge(
        master,
        left_on="IdEstablecimiento",
        right_on="IdEstablecimiento_lookup",
        how="left",
    ).drop(columns=["IdEstablecimiento_lookup"])

    detail = detail.rename(
        columns={
            "EstablecimientoCodigo": "EstablecimientoCodigo_master",
            "EstablecimientoCodigoMadreNuevo": "codigo_madre_master",
            "SeremiSaludCodigo_ServicioDeSaludCodigo": "IdServicio_master",
            "SeremiSaludGlosa_ServicioDeSaludGlosa": "servicio_salud_master",
            "TipoEstablecimientoGlosa": "tipo_establecimiento_master",
            "EstablecimientoGlosa": "establecimiento_master",
            "DependenciaAdministrativa": "dependencia_master",
            "NivelAtencionEstabglosa": "nivel_atencion_master",
            "ComunaCodigo": "IdComuna_master",
            "ComunaGlosa": "comuna_master",
            "EstadoFuncionamiento": "estado_funcionamiento_master",
        }
    )
    detail["sin_match_master"] = detail["establecimiento_master"].isna()
    return detail


def build_professional_output(detail: pd.DataFrame, config: dict) -> pd.DataFrame:
    professional_map = config["rem_a02"]["seccion_a_profesional"]["codigos"]
    age_map = config["rem_a02"]["grupos_etarios_solicitados"]
    sex_age_map = config["rem_a02"]["grupos_etarios_sexo"]
    value_cols = (
        ["total_15_mas", "total_hombres", "total_mujeres"]
        + list(age_map.keys())
        + [f"{group}_hombres" for group in sex_age_map]
        + [f"{group}_mujeres" for group in sex_age_map]
        + ["pueblos_originarios", "migrantes"]
    )
    geo_cols = [
        "Ano",
        "IdRegion",
        "IdServicio",
        "IdComuna",
        "IdEstablecimiento",
        "codigo_madre_master",
        "IdServicio_master",
        "servicio_salud_master",
        "dependencia_master",
        "IdComuna_master",
        "comuna_master",
        "tipo_establecimiento_master",
        "establecimiento_master",
        "nivel_atencion_master",
        "estado_funcionamiento_master",
        "es_aps",
        "sin_match_master",
    ]

    df = detail[detail["CodigoPrestacion"].isin(professional_map)].copy()
    df["profesional"] = df["CodigoPrestacion"].map(professional_map)
    years_with_age = set(config["rem_a02"]["seccion_a_profesional"].get("anos_con_desglose_etario", []))
    with_age = df[df["Ano"].isin(years_with_age)].copy()
    without_age = df[~df["Ano"].isin(years_with_age)].copy()
    frames = []
    if not with_age.empty:
        frames.append(add_a02_derived_columns(with_age, config, has_age_detail=True))
    if not without_age.empty:
        frames.append(add_a02_derived_columns(without_age, config, has_age_detail=False))
    df = pd.concat(frames, ignore_index=True) if frames else df
    out = df.groupby(geo_cols + ["profesional"], dropna=False, as_index=False)[value_cols].sum()
    return out.rename(columns={"total_15_mas": "total_ambos_sexos"})


def build_iaaps_numerator_output(professional: pd.DataFrame, coverage: pd.DataFrame, config: dict) -> pd.DataFrame:
    geo_cols = [
        "Ano",
        "IdRegion",
        "IdServicio",
        "IdComuna",
        "IdEstablecimiento",
        "codigo_madre_master",
        "IdServicio_master",
        "servicio_salud_master",
        "dependencia_master",
        "IdComuna_master",
        "comuna_master",
        "tipo_establecimiento_master",
        "establecimiento_master",
        "nivel_atencion_master",
        "estado_funcionamiento_master",
        "es_aps",
        "sin_match_master",
    ]
    value_cols = [
        "20_64_hombres",
        "20_64_mujeres",
        "65_mas_hombres",
        "65_mas_mujeres",
    ]
    professional_years = set(config["rem_a02"]["seccion_a_profesional"].get("anos_con_desglose_etario", []))
    professional_part = professional[professional["Ano"].isin(professional_years)]
    coverage_part = coverage[~coverage["Ano"].isin(professional_years)]

    frames = []
    if not professional_part.empty:
        prof = professional_part.groupby(geo_cols, dropna=False, as_index=False)[value_cols].sum()
        prof["fuente_numerador_iaaps"] = "REM A02 Seccion A"
        frames.append(prof)
    if not coverage_part.empty:
        cov = coverage_part.groupby(geo_cols, dropna=False, as_index=False)[value_cols].sum()
        cov["fuente_numerador_iaaps"] = "REM A02 Seccion B proxy historica"
        frames.append(cov)

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=geo_cols + value_cols)
    out["20_64_total"] = out["20_64_hombres"] + out["20_64_mujeres"]
    out["65_mas_total"] = out["65_mas_hombres"] + out["65_mas_mujeres"]
    return out


def build_nutritional_output(detail: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    category_map = config["rem_a02"]["seccion_b_estado_nutricional"]["codigos"]
    age_map = config["rem_a02"]["grupos_etarios_solicitados"]

    geo_cols = [
        "Ano",
        "IdRegion",
        "IdServicio",
        "IdComuna",
        "IdEstablecimiento",
        "codigo_madre_master",
        "IdServicio_master",
        "servicio_salud_master",
        "dependencia_master",
        "IdComuna_master",
        "comuna_master",
        "tipo_establecimiento_master",
        "establecimiento_master",
        "nivel_atencion_master",
        "estado_funcionamiento_master",
        "es_aps",
        "sin_match_master",
    ]

    df = detail[detail["CodigoPrestacion"].isin(category_map)].copy()
    df["categoria_estado_nutricional"] = df["CodigoPrestacion"].map(category_map)
    df = add_a02_derived_columns(df, config)

    requested_cols = [
        "total_15_mas",
        "total_hombres",
        "total_mujeres",
        *list(age_map.keys()),
        *[f"{group}_hombres" for group in config["rem_a02"]["grupos_etarios_sexo"]],
        *[f"{group}_mujeres" for group in config["rem_a02"]["grupos_etarios_sexo"]],
        "pueblos_originarios",
        "migrantes",
    ]
    nutricion = (
        df.groupby(geo_cols + ["categoria_estado_nutricional"], dropna=False, as_index=False)[requested_cols]
        .sum()
    )

    cobertura = (
        df.groupby(geo_cols, dropna=False, as_index=False)[requested_cols]
        .sum()
    )
    return nutricion, cobertura


def build_risk_output(detail: pd.DataFrame, config: dict) -> pd.DataFrame:
    risk_map = {}
    risk_map.update(config["rem_a02"]["seccion_c_factores_riesgo"]["codigos"])
    risk_map.update(config["rem_a02"]["seccion_d_factores_laboratorio"]["codigos"])
    age_map = config["rem_a02"]["grupos_etarios_solicitados"]

    geo_cols = [
        "Ano",
        "IdRegion",
        "IdServicio",
        "IdComuna",
        "IdEstablecimiento",
        "codigo_madre_master",
        "IdServicio_master",
        "servicio_salud_master",
        "dependencia_master",
        "IdComuna_master",
        "comuna_master",
        "tipo_establecimiento_master",
        "establecimiento_master",
        "nivel_atencion_master",
        "estado_funcionamiento_master",
        "es_aps",
        "sin_match_master",
    ]

    df = detail[detail["CodigoPrestacion"].isin(risk_map)].copy()
    df["factor_riesgo"] = df["CodigoPrestacion"].map(risk_map)
    df = add_a02_derived_columns(df, config)

    requested_cols = [
        "total_15_mas",
        "total_hombres",
        "total_mujeres",
        *list(age_map.keys()),
        *[f"{group}_hombres" for group in config["rem_a02"]["grupos_etarios_sexo"]],
        *[f"{group}_mujeres" for group in config["rem_a02"]["grupos_etarios_sexo"]],
        "pueblos_originarios",
        "migrantes",
    ]
    return (
        df.groupby(geo_cols + ["factor_riesgo"], dropna=False, as_index=False)[requested_cols]
        .sum()
    )


def build_control_output(detail: pd.DataFrame) -> pd.DataFrame:
    control = detail[
        [
            "Ano",
            "Mes",
            "IdServicio",
            "IdComuna",
            "IdEstablecimiento",
            "CodigoPrestacion",
            "establecimiento_master",
            "tipo_establecimiento_master",
            "nivel_atencion_master",
            "es_aps",
            "sin_match_master",
        ]
    ].drop_duplicates()
    return control.sort_values(["Ano", "IdServicio", "IdComuna", "IdEstablecimiento", "CodigoPrestacion"])


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    config = load_config()
    detail = prepare_filtered_detail(config)
    professional = build_professional_output(detail, config)
    nutrition, coverage = build_nutritional_output(detail, config)
    iaaps_numerator = build_iaaps_numerator_output(professional, coverage, config)
    risk = build_risk_output(detail, config)
    control = build_control_output(detail)

    outputs = {
        "rem_a02_empa_detalle_filtrado_2023_2025.csv": detail,
        "numerador_empa_profesional_establecimiento_2023_2025.csv": professional,
        "numerador_empa_iaaps_establecimiento_2023_2025.csv": iaaps_numerator,
        "numerador_empa_estado_nutricional_establecimiento_2023_2025.csv": nutrition,
        "numerador_empa_cobertura_establecimiento_2023_2025.csv": coverage,
        "numerador_empa_factores_riesgo_establecimiento_2023_2025.csv": risk,
        "control_calidad_empa_numerador_2023_2025.csv": control,
    }

    for filename, df in outputs.items():
        output_path = OUTPUT_DIR / filename
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"Escrito: {output_path}")

    aps_rows = int(coverage["es_aps"].fillna(False).sum())
    print(f"Filas detalle REM filtradas: {len(detail):,}")
    print(f"Registros con match en maestro: {(~detail['sin_match_master']).sum():,}")
    print(f"Filas de cobertura en APS: {aps_rows:,}")


if __name__ == "__main__":
    main()
