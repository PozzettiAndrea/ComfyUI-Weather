import json
import os
import time
from datetime import datetime, timezone

import numpy as np
import openmeteo_requests
import comfy.model_management
from comfy_api.latest import io

WEATHER_DATA = io.Custom("WEATHER_DATA")
WEATHER_GRID = io.Custom("WEATHER_GRID")
GRID_COORDS = io.Custom("GRID_COORDS")
LATLON_COORDS = io.Custom("LATLON_COORDS")

API_URL = "https://api.open-meteo.com/v1/forecast"

# Model registry: key -> (API value, display name, approx resolution)
# Latlon backend: seamless models (auto-blend resolutions, best for point queries)
LATLON_MODELS = {
    "ecmwf_ifs025":          ("ecmwf_ifs025",          "ECMWF IFS 0.25°",     0.25),
    "gfs_seamless":          ("gfs_seamless",           "GFS (NOAA)",           0.25),
    "icon_seamless":         ("icon_seamless",          "ICON (DWD)",           0.125),
    "meteofrance_seamless":  ("meteofrance_seamless",   "Météo-France",         0.1),
    "ukmo_seamless":         ("ukmo_seamless",          "UKMO",                 0.09),
    "jma_seamless":          ("jma_seamless",           "JMA (Japan)",          0.05),
    "gem_seamless":          ("gem_seamless",           "GEM (Canada)",         0.25),
}

# Grid backend: specific domain models (fixed grid, supports bounding_box)
GRID_MODELS = {
    "ecmwf_ifs025":                    ("ecmwf_ifs025",                    "ECMWF IFS 0.25°",              0.25),
    "icon_global":                     ("icon_global",                     "ICON Global (DWD)",            0.1),
    "icon_eu":                         ("icon_eu",                         "ICON EU (DWD)",                0.0625),
    "icon_d2":                         ("icon_d2",                         "ICON D2 (DWD)",                0.02),
    "meteofrance_arpege_world025":     ("meteofrance_arpege_world025",     "ARPEGE World 0.25°",           0.25),
    "meteofrance_arpege_europe":       ("meteofrance_arpege_europe",       "ARPEGE Europe 0.1°",           0.1),
    "meteofrance_arome_france":        ("meteofrance_arome_france",        "AROME France 0.025°",          0.025),
    "ukmo_global_deterministic_10km":  ("ukmo_global_deterministic_10km",  "UKMO Global 10km",             0.09),
    "gem_global":                      ("gem_global",                      "GEM Global (Canada)",           0.15),
    "jma_gsm":                         ("jma_gsm",                         "JMA GSM (Japan)",              0.5),
    "cma_grapes_global":               ("cma_grapes_global",               "GRAPES Global (CMA)",          0.1),
    "knmi_harmonie_arome_europe":      ("knmi_harmonie_arome_europe",      "HARMONIE AROME (KNMI)",        0.04),
}

# Combined for backward compat (used by _parse_selected_models)
MODELS = {**LATLON_MODELS, **GRID_MODELS}

# --- LatLon backend ---

# --- Grid backend ---

GRID_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "pressure_msl",
    "surface_pressure",
    "cloud_cover",
    "wind_speed_10m",
    "wind_speed_80m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "precipitation",
    "rain",
    "snowfall",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "cape",
    "soil_temperature_0cm",
    "snow_depth",
]

VAR_META = {
    "temperature_2m": ("2m Temperature", "°C"),
    "relative_humidity_2m": ("2m Relative Humidity", "%"),
    "pressure_msl": ("Pressure reduced to MSL", "hPa"),
    "surface_pressure": ("Surface Pressure", "hPa"),
    "cloud_cover": ("Cloud Cover", "%"),
    "wind_speed_10m": ("10m Wind Speed", "m/s"),
    "wind_speed_80m": ("80m Wind Speed", "m/s"),
    "wind_direction_10m": ("10m Wind Direction", "°"),
    "wind_gusts_10m": ("10m Wind Gusts", "m/s"),
    "precipitation": ("Precipitation", "mm"),
    "rain": ("Rain", "mm"),
    "snowfall": ("Snowfall", "cm"),
    "shortwave_radiation": ("Shortwave Radiation", "W/m²"),
    "direct_radiation": ("Direct Radiation", "W/m²"),
    "diffuse_radiation": ("Diffuse Radiation", "W/m²"),
    "cape": ("CAPE", "J/kg"),
    "soil_temperature_0cm": ("Soil Temperature (0cm)", "°C"),
    "snow_depth": ("Snow Depth", "m"),
}

