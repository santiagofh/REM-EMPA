from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
CONFIG_PATH = DATA_DIR / "diccionario_rem_empa_2023_2025.json"
DENOMINATOR_CODE_ALIASES = {
    "311001": "201674",
}


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def code_text(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .replace({"nan": "", "None": ""})
    )


def to_int_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0).astype("int64")


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


def load_sheet_with_embedded_header(path: Path, sheet_name: str, skiprows: int) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet_name, header=None, skiprows=skiprows)
    header_row = 0
    for idx in range(len(raw)):
        row = raw.iloc[idx]
        values = [str(value).strip() for value in row.tolist() if pd.notna(value)]
        if len(values) >= 5 and any(
            any(token in value.lower() for token in ["codigo", "código", "servicio"])
            for value in values
        ):
            header_row = idx
            break
    header = raw.iloc[header_row].tolist()
    df = raw.iloc[header_row + 1 :].copy()
    df.columns = header
    return df


def standardize_denominator_frame(year: str, df: pd.DataFrame) -> pd.DataFrame:
    if year == "2023":
        renamed = df.rename(
            columns={
                "Código Región": "RegionCodigo",
                "Nombre Región": "RegionGlosa",
                "Código Serv. Salud": "IdServicio_den",
                "Nombre Serv. Salud": "servicio_salud_denominador",
                "Código Comuna": "IdComuna_den",
                "Nombre Comuna": "comuna_denominador",
                "Código Establecimiento": "IdEstablecimiento",
                "Nombre Establecimiento": "establecimiento_denominador",
                "Sexo": "sexo",
                "Edad": "edad",
                "Inscritos": "inscritos",
            }
        )
        renamed["dependencia_denominador"] = pd.NA
    elif year == "2024":
        renamed = df.rename(
            columns={
                "Servicio de Salud": "servicio_salud_denominador",
                "Código Comuna": "IdComuna_den",
                "Comuna": "comuna_denominador",
                "Dependencia Adm.": "dependencia_denominador",
                "Código Centro": "IdEstablecimiento",
                "Centro": "establecimiento_denominador",
                "Sexo": "sexo",
                "Edad": "edad",
                "Inscritos": "inscritos",
            }
        )
        renamed["RegionCodigo"] = "13"
        renamed["RegionGlosa"] = "Región Metropolitana"
        renamed["IdServicio_den"] = pd.NA
    else:
        renamed = df.rename(
            columns={
                "Servicio de Salud": "servicio_salud_denominador",
                "Dependencia": "dependencia_denominador",
                "Comuna": "comuna_denominador",
                "Código Centro": "IdEstablecimiento",
                "Nombre Centro": "establecimiento_denominador",
                "Sexo": "sexo",
                "Edad": "edad",
                "Inscritos": "inscritos",
            }
        )
        renamed["RegionCodigo"] = "13"
        renamed["RegionGlosa"] = "Región Metropolitana"
        renamed["IdServicio_den"] = pd.NA

    required = [
        "RegionCodigo",
        "RegionGlosa",
        "IdServicio_den",
        "servicio_salud_denominador",
        "dependencia_denominador",
        "IdComuna_den",
        "comuna_denominador",
        "IdEstablecimiento",
        "establecimiento_denominador",
        "sexo",
        "edad",
        "inscritos",
    ]
    for col in required:
        if col not in renamed.columns:
            renamed[col] = pd.NA
    renamed = renamed[required].copy()
    renamed["Ano"] = int(year)
    renamed["IdEstablecimiento"] = code_text(renamed["IdEstablecimiento"])
    renamed["IdComuna_den"] = code_text(renamed["IdComuna_den"])
    renamed["IdServicio_den"] = code_text(renamed["IdServicio_den"])
    renamed["IdEstablecimiento"] = renamed["IdEstablecimiento"].replace(DENOMINATOR_CODE_ALIASES)
    renamed["edad"] = pd.to_numeric(renamed["edad"], errors="coerce")
    renamed["inscritos"] = to_int_series(renamed["inscritos"])
    renamed["sexo"] = renamed["sexo"].astype(str).str.strip()
    renamed["servicio_salud_denominador"] = renamed["servicio_salud_denominador"].astype(str).str.strip()
    renamed["dependencia_denominador"] = renamed["dependencia_denominador"].astype(str).str.strip()
    renamed["comuna_denominador"] = renamed["comuna_denominador"].astype(str).str.strip()
    renamed["establecimiento_denominador"] = renamed["establecimiento_denominador"].astype(str).str.strip()
    return renamed


