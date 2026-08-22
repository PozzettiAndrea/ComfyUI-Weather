import json
import os
import requests
import numpy as np
from datetime import datetime, timedelta, timezone

import comfy.model_management
from comfy_api.latest import io

WEATHER_DATA = io.Custom("WEATHER_DATA")
WEATHER_GRID = io.Custom("WEATHER_GRID")
LATLON_COORDS = io.Custom("LATLON_COORDS")
GRID_COORDS = io.Custom("GRID_COORDS")

# Jua-proprietary models only (third-party models like GraphCast/Aurora
# are accessible via Open-Meteo or Earth2Studio)
JUA_MODELS = {
    "ept2": ("ept2", "EPT-2 (Jua)"),
}

JUA_VAR_META = {
    "air_temperature_at_height_level_2m": ("2m Temperature", "K"),
    "dew_point_temperature_at_height_level_2m": ("2m Dew Point Temperature", "K"),
    "relative_humidity_at_height_level_2m": ("2m Relative Humidity", "%"),
    "wind_speed_at_height_level_10m": ("10m Wind Speed", "m/s"),
    "wind_speed_at_height_level_100m": ("100m Wind Speed", "m/s"),
    "wind_direction_at_height_level_10m": ("10m Wind Direction", "°"),
    "wind_direction_at_height_level_100m": ("100m Wind Direction", "°"),
    "air_pressure_at_mean_sea_level": ("Mean Sea Level Pressure", "Pa"),
    "precipitation_amount_sum_1h": ("Precipitation (1h sum)", "mm"),
    "cloud_area_fraction_at_entire_atmosphere": ("Cloud Cover", "%"),
    "surface_direct_downwelling_shortwave_flux_sum_1h": ("Direct Shortwave Flux (1h)", "W/m²"),
    "surface_downwelling_shortwave_flux_sum_1h": ("Shortwave Flux (1h)", "W/m²"),
}

# Jua grid resolution (~0.081° ~= 9km)
JUA_GRID_RESOLUTION = 0.081

# API key for Jua (set via env var or node input)
_api_key = os.environ.get("JUA_API_KEY") or None

# API endpoints
JUA_POINT_URL = "https://query.jua.ai/v1/forecast/"
JUA_GRID_URL = "https://query.jua.ai/v1/forecast/data"


def _resolve_api_key(api_key_input):
    """Resolve API key from node input or env var."""
    key = api_key_input.strip() if api_key_input else ""
    if not key:
        key = _api_key or ""
    if not key or ":" not in key:
        raise ValueError("API key must be in format 'key_id:key_secret'. Get one at https://developer.jua.ai/")
    return key


def _parse_selected_models(models_json):
    """Parse JSON model selection string into list of (model_key, api_value)."""
    try:
        keys = json.loads(models_json) if models_json else []
    except (json.JSONDecodeError, TypeError):
        keys = []
    selected = []
    for key in keys:
        if key in JUA_MODELS:
            selected.append((key, JUA_MODELS[key][0]))
    if not selected:
        selected = [("ept2", "ept2")]
    return selected


def _parse_variables(variables_json):
    """Parse JSON variable selection string."""
    try:
        variables = json.loads(variables_json) if variables_json else []
    except (json.JSONDecodeError, TypeError):
        variables = []
    if not variables:
        variables = ["air_temperature_at_height_level_2m"]
    return variables


def _check_jua_response(resp):
    """Check Jua API response for errors."""
    if resp.status_code == 401:
        raise RuntimeError("Jua API authentication failed. Check your API key.")
    if resp.status_code == 403:
        raise RuntimeError("Jua API access forbidden. Your subscription may not include this resource.")
    if resp.status_code == 402:
        raise RuntimeError("Jua API: insufficient credits.")
    resp.raise_for_status()


