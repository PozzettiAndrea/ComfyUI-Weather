"""Predict Weather node — runs ML weather forecast using Earth2Studio models."""

import importlib
from datetime import datetime, timezone

import numpy as np
import torch
import comfy.model_management as mm
from comfy_api.latest import io
from comfy.utils import ProgressBar

from ._weather_ml_registry import (
    DATA_SOURCES, VAR_DISPLAY,
    get_data_source_list,
)

WEATHER_MODEL = io.Custom("WEATHER_MODEL")
WEATHER_GRID = io.Custom("WEATHER_GRID")

# Common surface variables to extract
DEFAULT_OUTPUT_VARS = [
    "t2m", "u10m", "v10m", "msl",
    "t850", "z500", "u500", "v500",
]


class PredictWeather(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_Predict",
            display_name="Predict Weather",
            category="Weather",
            description=(
                "Run ML weather forecast using a loaded model. "
                "Fetches initial conditions automatically from GFS or ERA5, "
                "runs autoregressive prediction, and outputs a WEATHER_GRID."
            ),
            inputs=[
                WEATHER_MODEL.Input(
                    "weather_model",
                    tooltip="Loaded weather model from (Down)Load Weather Model node.",
                ),
                io.Combo.Input(
                    "data_source",
                    options=get_data_source_list(),
                    default=get_data_source_list()[0],
                    tooltip="Data source for initial conditions.",
                ),
                io.Int.Input(
                    "forecast_steps",
                    default=4,
                    min=1,
                    max=40,
                    step=1,
                    tooltip="Number of model time steps to forecast. Total hours = steps × model step size.",
                ),
            ],
            outputs=[
                WEATHER_GRID.Output(display_name="WEATHER_GRID"),
                io.String.Output(display_name="Info"),
            ],
        )

    @classmethod
    def execute(cls, weather_model, data_source="GFS (latest)", forecast_steps=4):
        model = weather_model["model"]
        model_name = weather_model["model_name"]
        meta = weather_model["metadata"]
        device = weather_model["device"]
        model_vars = weather_model["variables"]
        step_hours = meta["step_hours"]

        total_hours = forecast_steps * step_hours
        print(f"[Weather ML] Predicting: {model_name}, {forecast_steps} steps "
              f"({total_hours}h), source={data_source}")

        # Fetch initial conditions
        mm.throw_exception_if_processing_interrupted()
        print(f"[Weather ML] Fetching initial conditions from {data_source}...")
        x, coords, init_time = cls._fetch_initial_conditions(
            model, data_source, device,
        )
        print(f"[Weather ML] Initial conditions: tensor {list(x.shape)}, "
              f"{len(coords.get('variable', []))} vars, init={init_time}")

        # Run autoregressive forecast
        pbar = ProgressBar(forecast_steps + 1)
        all_steps = []  # List of (tensor, coords) per timestep

        iterator = model.create_iterator(x, coords)
        for step, (x_out, coords_out) in enumerate(iterator):
            mm.throw_exception_if_processing_interrupted()
            all_steps.append((x_out.cpu(), {k: np.array(v) if not isinstance(v, np.ndarray) else v
                                             for k, v in coords_out.items()}))
            pbar.update(1)
            print(f"[Weather ML] Step {step}/{forecast_steps}: "
                  f"lead_time={coords_out.get('lead_time', ['?'])}")
            if step >= forecast_steps:
                break

        # Convert to WEATHER_GRID
        grid_data = cls._to_weather_grid(all_steps, model_name, model_vars)
        grid_data["init_time"] = init_time

        # Build info
        n_fields = len(grid_data.get("fields", {}))
        n_times = len(all_steps)
        info_lines = [
            f"Model: {model_name} ({meta['e2s_class']})",
            f"Forecast: {forecast_steps} steps × {step_hours}h = {total_hours}h",
            f"Data source: {data_source}",
            f"Output fields: {n_fields}",
            f"Timesteps: {n_times}",
        ]
        info = "\n".join(info_lines)
        print(f"[Weather ML] Forecast complete: {n_fields} fields, {n_times} timesteps")

        return io.NodeOutput(grid_data, info)

    @classmethod
    def _fetch_initial_conditions(cls, model, data_source_name, device):
        """Fetch initial conditions using Earth2Studio data sources."""
        from earth2studio.data import fetch_data

        # Import data source class
        ds_meta = DATA_SOURCES[data_source_name]
        data_module = importlib.import_module("earth2studio.data")
        data_cls = getattr(data_module, ds_meta["e2s_class"])
        source = data_cls()

        # Get model's required input coordinates
        input_coords = model.input_coords()

        # Use current time (most recent analysis)
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        # Round to nearest 6-hour cycle
        hour = (now.hour // 6) * 6
        now = now.replace(hour=hour)
        time_arr = np.array([np.datetime64(now.strftime("%Y-%m-%dT%H:%M"))])

        x, coords = fetch_data(
            source=source,
            time=time_arr,
            variable=input_coords["variable"],
            lead_time=input_coords.get("lead_time", np.array([np.timedelta64(0, "h")])),
            device=device,
        )

        init_time = now.strftime("%Y-%m-%dT%H:%M")
        return x, coords, init_time

    @classmethod
    def _to_weather_grid(cls, all_steps, model_name, model_vars):
        """Convert forecast steps to WEATHER_GRID format."""
        if not all_steps:
            return {"fields": {}, "model_names": [model_name], "variables": []}

        # Each step: (tensor [batch, lead_time, variable, lat, lon], coords dict)
        # Collect all timesteps for each variable
        first_tensor, first_coords = all_steps[0]
        var_names = list(first_coords.get("variable", model_vars))
        lat = first_coords.get("lat", np.array([]))
        lon = first_coords.get("lon", np.array([]))

        # Build timestamps from lead_time or step index
        timestamps = []
        for step_idx, (_, step_coords) in enumerate(all_steps):
            lt = step_coords.get("lead_time", np.array([0]))
            if len(lt) > 0:
                # lead_time is typically in hours as timedelta64
                try:
                    hours = int(lt[0] / np.timedelta64(1, "h"))
                    timestamps.append(f"+{hours}h")
                except (TypeError, ValueError):
                    timestamps.append(f"step_{step_idx}")
            else:
                timestamps.append(f"step_{step_idx}")

        # Build fields: one field per variable, containing all timesteps
        fields = {}
        output_variables = []

        for vi, var_name in enumerate(var_names):
            # Collect this variable across all timesteps
            var_values = []
            for tensor, _ in all_steps:
                # tensor shape: [batch, lead_time, variable, lat, lon]
                # Take first batch, first lead_time
                if tensor.ndim == 5:
                    val = tensor[0, 0, vi].numpy()
                elif tensor.ndim == 4:
                    val = tensor[0, vi].numpy()
                elif tensor.ndim == 3:
                    val = tensor[vi].numpy()
                else:
                    continue
                var_values.append(val)

            if not var_values:
                continue

            values_3d = np.stack(var_values, axis=0)  # [T, lat, lon]
            values_3d = np.nan_to_num(values_3d, nan=0.0)

            long_name, unit = VAR_DISPLAY.get(
                var_name, (var_name, "")
            )

            field_key = f"{model_name}::{var_name}" if len(var_names) > 1 else var_name
            fields[field_key] = {
                "variable": var_name,
                "model": model_name,
                "long_name": f"{long_name} ({model_name})",
                "unit": unit,
                "timestamps": timestamps,
                "latitude": lat.tolist() if isinstance(lat, np.ndarray) else list(lat),
                "longitude": lon.tolist() if isinstance(lon, np.ndarray) else list(lon),
                "values": values_3d.tolist(),
                "shape": list(values_3d.shape),
            }
            output_variables.append(var_name)

        return {
            "fields": fields,
            "model_names": [model_name],
            "variables": output_variables,
        }
