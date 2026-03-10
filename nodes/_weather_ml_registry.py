"""Model registry and constants for ML weather prediction nodes."""

import os
import folder_paths

# Register model folder
_models_dir = os.path.join(folder_paths.models_dir, "weather_ml")
os.makedirs(_models_dir, exist_ok=True)
folder_paths.add_model_folder_path("weather_ml", _models_dir)

# Model registry: display_name -> metadata
# e2s_module: import path under earth2studio.models.px
WEATHER_ML_MODELS = {
    "Aurora": {
        "e2s_module": "earth2studio.models.px",
        "e2s_class": "Aurora",
        "extra": "aurora",
        "description": "Microsoft Aurora — 0.25° global, 6h steps, 1.3B parameters",
        "license": "Academic/research only",
        "step_hours": 6,
        "resolution": "0.25°",
        "vram_gb": 40,
    },
    "Pangu 24h": {
        "e2s_module": "earth2studio.models.px",
        "e2s_class": "Pangu24",
        "extra": "pangu",
        "description": "Huawei Pangu-Weather — 0.25° global, 24h steps",
        "license": "CC BY-NC-SA 4.0 (non-commercial)",
        "step_hours": 24,
        "resolution": "0.25°",
        "vram_gb": 8,
    },
    "Pangu 6h": {
        "e2s_module": "earth2studio.models.px",
        "e2s_class": "Pangu6",
        "extra": "pangu",
        "description": "Huawei Pangu-Weather — 0.25° global, 6h steps",
        "license": "CC BY-NC-SA 4.0 (non-commercial)",
        "step_hours": 6,
        "resolution": "0.25°",
        "vram_gb": 8,
    },
    "FuXi": {
        "e2s_module": "earth2studio.models.px",
        "e2s_class": "FuXi",
        "extra": "fuxi",
        "description": "FuXi weather model — 0.25° global, 6h steps",
        "license": "CC BY-NC-SA 4.0 (non-commercial)",
        "step_hours": 6,
        "resolution": "0.25°",
        "vram_gb": 8,
    },
}

# Data source registry
DATA_SOURCES = {
    "GFS (latest)": {
        "e2s_class": "GFS",
        "description": "NOAA Global Forecast System — latest analysis (0.25°)",
    },
    "ERA5 (NCAR)": {
        "e2s_class": "NCAR_ERA5",
        "description": "ECMWF ERA5 reanalysis via NSF NCAR (0.25°, 1940–present)",
    },
    "CDS (ERA5)": {
        "e2s_class": "CDS",
        "description": "ECMWF ERA5 via Copernicus CDS API (requires API key)",
    },
}

# Variable display names and units
VAR_DISPLAY = {
    "t2m": ("2m Temperature", "K"),
    "u10m": ("10m U-Wind", "m/s"),
    "v10m": ("10m V-Wind", "m/s"),
    "msl": ("Mean Sea Level Pressure", "Pa"),
    "sp": ("Surface Pressure", "Pa"),
    "tcwv": ("Total Column Water Vapour", "kg/m²"),
    "t850": ("Temperature 850hPa", "K"),
    "t500": ("Temperature 500hPa", "K"),
    "z500": ("Geopotential 500hPa", "m²/s²"),
    "z1000": ("Geopotential 1000hPa", "m²/s²"),
    "u500": ("U-Wind 500hPa", "m/s"),
    "v500": ("V-Wind 500hPa", "m/s"),
    "u850": ("U-Wind 850hPa", "m/s"),
    "v850": ("V-Wind 850hPa", "m/s"),
    "r500": ("Relative Humidity 500hPa", "%"),
    "r850": ("Relative Humidity 850hPa", "%"),
    "q500": ("Specific Humidity 500hPa", "kg/kg"),
    "q850": ("Specific Humidity 850hPa", "kg/kg"),
}


def get_model_list():
    """Return list of model display names."""
    return list(WEATHER_ML_MODELS.keys())


def get_data_source_list():
    """Return list of data source display names."""
    return list(DATA_SOURCES.keys())
