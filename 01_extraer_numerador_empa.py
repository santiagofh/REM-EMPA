from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
CONFIG_PATH = DATA_DIR / "diccionario_rem_empa_2023_2025.json"


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
    value_cols = ["Col01", "Col02", "Col03", "Col04", "Col05"]
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
    out = df.groupby(geo_cols + ["profesional"], dropna=False, as_index=False)[value_cols].sum()
    return out.rename(
        columns={
            "Col01": "total_ambos_sexos",
            "Col02": "total_hombres",
            "Col03": "total_mujeres",
            "Col04": "pueblos_originarios",
            "Col05": "migrantes",
        }
    )


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
    df["total_15_mas"] = df["Col01"]
    df["total_hombres"] = df["Col02"]
    df["total_mujeres"] = df["Col03"]
    for group_key, group_config in age_map.items():
        age_group_sum(df, group_config["columns"], group_key)

    requested_cols = ["total_15_mas", "total_hombres", "total_mujeres"] + list(age_map.keys()) + ["Col32", "Col33"]
    nutricion = (
        df.groupby(geo_cols + ["categoria_estado_nutricional"], dropna=False, as_index=False)[requested_cols]
        .sum()
        .rename(columns={"Col32": "pueblos_originarios", "Col33": "migrantes"})
    )

    cobertura = (
        df.groupby(geo_cols, dropna=False, as_index=False)[requested_cols]
        .sum()
        .rename(columns={"Col32": "pueblos_originarios", "Col33": "migrantes"})
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
    df["total_15_mas"] = df["Col01"]
    df["total_hombres"] = df["Col02"]
    df["total_mujeres"] = df["Col03"]
    for group_key, group_config in age_map.items():
        age_group_sum(df, group_config["columns"], group_key)

    requested_cols = ["total_15_mas", "total_hombres", "total_mujeres"] + list(age_map.keys()) + ["Col32", "Col33"]
    return (
        df.groupby(geo_cols + ["factor_riesgo"], dropna=False, as_index=False)[requested_cols]
        .sum()
        .rename(columns={"Col32": "pueblos_originarios", "Col33": "migrantes"})
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
    risk = build_risk_output(detail, config)
    control = build_control_output(detail)

    outputs = {
        "rem_a02_empa_detalle_filtrado_2023_2025.csv": detail,
        "numerador_empa_profesional_establecimiento_2023_2025.csv": professional,
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