def requested_age_group(age: pd.Series) -> pd.Series:
    out = pd.Series(index=age.index, dtype="object")
    out.loc[age.between(15, 19, inclusive="both")] = "15_19"
    out.loc[age.between(20, 24, inclusive="both")] = "20_24"
    out.loc[age.between(25, 29, inclusive="both")] = "25_29"
    out.loc[age.between(30, 34, inclusive="both")] = "30_34"
    out.loc[age.between(35, 39, inclusive="both")] = "35_39"
    out.loc[age.between(40, 44, inclusive="both")] = "40_44"
    out.loc[age.between(45, 49, inclusive="both")] = "45_49"
    out.loc[age.between(50, 54, inclusive="both")] = "50_54"
    out.loc[age.between(55, 59, inclusive="both")] = "55_59"
    out.loc[age.between(60, 64, inclusive="both")] = "60_64"
    out.loc[age.ge(65)] = "65_mas"
    return out


def detailed_age_group(age: pd.Series) -> pd.Series:
    out = pd.Series(index=age.index, dtype="object")
    out.loc[age.between(15, 19, inclusive="both")] = "15_19"
    out.loc[age.between(20, 24, inclusive="both")] = "20_24"
    out.loc[age.between(25, 29, inclusive="both")] = "25_29"
    out.loc[age.between(30, 34, inclusive="both")] = "30_34"
    out.loc[age.between(35, 39, inclusive="both")] = "35_39"
    out.loc[age.between(40, 44, inclusive="both")] = "40_44"
    out.loc[age.between(45, 49, inclusive="both")] = "45_49"
    out.loc[age.between(50, 54, inclusive="both")] = "50_54"
    out.loc[age.between(55, 59, inclusive="both")] = "55_59"
    out.loc[age.between(60, 64, inclusive="both")] = "60_64"
    out.loc[age.ge(65)] = "65_mas"
    return out


def load_denominator_detail(config: dict) -> pd.DataFrame:
    sources = config["input_paths"]["denominadores_fonasa"]
    frames = []
    for year, source_cfg in sources.items():
        env_var = f"DENOMINADOR_EMPA_{year}_PATH"
        path = Path(os.environ.get(env_var, source_cfg["path"]))
        for sheet_name in source_cfg["sheets"]:
            raw = load_sheet_with_embedded_header(path, sheet_name, source_cfg["skiprows"])
            standardized = standardize_denominator_frame(year, raw)
            if year in {"2023", "2024"}:
                standardized = standardized[
                    standardized["IdComuna_den"].astype(str).str.startswith("13", na=False)
                ].copy()
            frames.append(standardized)

    detail = pd.concat(frames, ignore_index=True)
    detail = detail[detail["edad"].ge(15)].copy()
    detail["grupo_etario"] = requested_age_group(detail["edad"])
    detail["grupo_etario_detalle"] = detailed_age_group(detail["edad"])
    detail = detail[detail["grupo_etario"].notna() & detail["grupo_etario_detalle"].notna()].copy()
    return detail