# Shared SDK client
_client = openmeteo_requests.Client()

# API key for Open-Meteo (set via SetOpenMeteoAPIKey node or OPEN_METEO_API_KEY env var)
_api_key = os.environ.get("OPEN_METEO_API_KEY") or None


def _get_api_url():
    """Return the appropriate API URL based on whether an API key is set."""
    if _api_key:
        return "https://customer-api.open-meteo.com/v1/forecast"
    return API_URL


def _api_params(params):
    """Add API key to params if set."""
    if _api_key:
        params["apikey"] = _api_key
    return params


def _fetch_with_retry(url, params, method="GET", max_retries=3):
    """Fetch from Open-Meteo with retry on rate limit."""
    for attempt in range(max_retries):
        comfy.model_management.throw_exception_if_processing_interrupted()
        try:
            if method == "POST":
                return _client.weather_api(url, params=params, method="POST")
            return _client.weather_api(url, params=params)
        except Exception as e:
            if "rate limit" in str(e).lower() or "request limit" in str(e).lower():
                if attempt < max_retries - 1:
                    wait = 15 * (attempt + 1)
                    print(f"[Weather] Rate limited, waiting {wait}s (attempt {attempt+1}/{max_retries})...")
                    # Sleep in 1s increments to allow interrupt checks
                    for _ in range(wait):
                        comfy.model_management.throw_exception_if_processing_interrupted()
                        time.sleep(1)
                    continue
            raise
    raise RuntimeError("Max retries exceeded")


def _parse_selected_models(models_json):
    """Parse JSON model selection string into list of (model_key, api_value)."""
    selected = []
    try:
        keys = json.loads(models_json) if models_json else []
    except (json.JSONDecodeError, TypeError):
        keys = []
    for key in keys:
        if key in MODELS:
            selected.append((key, MODELS[key][0]))
        elif key == "best_match":
            selected.append(("best_match", None))
    if not selected:
        selected = [("best_match", None)]
    return selected


