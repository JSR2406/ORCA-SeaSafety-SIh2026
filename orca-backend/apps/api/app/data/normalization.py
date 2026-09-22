# Data Normalization
# Converts ARGO xarray datasets to normalized pandas DataFrames

import logging
import numpy as np
import pandas as pd
import xarray as xr
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# ARGO standard variable names
ARGO_VARIABLES = {
    "TEMP": "temperature_c",
    "PSAL": "salinity_psu",
    "DOXY": "oxygen_umol_kg",
    "CHLA": "chlorophyll",
    "NITRATE": "nitrate",
    "PH_IN_SITU_TOTAL": "ph",
}

# QC flag meanings
QC_FLAGS = {
    0: "no_qc",
    1: "good",
    2: "probably_good",
    3: "probably_bad",
    4: "bad",
    5: "value_changed",
    8: "estimated",
    9: "missing",
}

RECOMMENDED_QC = {1, 2}
GOOD_ONLY_QC = {1}


def normalize_variable_name(var: str) -> str:
    """Convert ARGO variable name to standard name."""
    return ARGO_VARIABLES.get(var.upper(), var.lower())


def apply_qc_filter(
    df: pd.DataFrame,
    variable: str,
    quality_filter: str = "recommended",
) -> pd.DataFrame:
    """Apply quality control filter to a variable column."""
    qc_col = f"{variable}_qc"
    if qc_col not in df.columns:
        return df

    if quality_filter == "recommended":
        valid_flags = RECOMMENDED_QC
    elif quality_filter == "good_only":
        valid_flags = GOOD_ONLY_QC
    elif quality_filter == "all":
        return df
    else:
        logger.warning(f"Unknown quality filter: {quality_filter}")
        return df

    mask = df[qc_col].isin(valid_flags)
    filtered = df[mask].copy()
    logger.debug(f"QC filter '{quality_filter}' on {variable}: {len(df)} -> {len(filtered)} rows")
    return filtered


def pressure_to_depth(pressure_dbar: np.ndarray, latitude: float) -> np.ndarray:
    """
    Convert pressure (dbar) to depth (m) using UNESCO 1983 equation.
    Simplified: 1 dbar ≈ 1 m for most purposes.
    """
    # For MVP, use approximation. Full TEOS-10 available via gsw package if needed.
    return pressure_dbar * 1.0197  # Approximate conversion


