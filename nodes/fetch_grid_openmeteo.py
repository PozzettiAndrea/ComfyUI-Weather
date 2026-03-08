import requests
import numpy as np
import comfy.model_management
from comfy_api.latest import io

WEATHER_GRID = io.Custom("WEATHER_GRID")

GRID_MODELS = {
    "best_match": None,
    "ecmwf_ifs025": "ecmwf_ifs025",
    "gfs_seamless": "gfs_seamless",
    "icon_seamless": "icon_seamless",
    "meteofrance_seamless": "meteofrance_seamless",
    "ukmo_seamless": "ukmo_seamless",
    "jma_seamless": "jma_seamless",
    "gem_seamless": "gem_seamless",
}

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

# Variable metadata (long_name, unit)
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

BBOX_PRESETS = {
    "Global": (-90, -180, 90, 180),
    "Europe": (35, -15, 72, 45),
    "North America": (15, -170, 75, -50),
    "South America": (-60, -85, 15, -30),
    "Africa": (-40, -20, 40, 55),
    "Asia": (0, 40, 75, 180),
    "Australia & Oceania": (-50, 100, 0, 180),
    "Arctic": (60, -180, 90, 180),
    "Antarctic": (-90, -180, -60, 180),
    "Custom": (0, 0, 0, 0),
}