class FetchJuaForecast(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_FetchJua",
            display_name="Fetch Jua.ai Forecast",
            category="Weather",
            description=(
                "Fetch weather forecast from Jua.ai API (requires API key). "
                "Backend 'latlon' returns time-series (WEATHER_DATA). "
                "Backend 'grid' returns a 2D spatial grid (WEATHER_GRID)."
            ),
            inputs=[
                io.String.Input(
                    "api_key",
                    default="",
                    tooltip="Jua.ai API key in format: key_id:key_secret. Also reads JUA_API_KEY env var.",
                ),
                io.String.Input(
                    "models_selection",
                    default='["ept2"]',
                    multiline=False,
                    tooltip="JSON array of selected model keys. Managed by the model selector popup.",
                ),
                io.DynamicCombo.Input("backend", tooltip="Data mode: single-point time-series or 2D spatial grid.", options=[
                    io.DynamicCombo.Option("latlon", [
                        LATLON_COORDS.Input(
                            "latlon_coords",
                            tooltip="Coordinates from LatLon Collector.",
                        ),
                        io.String.Input(
                            "variables_selection",
                            default='["air_temperature_at_height_level_2m","wind_speed_at_height_level_10m"]',
                            multiline=False,
                            tooltip="JSON array of selected variable keys. Managed by the variable selector popup.",
                        ),
                        io.Int.Input(
                            "max_prediction_hours", default=72, min=1, max=480, step=1,
                            tooltip="Maximum forecast lead time in hours.",
                        ),
                    ]),
                    io.DynamicCombo.Option("grid", [
                        GRID_COORDS.Input(
                            "grid_coords",
                            tooltip="Bounding box from Grid Collector.",
                        ),
                        io.String.Input(
                            "grid_variables_selection",
                            default='["air_temperature_at_height_level_2m"]',
                            multiline=False,
                            tooltip="JSON array of selected variable keys for grid mode. Managed by the variable selector popup.",
                        ),
                        io.Int.Input(
                            "max_prediction_hours", default=72, min=1, max=480, step=1,
                            tooltip="Maximum forecast lead time in hours.",
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
    def execute(cls, api_key, backend, models_selection='["ept2"]'):
        key = _resolve_api_key(api_key)
        selected_models = _parse_selected_models(models_selection)
        selected = backend["backend"]

        if selected == "latlon":
            return cls._execute_latlon(key, backend, selected_models)
        else:
            return cls._execute_grid(key, backend, selected_models)

    @classmethod
    def _execute_latlon(cls, api_key, backend, selected_models):
        coords = backend["latlon_coords"]
        points = coords.get("points", [])
        if not points and "latitude" in coords:
            points = [{"latitude": coords["latitude"], "longitude": coords["longitude"]}]
        if not points:
            raise ValueError("No coordinates provided. Connect a LatLon Collector.")

        variables = _parse_variables(backend.get("variables_selection", "[]"))
        max_hours = backend["max_prediction_hours"]

        model_names = ", ".join(m[0] for m in selected_models)
        print(f"[Weather] Fetching Jua.ai latlon: {len(points)} location(s), "
              f"models=[{model_names}], vars={len(variables)}, hours={max_hours}")

        locations = []
        info_lines = []

        for pi, pt in enumerate(points):
            comfy.model_management.throw_exception_if_processing_interrupted()
            latitude = pt["latitude"]
            longitude = pt["longitude"]
            print(f"[Weather] Location {pi+1}/{len(points)}: ({latitude:.4f}, {longitude:.4f})")

            model_results = {}
            for model_key, model_api_value in selected_models:
                result = cls._fetch_point(
                    api_key, latitude, longitude, model_api_value,
                    variables, max_hours,
                )
                model_results[model_key] = result
                print(f"[Weather]   {model_key}: {len(result['timestamps'])} steps, "
                      f"{len(result['variables'])} variables")

            first = next(iter(model_results.values()))
            loc_data = {
                "source": f"jua ({model_names})",
                "latitude": latitude,
                "longitude": longitude,
                "location_name": None,
                "timezone": "UTC",
                "elevation": None,
                "units": first["units"],
                "timestamps": first["timestamps"],
                "variables": first["variables"],
                "models": model_results,
            }
            locations.append(loc_data)

            info_lines.append(f"Location {pi+1}: ({latitude:.2f}, {longitude:.2f})")
            for mk, mr in model_results.items():
                info_lines.append(f"  {mk}: {len(mr['timestamps'])} steps, "
                                  f"{len(mr['variables'])} vars")

        weather_data = {"locations": locations}
        info = "\n".join(info_lines)

        return io.NodeOutput(weather_data, None, info)

    @classmethod
    def _execute_grid(cls, api_key, backend, selected_models):
        coords = backend["grid_coords"]
        lat_south = coords["lat_south"]
        lon_west = coords["lon_west"]
        lat_north = coords["lat_north"]
        lon_east = coords["lon_east"]
        max_hours = backend["max_prediction_hours"]

        variables = _parse_variables(backend.get("grid_variables_selection", "[]"))

        if lat_south >= lat_north:
            raise ValueError(f"lat_south ({lat_south}) must be less than lat_north ({lat_north})")

        model_names_str = ", ".join(m[0] for m in selected_models)
        print(f"[Weather] Fetching Jua.ai grid: vars={variables}, "
              f"models=[{model_names_str}], bbox=({lat_south},{lon_west},{lat_north},{lon_east}), hours={max_hours}")

        fields = {}
        all_info_lines = [f"Variables: {', '.join(variables)}"]
        init_time = None

        for model_key, model_api_value in selected_models:
            comfy.model_management.throw_exception_if_processing_interrupted()

            for variable in variables:
                grid_result = cls._fetch_grid_single(
                    api_key, model_api_value, variable,
                    lat_south, lon_west, lat_north, lon_east,
                    max_hours,
                )

                if init_time is None:
                    init_time = grid_result.get("init_time")

                v3d = grid_result["values"]
                long_name, unit = JUA_VAR_META.get(variable, (variable, ""))
                field_key = f"{model_key}::{variable}" if len(variables) > 1 else model_key
                fields[field_key] = {
                    "variable": variable,
                    "model": model_key,
                    "long_name": f"{long_name} ({model_key})",
                    "unit": unit,
                    "timestamps": grid_result["timestamps"],
                    "latitude": grid_result["latitude"],
                    "longitude": grid_result["longitude"],
                    "values": v3d.tolist(),
                    "shape": list(v3d.shape),
                }
                all_info_lines.append(
                    f"{model_key}::{variable}: {v3d.shape[0]}t {v3d.shape[1]}x{v3d.shape[2]}, "
                    f"[{np.nanmin(v3d):.2f}, {np.nanmax(v3d):.2f}] {unit}"
                )

        model_names = [mk for mk, _ in selected_models]
        grid_data = {
            "fields": fields,
            "model_names": model_names,
            "variables": variables,
            "init_time": init_time,
        }
        all_info_lines.append(f"Models: {', '.join(model_names)}")

        info = "\n".join(all_info_lines)
        print(f"[Weather] Jua grid ready: {len(selected_models)} model(s), {len(variables)} variable(s)")

        return io.NodeOutput(None, grid_data, info)

    @classmethod
    def _fetch_point(cls, api_key, latitude, longitude, model, variables, max_hours):
        """Fetch single-point time-series for one model from Jua API (GET)."""
        resp = requests.get(
            JUA_POINT_URL,
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            params={
                "models": model,
                "init_time": "latest",
                "latitude": latitude,
                "longitude": longitude,
                "variables": variables,
                "max_prediction_timedelta": f"{max_hours}h",
            },
            timeout=60,
        )
        _check_jua_response(resp)
        data = resp.json()

        timestamps, base_time = _parse_jua_timestamps(data)

        var_data = {}
        num_steps = len(timestamps)
        for var_name in variables:
            values = data.get(var_name, [])
            if values:
                var_data[var_name] = values
                num_steps = max(num_steps, len(values))

        if not timestamps and num_steps > 0:
            base_time = datetime.now(timezone.utc)
            timestamps = [
                (base_time + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M")
                for i in range(num_steps)
            ]

        units = {k: JUA_VAR_META.get(k, (k, "unknown"))[1] for k in var_data}

        return {
            "model": model,
            "latitude": latitude,
            "longitude": longitude,
            "timezone": "UTC",
            "elevation": None,
            "units": units,
            "timestamps": timestamps,
            "variables": var_data,
        }

    @classmethod
    def _fetch_grid_single(cls, api_key, model, variable,
                           lat_south, lon_west, lat_north, lon_east,
                           max_hours):
        """Fetch grid data for one variable via Jua POST /v1/forecast/data with BoundingBox."""
        payload = {
            "model": model,
            "init_time": "latest",
            "variables": [variable],
            "max_prediction_timedelta": f"{max_hours}h",
            "geo": {
                "type": "BoundingBox",
                "value": [[lat_south, lon_west], [lat_north, lon_east]],
            },
        }

        print(f"[Weather] Jua grid POST: {variable}, model={model}, "
              f"bbox=({lat_south},{lon_west},{lat_north},{lon_east})")

        resp = requests.post(
            JUA_GRID_URL,
            headers={
                "X-API-Key": api_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        _check_jua_response(resp)
        data = resp.json()

        # Parse response structure
        # Jua grid response contains latitude[], longitude[], prediction_timedelta[], init_time[], and variable data
        lats = data.get("latitude", [])
        lons = data.get("longitude", [])
        timestamps, base_time = _parse_jua_timestamps(data)

        init_time_str = None
        init_times = data.get("init_time", [])
        if init_times:
            init_time_str = str(init_times[0])

        # Variable data: flat array indexed as [time][lat][lon]
        var_values = data.get(variable, [])

        # Build unique sorted lat/lon arrays
        unique_lats = sorted(set(round(l, 4) for l in lats), reverse=True)  # north-top
        unique_lons = sorted(set(round(l, 4) for l in lons))
        n_times = len(timestamps)
        rows = len(unique_lats)
        cols = len(unique_lons)

        if rows == 0 or cols == 0:
            raise RuntimeError(f"Jua returned empty grid: {rows}x{cols}")

        # If data is a flat list with lat/lon arrays of same length (columnar format)
        # Each entry corresponds to one (time, lat, lon) combination
        if isinstance(var_values, list) and len(lats) == len(var_values):
            lat_idx = {round(lat, 4): i for i, lat in enumerate(unique_lats)}
            lon_idx = {round(lon, 4): i for i, lon in enumerate(unique_lons)}

            values_3d = np.zeros((n_times, rows, cols))
            n_points = len(lats)
            points_per_time = n_points // max(n_times, 1)

            for i, val in enumerate(var_values):
                t = i // points_per_time if points_per_time > 0 else 0
                if t >= n_times:
                    break
                lat_r = round(lats[i], 4)
                lon_r = round(lons[i], 4)
                ri = lat_idx.get(lat_r)
                ci = lon_idx.get(lon_r)
                if ri is not None and ci is not None:
                    try:
                        values_3d[t, ri, ci] = float(val) if val is not None else 0.0
                    except (TypeError, ValueError):
                        values_3d[t, ri, ci] = 0.0
        elif isinstance(var_values, list) and len(var_values) > 0 and isinstance(var_values[0], list):
            # Nested array format [time][spatial]
            values_3d = np.zeros((n_times, rows, cols))
            for t in range(min(n_times, len(var_values))):
                frame = var_values[t]
                if isinstance(frame, list) and len(frame) == rows * cols:
                    values_3d[t] = np.array(frame).reshape(rows, cols)
        else:
            values_3d = np.zeros((max(n_times, 1), rows, cols))

        values_3d = np.nan_to_num(values_3d, nan=0.0)

        return {
            "timestamps": timestamps,
            "latitude": unique_lats,
            "longitude": unique_lons,
            "values": values_3d,
            "init_time": init_time_str,
        }


def _parse_jua_timestamps(data):
    """Parse Jua response timestamps. Returns (timestamps_list, base_time)."""
    init_times = data.get("init_time", [])
    prediction_timedeltas = data.get("prediction_timedelta", [])

    base_time = None
    timestamps = []
    if init_times and prediction_timedeltas:
        try:
            base_time = datetime.fromisoformat(str(init_times[0]).replace("Z", "+00:00"))
        except (ValueError, AttributeError, IndexError):
            base_time = datetime.now(timezone.utc)

        seen = set()
        for td_str in prediction_timedeltas:
            hours = _parse_timedelta_hours(td_str)
            ts = base_time + timedelta(hours=hours)
            ts_str = ts.strftime("%Y-%m-%dT%H:%M")
            if ts_str not in seen:
                timestamps.append(ts_str)
                seen.add(ts_str)

    return timestamps, base_time


def _parse_timedelta_hours(td_str):
    """Parse a timedelta string to hours. Handles '1h', 'PT1H', '3600s', etc."""
    s = str(td_str).strip()

    if s.endswith("h") and s[:-1].replace(".", "").isdigit():
        return float(s[:-1])

    if s.startswith("PT"):
        s = s[2:]
        hours = 0
        if "H" in s:
            h_part, s = s.split("H", 1)
            hours += float(h_part)
        if "M" in s:
            m_part, s = s.split("M", 1)
            hours += float(m_part) / 60
        return hours

    if s.endswith("s") and s[:-1].replace(".", "").isdigit():
        return float(s[:-1]) / 3600

    try:
        return float(s)
    except ValueError:
        return 0