def normalize_dataset(
    ds: xr.Dataset,
    quality_filter: str = "recommended",
    source: str = "argo_gdac",
    source_url: Optional[str] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Convert ARGO xarray Dataset to normalized profile and observation DataFrames.
    
    Returns:
        tuple: (profiles_df, observations_df)
    """
    # Convert to DataFrame - this flattens all dimensions
    df = ds.to_dataframe().reset_index()
    
    if df.empty:
        logger.warning("Empty dataset after conversion")
        return pd.DataFrame(), pd.DataFrame()

    # Rename columns to standard names
    rename_map = {}
    for col in df.columns:
        upper_col = col.upper()
        if upper_col in ARGO_VARIABLES:
            rename_map[col] = ARGO_VARIABLES[upper_col]
        elif upper_col.endswith("_QC"):
            base = upper_col[:-3]
            if base in ARGO_VARIABLES:
                rename_map[col] = f"{ARGO_VARIABLES[base]}_qc"
    
    df = df.rename(columns=rename_map)

    # Ensure required columns exist
    required_profile_cols = ["PLATFORM_NUMBER", "CYCLE_NUMBER", "TIME", "LATITUDE", "LONGITUDE"]
    for col in required_profile_cols:
        if col not in df.columns:
            logger.error(f"Missing required column: {col}")
            return pd.DataFrame(), pd.DataFrame()

    # Create profile DataFrame (one row per profile)
    profile_cols = ["PLATFORM_NUMBER", "CYCLE_NUMBER", "TIME", "LATITUDE", "LONGITUDE"]
    if "DIRECTION" in df.columns:
        profile_cols.append("DIRECTION")
    if "DATA_MODE" in df.columns:
        profile_cols.append("DATA_MODE")
    if "POSITION_QC" in df.columns:
        profile_cols.append("POSITION_QC")

    profiles_df = df[profile_cols].drop_duplicates(subset=["PLATFORM_NUMBER", "CYCLE_NUMBER"]).copy()
    profiles_df = profiles_df.rename(columns={
        "PLATFORM_NUMBER": "platform_number",
        "CYCLE_NUMBER": "cycle_number",
        "TIME": "profile_time",
        "LATITUDE": "latitude",
        "LONGITUDE": "longitude",
        "DIRECTION": "direction",
        "DATA_MODE": "data_mode",
        "POSITION_QC": "position_qc",
    })
    
    profiles_df["source"] = source
    profiles_df["source_url"] = source_url
    profiles_df["qc_status"] = quality_filter
    profiles_df["ingested_at"] = datetime.utcnow()

    # Create observation DataFrame (one row per measurement level)
    obs_cols = ["PLATFORM_NUMBER", "CYCLE_NUMBER"]
    # Add all measurement columns
    for col in df.columns:
        if col not in profile_cols and not col.endswith("_QC") and col not in ["PLATFORM_NUMBER", "CYCLE_NUMBER"]:
            obs_cols.append(col)
        elif col.endswith("_QC"):
            obs_cols.append(col)

    observations_df = df[obs_cols].copy()
    observations_df = observations_df.rename(columns={
        "PLATFORM_NUMBER": "platform_number",
        "CYCLE_NUMBER": "cycle_number",
    })

    # Convert pressure to depth if needed
    if "PRES" in observations_df.columns and "depth_m" not in observations_df.columns:
        observations_df["pressure_dbar"] = observations_df["PRES"]
        # We'll compute depth per profile using latitude
        # For now, approximate
        observations_df["depth_m"] = observations_df["pressure_dbar"] * 1.0197

    # Ensure standard variable columns exist
    for std_name in ["temperature_c", "salinity_psu", "oxygen_umol_kg", "chlorophyll"]:
        if std_name not in observations_df.columns:
            observations_df[std_name] = np.nan
        qc_name = f"{std_name}_qc"
        if qc_name not in observations_df.columns:
            observations_df[qc_name] = np.nan

    observations_df["ingested_at"] = datetime.utcnow()

    logger.info(f"Normalized: {len(profiles_df)} profiles, {len(observations_df)} observations")
    return profiles_df, observations_df


def validate_dataset(
    profiles_df: pd.DataFrame,
    observations_df: pd.DataFrame,
) -> Dict[str, Any]:
    """Validate normalized dataset and return quality report."""
    report = {
        "profile_count": len(profiles_df),
        "observation_count": len(observations_df),
        "float_count": profiles_df["platform_number"].nunique() if not profiles_df.empty else 0,
        "issues": [],
        "warnings": [],
    }

    if profiles_df.empty:
        report["issues"].append("No profiles in dataset")
        return report

    # Check coordinate ranges
    lat_out = profiles_df[
        (profiles_df["latitude"] < -90) | (profiles_df["latitude"] > 90)
    ]
    if not lat_out.empty:
        report["issues"].append(f"{len(lat_out)} profiles with invalid latitude")

    lon_out = profiles_df[
        (profiles_df["longitude"] < -180) | (profiles_df["longitude"] > 180)
    ]
    if not lon_out.empty:
        report["issues"].append(f"{len(lon_out)} profiles with invalid longitude")

    # Check for duplicate profiles
    dupes = profiles_df.duplicated(subset=["platform_number", "cycle_number"]).sum()
    if dupes > 0:
        report["issues"].append(f"{dupes} duplicate platform/cycle combinations")

    # Check time range
    if "profile_time" in profiles_df.columns:
        report["time_range"] = {
            "start": profiles_df["profile_time"].min().isoformat(),
            "end": profiles_df["profile_time"].max().isoformat(),
        }

    # Check observations
    if not observations_df.empty:
        # Depth consistency
        if "depth_m" in observations_df.columns and "pressure_dbar" in observations_df.columns:
            depth_pressure_ratio = observations_df["depth_m"] / observations_df["pressure_dbar"]
            outliers = depth_pressure_ratio[(depth_pressure_ratio < 0.5) | (depth_pressure_ratio > 2.0)]
            if len(outliers) > 0:
                report["warnings"].append(f"{len(outliers)} observations with unusual depth/pressure ratio")

        # Missing value check
        for var in ["temperature_c", "salinity_psu", "oxygen_umol_kg", "chlorophyll"]:
            if var in observations_df.columns:
                missing = observations_df[var].isna().sum()
                total = len(observations_df)
                if missing > 0:
                    report["warnings"].append(f"{var}: {missing}/{total} missing ({missing/total*100:.1f}%)")

    return report