class FetchGridForecast(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_FetchGridOpenMeteo",
            display_name="Fetch Grid Forecast (Open-Meteo)",
            category="Weather",
            description=(
                "Fetch a gridded weather forecast from Open-Meteo. "
                "Returns a 2D lat/lon grid (WEATHER_GRID) that can be viewed with Preview Weather Grid. "
                "Uses Open-Meteo's native model grid resolution."
            ),
            inputs=[
                io.Combo.Input(
                    "region",
                    options=list(BBOX_PRESETS.keys()),
                    default="Europe",
                    tooltip="Predefined bounding box, or 'Custom' to specify your own.",
                ),
                io.Float.Input("lat_south", default=-90, min=-90, max=90, step=0.1,
                               tooltip="Southern latitude (only used with 'Custom' region)."),
                io.Float.Input("lon_west", default=-180, min=-180, max=360, step=0.1,
                               tooltip="Western longitude (only used with 'Custom' region)."),
                io.Float.Input("lat_north", default=90, min=-90, max=90, step=0.1,
                               tooltip="Northern latitude (only used with 'Custom' region)."),
                io.Float.Input("lon_east", default=180, min=-180, max=360, step=0.1,
                               tooltip="Eastern longitude (only used with 'Custom' region)."),
                io.Combo.Input(
                    "variable",
                    options=GRID_VARIABLES,
                    default="temperature_2m",
                    tooltip="Weather variable to fetch.",
                ),
                io.Combo.Input(
                    "model",
                    options=list(GRID_MODELS.keys()),
                    default="best_match",
                    tooltip="NWP model backend.",
                ),
                io.Int.Input(
                    "forecast_hour",
                    default=0, min=0, max=384, step=1,
                    tooltip="Forecast hour offset from now (0 = current/analysis).",
                ),
            ],
            outputs=[
                WEATHER_GRID.Output(display_name="WEATHER_GRID"),
                io.String.Output(display_name="Grid Info"),
            ],
            not_idempotent=True,
        )

    @classmethod
    def execute(cls, region, lat_south, lon_west, lat_north, lon_east,
                variable, model, forecast_hour):
        # Resolve bounding box
        if region != "Custom":
            lat_south, lon_west, lat_north, lon_east = BBOX_PRESETS[region]

        if lat_south >= lat_north:
            raise ValueError(f"lat_south ({lat_south}) must be less than lat_north ({lat_north})")

        print(f"[Weather] Fetching Open-Meteo grid: {variable}, model={model}, "
              f"bbox=({lat_south},{lon_west},{lat_north},{lon_east}), hour={forecast_hour}")

        # Build API request with bounding box
        # Open-Meteo expects: latitude=lat1,lat2&longitude=lon1,lon2
        # for bounding box mode (undocumented but supported)
        params = {
            "latitude": f"{lat_south},{lat_north}",
            "longitude": f"{lon_west},{lon_east}",
            "hourly": variable,
            "forecast_hours": min(forecast_hour + 1, 384),
            "forecast_days": max(1, (forecast_hour // 24) + 1),
        }

        model_value = GRID_MODELS.get(model)
        if model_value:
            params["models"] = model_value

        # Open-Meteo doesn't have a native grid endpoint that returns a 2D array.
        # We construct a grid of lat/lon points and query them all.
        # Model native resolution is typically 0.25° (ECMWF, GFS).
        resolution = 0.25
        if model in ("icon_seamless",):
            resolution = 0.125  # ICON is higher res

        lats = np.arange(lat_south, lat_north + resolution / 2, resolution)
        lons = np.arange(lon_west, lon_east + resolution / 2, resolution)

        # Cap grid size to avoid enormous requests
        max_points = 10000
        total = len(lats) * len(lons)
        if total > max_points:
            # Increase resolution to fit
            factor = np.sqrt(total / max_points)
            resolution = resolution * factor
            lats = np.arange(lat_south, lat_north + resolution / 2, resolution)
            lons = np.arange(lon_west, lon_east + resolution / 2, resolution)
            total = len(lats) * len(lons)
            print(f"[Weather] Reduced resolution to {resolution:.3f}° ({len(lats)}x{len(lons)} = {total} points)")

        # Build coordinate pairs for every grid point
        lat_list = []
        lon_list = []
        for lat in lats:
            for lon in lons:
                lat_list.append(round(float(lat), 4))
                lon_list.append(round(float(lon), 4))

        print(f"[Weather] Querying {len(lat_list)} grid points ({len(lats)}x{len(lons)})...")

        # Query in batches (Open-Meteo may limit URL length)
        batch_size = 500
        all_values = []
        all_returned_lats = []
        all_returned_lons = []

        for i in range(0, len(lat_list), batch_size):
            comfy.model_management.throw_exception_if_processing_interrupted()
            batch_lats = lat_list[i:i + batch_size]
            batch_lons = lon_list[i:i + batch_size]

            batch_params = {
                "latitude": ",".join(str(x) for x in batch_lats),
                "longitude": ",".join(str(x) for x in batch_lons),
                "hourly": variable,
                "forecast_days": max(1, (forecast_hour // 24) + 1),
            }
            if model_value:
                batch_params["models"] = model_value

            resp = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params=batch_params,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                raise RuntimeError(f"Open-Meteo error: {data.get('reason', data['error'])}")

            # Single point returns a dict, multiple returns a list
            if isinstance(data, list):
                results = data
            else:
                results = [data]

            for r in results:
                hourly = r.get("hourly", {})
                times = hourly.get("time", [])
                vals = hourly.get(variable, [])

                # Pick the requested forecast hour
                idx = min(forecast_hour, len(vals) - 1) if vals else 0
                value = vals[idx] if vals else 0.0
                if value is None:
                    value = 0.0

                all_values.append(float(value))
                all_returned_lats.append(r.get("latitude", batch_lats[len(all_returned_lats) - len(all_returned_lats)]))
                all_returned_lons.append(r.get("longitude", 0))

                # Get timestamp from first result
                if len(all_values) == 1 and times:
                    timestamp = times[min(forecast_hour, len(times) - 1)]

            print(f"[Weather] Batch {i // batch_size + 1}: fetched {len(results)} points")

        # Reshape into 2D grid (lats descending = north at top)
        rows = len(lats)
        cols = len(lons)
        values_2d = np.array(all_values[:rows * cols]).reshape(rows, cols)

        # Flip so north is at top (lats descending)
        lats_sorted = np.sort(lats)[::-1]  # descending
        values_2d = np.flipud(values_2d)

        long_name, unit = VAR_META.get(variable, (variable, ""))

        # Get timestamp
        ts = timestamp if 'timestamp' in dir() else "unknown"

        grid_data = {
            "variable": variable,
            "long_name": long_name,
            "unit": unit,
            "timestamp": ts,
            "latitude": lats_sorted.tolist(),
            "longitude": lons.tolist(),
            "values": np.nan_to_num(values_2d, nan=0.0).tolist(),
            "shape": [rows, cols],
        }

        lat_step = abs(lats[1] - lats[0]) if len(lats) > 1 else 0
        lon_step = abs(lons[1] - lons[0]) if len(lons) > 1 else 0

        info_lines = [
            f"Variable: {variable} ({long_name})",
            f"Unit: {unit}",
            f"Timestamp: {ts}",
            f"Model: {model}",
            f"Grid: {rows} x {cols} ({lat_step:.4f}° x {lon_step:.4f}°)",
            f"Lat: {lats.min():.2f}° to {lats.max():.2f}°",
            f"Lon: {lons.min():.2f}° to {lons.max():.2f}°",
            f"Value range: {values_2d.min():.2f} to {values_2d.max():.2f} {unit}",
        ]
        grid_info = "\n".join(info_lines)

        print(f"[Weather] Grid ready: {rows}x{cols}, {variable} [{unit}], "
              f"range [{values_2d.min():.1f}, {values_2d.max():.1f}]")

        return io.NodeOutput(grid_data, grid_info)