def _response_to_timestamps(hourly):
    """Convert FlatBuffers hourly time range to ISO timestamps."""
    start = hourly.Time()
    end = hourly.TimeEnd()
    interval = hourly.Interval()
    timestamps = []
    t = start
    while t < end:
        timestamps.append(datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M"))
        t += interval
    return timestamps


def _fetch_latlon_single(latitude, longitude, model_key, model_api_value,
                         variables, forecast_hours):
    """Fetch single-point time-series for one model using SDK (FlatBuffers)."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": variables,
        "forecast_hours": forecast_hours,
    }
    if model_api_value:
        params["models"] = model_api_value

    responses = _fetch_with_retry(_get_api_url(), _api_params(params))
    r = responses[0]

    hourly = r.Hourly()
    timestamps = _response_to_timestamps(hourly)

    # Extract all requested variables
    var_data = {}
    units = {}
    for i, var_name in enumerate(variables):
        if i < hourly.VariablesLength():
            arr = hourly.Variables(i).ValuesAsNumpy()
            var_data[var_name] = [float(v) if not np.isnan(v) else None for v in arr]
        else:
            var_data[var_name] = []
        # SDK doesn't return unit strings, use our metadata
        meta = VAR_META.get(var_name)
        if meta:
            units[var_name] = meta[1]

    return {
        "model": model_key,
        "latitude": r.Latitude(),
        "longitude": r.Longitude(),
        "timezone": "UTC",
        "elevation": r.Elevation(),
        "units": units,
        "timestamps": timestamps,
        "variables": var_data,
    }


class FetchWeatherForecast(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_FetchOpenMeteo",
            display_name="Fetch Weather Forecast (Open-Meteo)",
            category="Weather",
            description=(
                "Fetch weather forecast from Open-Meteo. "
                "Enable multiple models to compare forecasts. "
                "Backend 'latlon' returns time-series (WEATHER_DATA). "
                "Backend 'grid' returns a 2D spatial grid (WEATHER_GRID)."
            ),
            inputs=[
                # Hidden JSON string for model selection (managed by JS popup widget)
                io.String.Input(
                    "models_selection",
                    default='["ecmwf_ifs025"]',
                    multiline=False,
                    tooltip="JSON array of selected model keys. Managed by the model selector popup.",
                ),
                # Backend selector with dynamic inputs
                io.DynamicCombo.Input("backend", tooltip="Data mode: single-point time-series or 2D spatial grid.", options=[
                    io.DynamicCombo.Option("latlon", [
                        LATLON_COORDS.Input(
                            "latlon_coords",
                            tooltip="Coordinates from LatLon Collector.",
                        ),
                        io.String.Input(
                            "variables_selection",
                            default='["temperature_2m","wind_speed_10m","wind_direction_10m"]',
                            multiline=False,
                            tooltip="JSON array of selected variable keys. Managed by the variable selector popup.",
                        ),
                        io.Int.Input(
                            "forecast_hours", default=72, min=1, max=384, step=1,
                            tooltip="Number of forecast hours (1-384, i.e. up to 16 days).",
                        ),
                    ]),
                    io.DynamicCombo.Option("grid", [
                        GRID_COORDS.Input(
                            "grid_coords",
                            tooltip="Bounding box from Grid Collector.",
                        ),
                        io.String.Input(
                            "grid_variables_selection",
                            default='["temperature_2m"]',
                            multiline=False,
                            tooltip="JSON array of selected variable keys for grid mode. Managed by the variable selector popup.",
                        ),
                        io.Int.Input(
                            "forecast_hours", default=72, min=1, max=384, step=1,
                            tooltip="Number of forecast hours to fetch (1-384, i.e. up to 16 days).",
                        ),
                    ]),
                ]),
            ],
            outputs=[
                WEATHER_DATA.Output(display_name="WEATHER_DATA"),
                WEATHER_GRID.Output(display_name="WEATHER_GRID"),
                io.String.Output(display_name="Info"),
            ],
            not_idempotent=True,
        )

    @classmethod
    def execute(cls, backend, models_selection='["ecmwf_ifs025"]'):
        selected = backend["backend"]
        selected_models = _parse_selected_models(models_selection)

        if selected == "latlon":
            return cls._execute_latlon(backend, selected_models)
        else:
            return cls._execute_grid(backend, selected_models)

    @classmethod
    def _execute_latlon(cls, backend, selected_models):
        coords = backend["latlon_coords"]
        points = coords.get("points", [])
        # Backward compat: old format had latitude/longitude directly
        if not points and "latitude" in coords:
            points = [{"latitude": coords["latitude"], "longitude": coords["longitude"]}]
        if not points:
            raise ValueError("No coordinates provided.")

        variables_json = backend.get("variables_selection", '["temperature_2m"]')
        forecast_hours = backend["forecast_hours"]

        try:
            variables = json.loads(variables_json) if variables_json else []
        except (json.JSONDecodeError, TypeError):
            variables = []
        if not variables:
            variables = ["temperature_2m"]

        model_names = ", ".join(m[0] for m in selected_models)
        print(f"[Weather] Fetching Open-Meteo latlon: {len(points)} location(s), "
              f"models=[{model_names}], vars={variables}, hours={forecast_hours}")

        locations = []
        info_lines = []

        for pi, pt in enumerate(points):
            comfy.model_management.throw_exception_if_processing_interrupted()
            latitude = pt["latitude"]
            longitude = pt["longitude"]
            print(f"[Weather] Location {pi+1}/{len(points)}: ({latitude:.4f}, {longitude:.4f})")

            model_results = {}
            for model_key, model_api_value in selected_models:
                result = _fetch_latlon_single(
                    latitude, longitude, model_key, model_api_value,
                    variables, forecast_hours,
                )
                model_results[model_key] = result
                print(f"[Weather]   {model_key}: {len(result['timestamps'])} hours, "
                      f"{len(result['variables'])} variables")

            first = next(iter(model_results.values()))
            loc_data = {
                "source": "open-meteo",
                "latitude": first["latitude"],
                "longitude": first["longitude"],
                "location_name": None,
                "timezone": first["timezone"],
                "elevation": first["elevation"],
                "units": first["units"],
                "timestamps": first["timestamps"],
                "variables": first["variables"],
                "models": model_results,
            }
            locations.append(loc_data)

            info_lines.append(f"Location {pi+1}: ({latitude:.2f}, {longitude:.2f})")
            for mk, mr in model_results.items():
                info_lines.append(f"  {mk}: {len(mr['timestamps'])} hours, "
                                  f"{len(mr['variables'])} vars")

        weather_data = {"locations": locations}
        info = "\n".join(info_lines)

        return io.NodeOutput(weather_data, None, info, ui={"text": [info]})

    @classmethod
    def _execute_grid(cls, backend, selected_models):
        coords = backend["grid_coords"]
        lat_south = coords["lat_south"]
        lon_west = coords["lon_west"]
        lat_north = coords["lat_north"]
        lon_east = coords["lon_east"]
        forecast_hours = backend["forecast_hours"]

        # Parse selected variables
        variables_json = backend.get("grid_variables_selection", '["temperature_2m"]')
        try:
            variables = json.loads(variables_json) if variables_json else []
        except (json.JSONDecodeError, TypeError):
            variables = []
        if not variables:
            variables = ["temperature_2m"]

        if lat_south >= lat_north:
            raise ValueError(f"lat_south ({lat_south}) must be less than lat_north ({lat_north})")

        # Filter to grid-compatible models only
        resolved_models = []
        for mk, mv in selected_models:
            if mk in GRID_MODELS:
                resolved_models.append((mk, mv))
            else:
                print(f"[Weather] Ignoring {mk} for grid mode (not a grid-compatible model)")

        if not resolved_models:
            resolved_models = [("ecmwf_ifs025", "ecmwf_ifs025")]

        # Fetch each model's grid for all selected variables
        fields = {}
        all_info_lines = [
            f"Variables: {', '.join(variables)}",
        ]

        for model_key, model_api_value in resolved_models:
            comfy.model_management.throw_exception_if_processing_interrupted()
            grid_result = cls._fetch_single_model_grid(
                variables, model_key, model_api_value,
                lat_south, lon_west, lat_north, lon_east,
                forecast_hours,
            )
            model_info_parts = []
            for variable in variables:
                v3d = grid_result["variables"][variable]
                long_name, unit = VAR_META.get(variable, (variable, ""))
                field_key = f"{model_key}::{variable}" if len(variables) > 1 else model_key
                fields[field_key] = {
                    "variable": variable,
                    "model": model_key,
                    "long_name": f"{long_name} ({model_key})",
                    "unit": unit,
                    "timestamps": grid_result["timestamps"],
                    "latitude": grid_result["latitude"],
                    "longitude": grid_result["longitude"],
                    "values": np.nan_to_num(v3d, nan=0.0).tolist(),
                    "shape": list(v3d.shape),
                }
                model_info_parts.append(
                    f"{variable}: {v3d.shape[0]}t {v3d.shape[1]}x{v3d.shape[2]}, "
                    f"[{np.nanmin(v3d):.2f}, {np.nanmax(v3d):.2f}] {unit}"
                )
            all_info_lines.append(f"Model {model_key}:")
            for part in model_info_parts:
                all_info_lines.append(f"  {part}")

        # init_time = first timestamp in the data (≈ model initialization time)
        first_field = next(iter(fields.values()), {})
        first_ts = (first_field.get("timestamps") or [None])[0]
        init_time = first_ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")

        model_names = [mk for mk, _ in resolved_models]
        grid_data = {
            "fields": fields,
            "model_names": model_names,
            "variables": variables,
            "init_time": init_time,
        }
        all_info_lines.append(f"Models: {', '.join(model_names)}")

        info = "\n".join(all_info_lines)
        print(f"[Weather] Grid ready: {len(resolved_models)} model(s), {len(variables)} variable(s)")

        return io.NodeOutput(None, grid_data, info, ui={"text": [info]})

    @classmethod
    def _fetch_single_model_grid(cls, variables, model_key, model_api_value,
                                  lat_south, lon_west, lat_north, lon_east,
                                  forecast_hours):
        """Fetch grid data for a single model, multiple variables.
        Returns dict with timestamps, latitude, longitude, and
        variables: {var_name: numpy 3D array [T, rows, cols]}."""
        resolution = GRID_MODELS.get(model_key, (None, None, 0.25))[2]

        print(f"[Weather] Fetching Open-Meteo grid: {variables}, model={model_key}, "
              f"bbox=({lat_south},{lon_west},{lat_north},{lon_east}), hours={forecast_hours}")

        est_rows = int((lat_north - lat_south) / resolution) + 1
        est_cols = int((lon_east - lon_west) / resolution) + 1
        est_total = est_rows * est_cols

        max_points = 200000
        if est_total > max_points:
            raise ValueError(
                f"Grid too large: ~{est_total} points ({est_rows}x{est_cols} at {resolution}°). "
                f"Maximum is {max_points:,}. Zoom in or select a coarser model."
            )

        tile_limit = 950
        # Tile in both dimensions to stay under the API's 1000-location limit
        tile_max_cols = min(est_cols, int(tile_limit ** 0.5))
        tile_max_rows = max(1, tile_limit // max(tile_max_cols, 1))
        tile_lat_span = max(resolution, tile_max_rows * resolution)
        tile_lon_span = max(resolution, tile_max_cols * resolution)

        tiles = []
        t_south = lat_south
        while t_south < lat_north:
            t_north = min(t_south + tile_lat_span, lat_north)
            t_west = lon_west
            while t_west < lon_east:
                t_east = min(t_west + tile_lon_span, lon_east)
                tiles.append((t_south, t_west, t_north, t_east))
                t_west = t_east + resolution
            t_south = t_north + resolution

        print(f"[Weather] Estimated {est_total} points, splitting into {len(tiles)} tile(s)")

        # val_lookups[var_name][(lat, lon)] = [time_values]
        val_lookups = {v: {} for v in variables}
        timestamps = None

        for ti, (ts, lw, tn, le) in enumerate(tiles):
            comfy.model_management.throw_exception_if_processing_interrupted()
            bbox_str = f"{ts},{lw},{tn},{le}"
            params = {
                "latitude": (ts + tn) / 2,
                "longitude": (lw + le) / 2,
                "hourly": variables,
                "models": model_api_value,
                "forecast_hours": forecast_hours,
                "bounding_box": bbox_str,
            }

            responses = _fetch_with_retry(_get_api_url(), _api_params(params))
            print(f"[Weather] Tile {ti+1}/{len(tiles)}: {len(responses)} points")

            for i, r in enumerate(responses):
                lat_r = round(r.Latitude(), 4)
                lon_r = round(r.Longitude(), 4)

                hourly = r.Hourly()
                for vi, var_name in enumerate(variables):
                    if vi < hourly.VariablesLength():
                        arr = hourly.Variables(vi).ValuesAsNumpy()
                        values_list = [float(v) if not np.isnan(v) else 0.0 for v in arr]
                    else:
                        values_list = []
                    val_lookups[var_name][(lat_r, lon_r)] = values_list

                if timestamps is None and ti == 0 and i == 0:
                    timestamps = _response_to_timestamps(hourly)

        if timestamps is None:
            timestamps = []

        # Build grid from first variable's coordinates (all share the same grid)
        first_lookup = val_lookups[variables[0]]
        unique_lats = sorted(set(k[0] for k in first_lookup))
        unique_lons = sorted(set(k[1] for k in first_lookup))
        rows = len(unique_lats)
        cols = len(unique_lons)
        n_times = len(timestamps)

        lats_north_top = list(reversed(unique_lats))

        lat_idx = {round(lat, 4): r_idx for r_idx, lat in enumerate(lats_north_top)}
        lon_idx = {round(lon, 4): c_idx for c_idx, lon in enumerate(unique_lons)}

        var_arrays = {}
        for var_name in variables:
            values_3d = np.zeros((n_times, rows, cols))
            for (lat_r, lon_r), time_values in val_lookups[var_name].items():
                ri = lat_idx.get(lat_r)
                ci = lon_idx.get(lon_r)
                if ri is not None and ci is not None:
                    for t in range(min(n_times, len(time_values))):
                        values_3d[t, ri, ci] = time_values[t]
            var_arrays[var_name] = values_3d

        return {
            "timestamps": timestamps,
            "latitude": lats_north_top,
            "longitude": unique_lons,
            "variables": var_arrays,
        }
