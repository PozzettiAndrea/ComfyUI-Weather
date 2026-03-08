import requests
from datetime import datetime, timedelta, timezone
from comfy_api.latest import io

WEATHER_DATA = io.Custom("WEATHER_DATA")

JUA_MODELS = ["ept2"]

JUA_VARIABLE_PRESETS = {
    "Temperature & Wind": "air_temperature_at_height_level_2m,wind_speed_at_height_level_10m",
    "Full Weather": "air_temperature_at_height_level_2m,relative_humidity_at_height_level_2m,precipitation_amount_sum_1h,wind_speed_at_height_level_10m,cloud_area_fraction_at_entire_atmosphere,air_pressure_at_mean_sea_level",
    "Wind Energy": "wind_speed_at_height_level_10m,wind_speed_at_height_level_100m,wind_direction_at_height_level_10m,wind_direction_at_height_level_100m",
    "Solar Energy": "surface_direct_downwelling_shortwave_flux_sum_1h,surface_downwelling_shortwave_flux_sum_1h,cloud_area_fraction_at_entire_atmosphere",
    "Custom": "",
}

JUA_UNITS = {
    "air_temperature_at_height_level_2m": "K",
    "dew_point_temperature_at_height_level_2m": "K",
    "relative_humidity_at_height_level_2m": "%",
    "wind_speed_at_height_level_10m": "m/s",
    "wind_speed_at_height_level_100m": "m/s",
    "wind_direction_at_height_level_10m": "°",
    "wind_direction_at_height_level_100m": "°",
    "air_pressure_at_mean_sea_level": "Pa",
    "precipitation_amount_sum_1h": "mm",
    "cloud_area_fraction_at_entire_atmosphere": "%",
    "surface_direct_downwelling_shortwave_flux_sum_1h": "W/m²",
    "surface_downwelling_shortwave_flux_sum_1h": "W/m²",
}


class FetchJuaForecast(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_FetchJua",
            display_name="Fetch Jua.ai Forecast",
            category="Weather",
            description="Fetch weather forecast from Jua.ai API (requires API key). Supports EPT-2 model with energy-sector variable presets.",
            inputs=[
                io.String.Input(
                    "api_key",
                    default="",
                    tooltip="Jua.ai API key in format: key_id:key_secret",
                ),
                io.Float.Input(
                    "latitude",
                    default=47.37,
                    min=-90.0,
                    max=90.0,
                    step=0.01,
                ),
                io.Float.Input(
                    "longitude",
                    default=8.54,
                    min=-180.0,
                    max=180.0,
                    step=0.01,
                ),
                io.Combo.Input(
                    "model",
                    options=JUA_MODELS,
                    default="ept2",
                    tooltip="Jua forecast model.",
                ),
                io.Combo.Input(
                    "variable_preset",
                    options=list(JUA_VARIABLE_PRESETS.keys()),
                    default="Temperature & Wind",
                    tooltip="Variable preset. 'Wind Energy' and 'Solar Energy' include height-level variables.",
                ),
                io.String.Input(
                    "custom_variables",
                    default="air_temperature_at_height_level_2m",
                    optional=True,
                    tooltip="Comma-separated Jua variable names. Used when preset is 'Custom'.",
                ),
                io.Int.Input(
                    "max_prediction_hours",
                    default=72,
                    min=1,
                    max=480,
                    step=1,
                    tooltip="Maximum forecast lead time in hours.",
                ),
            ],
            outputs=[
                WEATHER_DATA.Output(display_name="WEATHER_DATA"),
            ],
            not_idempotent=True,
        )

    @classmethod
    def execute(cls, api_key, latitude, longitude, model, variable_preset, max_prediction_hours, custom_variables=""):
        print(f"[Weather] Fetching Jua.ai forecast: ({latitude}, {longitude}), model={model}, preset={variable_preset}, hours={max_prediction_hours}")
        if not api_key or ":" not in api_key:
            raise ValueError("API key must be in format 'key_id:key_secret'. Get one at https://developer.jua.ai/")

        if variable_preset == "Custom":
            variables_str = custom_variables.strip()
            if not variables_str:
                raise ValueError("Specify variables when using 'Custom' preset.")
        else:
            variables_str = JUA_VARIABLE_PRESETS[variable_preset]

        variables_list = [v.strip() for v in variables_str.split(",")]

        resp = requests.get(
            "https://query.jua.ai/v1/forecast/",
            headers={
                "X-API-Key": api_key,
                "Accept": "application/json",
            },
            params={
                "models": model,
                "init_time": "latest",
                "latitude": latitude,
                "longitude": longitude,
                "variables": variables_list,
                "max_prediction_timedelta": f"{max_prediction_hours}h",
            },
            timeout=60,
        )

        if resp.status_code == 401:
            raise RuntimeError("Jua API authentication failed. Check your API key.")
        if resp.status_code == 403:
            raise RuntimeError("Jua API access forbidden. Your subscription may not include this resource.")
        if resp.status_code == 402:
            raise RuntimeError("Jua API: insufficient credits.")
        resp.raise_for_status()

        data = resp.json()

        # Parse response - Jua returns columnar arrays
        # Extract init_time and prediction_timedelta to build timestamps
        init_times = data.get("init_time", [])
        prediction_timedeltas = data.get("prediction_timedelta", [])

        # Build timestamps from init_time + prediction_timedelta
        timestamps = []
        if init_times and prediction_timedeltas:
            try:
                base_time = datetime.fromisoformat(init_times[0].replace("Z", "+00:00"))
            except (ValueError, AttributeError, IndexError):
                base_time = datetime.now(timezone.utc)

            for td_str in prediction_timedeltas:
                # Parse timedelta strings like "1h", "2h", "PT1H", etc.
                hours = _parse_timedelta_hours(td_str)
                ts = base_time + timedelta(hours=hours)
                timestamps.append(ts.strftime("%Y-%m-%dT%H:%M"))

        # Extract variable data
        variables = {}
        num_steps = len(timestamps) if timestamps else 0
        for var_name in variables_list:
            values = data.get(var_name, [])
            if values:
                variables[var_name] = values
                num_steps = max(num_steps, len(values))

        # If we couldn't parse timestamps, generate hourly ones
        if not timestamps and num_steps > 0:
            base_time = datetime.now(timezone.utc)
            timestamps = [
                (base_time + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M")
                for i in range(num_steps)
            ]

        units = {k: JUA_UNITS.get(k, "unknown") for k in variables}
        print(f"[Weather] Jua.ai returned {len(timestamps)} data points for {len(variables)} variables")

        location = {
            "source": f"jua ({model})",
            "latitude": latitude,
            "longitude": longitude,
            "location_name": None,
            "timezone": "UTC",
            "elevation": None,
            "units": units,
            "timestamps": timestamps,
            "variables": variables,
        }

        return io.NodeOutput({"locations": [location]})


def _parse_timedelta_hours(td_str):
    """Parse a timedelta string to hours. Handles '1h', 'PT1H', '3600s', etc."""
    s = str(td_str).strip()

    # Simple "Xh" format
    if s.endswith("h") and s[:-1].replace(".", "").isdigit():
        return float(s[:-1])

    # ISO 8601 duration "PTXhYm" format
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

    # Seconds
    if s.endswith("s") and s[:-1].replace(".", "").isdigit():
        return float(s[:-1]) / 3600

    # Try as raw number (assume hours)
    try:
        return float(s)
    except ValueError:
        return 0