def build_denominator_output(detail: pd.DataFrame, master: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    geo_cols = [
        "Ano",
        "IdEstablecimiento",
        "IdComuna_den",
        "comuna_denominador",
        "establecimiento_denominador",
        "servicio_salud_denominador",
        "dependencia_denominador",
    ]

    # Fill NaN in geo columns to prevent pivot_table from silently dropping rows
    # (pandas >= 1.1 drops NaN index entries by default in pivot_table)
    for col in geo_cols:
        if detail[col].isna().any():
            detail[col] = detail[col].fillna("Sin_dato")

    # --- Total (Ambos Sexos) ---
    pivot_total = (
        detail.pivot_table(
            index=geo_cols,
            columns="grupo_etario",
            values="inscritos",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )

    age_value_cols_base = ["15_19", "20_24", "25_29", "30_34", "35_39", "40_44", "45_49", "50_54", "55_59", "60_64", "65_mas"]
    for col in age_value_cols_base:
        if col not in pivot_total.columns:
            pivot_total[col] = 0

    pivot_total["total_15_mas"] = pivot_total[age_value_cols_base].sum(axis=1)

    detail_age_cols = ["15_19", "20_24", "25_29", "30_34", "35_39", "40_44", "45_49", "50_54", "55_59", "60_64"]
    pivot_total["20_64"] = pivot_total[
        ["20_24", "25_29", "30_34", "35_39", "40_44", "45_49", "50_54", "55_59", "60_64"]
    ].sum(axis=1)
    pivot_total["20_54"] = pivot_total[
        ["20_24", "25_29", "30_34", "35_39", "40_44", "45_49", "50_54"]
    ].sum(axis=1)

    out_total = pivot_total.merge(
        master,
        left_on="IdEstablecimiento",
        right_on="IdEstablecimiento_lookup",
        how="left",
    ).drop(columns=["IdEstablecimiento_lookup"])

    out_total = out_total.rename(
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
    out_total["sin_match_master"] = out_total["establecimiento_master"].isna()

    # --- By Sex (Hombres, Mujeres) ---
    sexo_map = {"Hombres": "Hombres_", "Mujeres": "Mujeres_"}
    sex_detail = detail[detail["sexo"].isin(["Hombres", "Mujeres"])].copy()

    geo_sex_cols = geo_cols + ["sexo"]

    pivot_sex = (
        sex_detail.pivot_table(
            index=geo_sex_cols,
            columns="grupo_etario",
            values="inscritos",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )

    for col in age_value_cols_base:
        if col not in pivot_sex.columns:
            pivot_sex[col] = 0

    pivot_sex["total_15_mas"] = pivot_sex[age_value_cols_base].sum(axis=1)
    pivot_sex["sexo"] = pivot_sex["sexo"].map({"Hombres": "Hombre", "Mujeres": "Mujer"})

    pivot_sex["20_64"] = pivot_sex[
        ["20_24", "25_29", "30_34", "35_39", "40_44", "45_49", "50_54", "55_59", "60_64"]
    ].sum(axis=1)
    pivot_sex["20_54"] = pivot_sex[
        ["20_24", "25_29", "30_34", "35_39", "40_44", "45_49", "50_54"]
    ].sum(axis=1)

    # Pivot sexo rows into columns so each row has both Hombre and Mujer columns
    age_value_cols = [
        *age_value_cols_base,
        "total_15_mas",
        "20_64",
        "20_54",
    ]
    pivot_wide = pivot_sex.pivot_table(
        index=geo_cols,
        columns="sexo",
        values=age_value_cols,
        fill_value=0,
    )
    pivot_wide.columns = [f"{col}_{sex}" for col, sex in pivot_wide.columns]
    pivot_wide = pivot_wide.reset_index()

    out_sex = pivot_wide.merge(
        master,
        left_on="IdEstablecimiento",
        right_on="IdEstablecimiento_lookup",
        how="left",
    ).drop(columns=["IdEstablecimiento_lookup"])

    out_sex = out_sex.rename(
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
    out_sex["sin_match_master"] = out_sex["establecimiento_master"].isna()

    control = out_total[
        [
            "Ano",
            "IdEstablecimiento",
            "establecimiento_denominador",
            "establecimiento_master",
            "servicio_salud_denominador",
            "servicio_salud_master",
            "dependencia_denominador",
            "dependencia_master",
            "nivel_atencion_master",
            "es_aps",
            "sin_match_master",
        ]
    ].copy()
    return out_total, out_sex, control


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    config = load_config()
    detail = load_denominator_detail(config)
    master = build_master_lookup(Path(config["input_paths"]["maestro_establecimientos"]))
    denominator_total, denominator_sex, control = build_denominator_output(detail, master)

    detail_path = OUTPUT_DIR / "denominador_empa_detalle_2023_2025.csv"
    denominator_path = OUTPUT_DIR / "denominador_empa_establecimiento_2023_2025.csv"
    denominator_sex_path = OUTPUT_DIR / "denominador_empa_establecimiento_sexo_2023_2025.csv"
    control_path = OUTPUT_DIR / "control_calidad_empa_denominador_2023_2025.csv"

    detail.to_csv(detail_path, index=False, encoding="utf-8-sig")
    denominator_total.to_csv(denominator_path, index=False, encoding="utf-8-sig")
    denominator_sex.to_csv(denominator_sex_path, index=False, encoding="utf-8-sig")
    control.to_csv(control_path, index=False, encoding="utf-8-sig")

    print(f"Escrito: {detail_path}")
    print(f"Escrito: {denominator_path}")
    print(f"Escrito: {denominator_sex_path}")
    print(f"Escrito: {control_path}")
    print(f"Filas detalle denominador: {len(detail):,}")
    print(f"Establecimientos con denominador: {len(denominator_total):,}")
    aps_count = int(denominator_total["es_aps"].eq(True).sum())
    print(f"Establecimientos APS: {aps_count:,}")
    print(f"Sin match en maestro: {int(denominator_total['sin_match_master'].sum()):,}")


if __name__ == "__main__":
    main()
