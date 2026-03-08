import os
import json
import time
import numpy as np
import folder_paths
from comfy_api.latest import io

WEATHER_GRID = io.Custom("WEATHER_GRID")


class PreviewWeatherGridDual(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_PreviewGridDual",
            display_name="Preview Weather Grid Dual",
            category="Weather",
            description=(
                "Compare two weather models side-by-side or view their difference. "
                "Requires a WEATHER_GRID with at least 2 models (use FetchOpenMeteo with multiple models selected)."
            ),
            inputs=[
                WEATHER_GRID.Input(
                    "grid_data",
                    tooltip="Multi-model gridded weather data (must contain at least 2 models).",
                ),
                io.Combo.Input(
                    "mode",
                    options=["side_by_side", "difference"],
                    default="side_by_side",
                    tooltip="side_by_side: show both grids next to each other. difference: show model1 - model2.",
                ),
                io.Combo.Input(
                    "model_1",
                    options=["auto"],
                    default="auto",
                    tooltip="First model (left / minuend). 'auto' picks the first available model.",
                ),
                io.Combo.Input(
                    "model_2",
                    options=["auto"],
                    default="auto",
                    tooltip="Second model (right / subtrahend). 'auto' picks the second available model.",
                ),
            ],
            outputs=[],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, grid_data, mode="side_by_side", model_1="auto", model_2="auto"):
        # Extract model fields
        if "fields" not in grid_data:
            raise ValueError(
                "Input WEATHER_GRID must contain fields. "
                "Select models in the FetchOpenMeteo node."
            )

        fields = grid_data["fields"]
        field_keys = list(fields.keys())

        if len(field_keys) < 2:
            raise ValueError(
                f"Need at least 2 fields for dual preview, got {len(field_keys)}: {field_keys}"
            )

        # Resolve field selections — "auto" picks first two fields
        m1 = field_keys[0] if model_1 == "auto" else model_1
        m2 = field_keys[1] if model_2 == "auto" else model_2

        if m1 not in fields:
            raise ValueError(f"Field '{m1}' not found. Available: {field_keys}")
        if m2 not in fields:
            raise ValueError(f"Field '{m2}' not found. Available: {field_keys}")

        field1 = fields[m1]
        field2 = fields[m2]

        print(f"[Weather] Dual preview: {m1} vs {m2}, mode={mode}")

        output_dir = folder_paths.get_output_directory()
        filename = f"weather_grid_dual_{int(time.time() * 1000)}.json"
        filepath = os.path.join(output_dir, filename)

        if mode == "difference":
            # Compute difference grid: model1 - model2
            # Grids may have different resolutions — interpolate model2 onto model1's grid
            diff_data = cls._compute_difference(field1, field2, m1, m2)
            payload = {
                "mode": "difference",
                "model_1": m1,
                "model_2": m2,
                "diff": diff_data,
            }
        else:
            payload = {
                "mode": "side_by_side",
                "model_1": m1,
                "model_2": m2,
                "field_1": field1,
                "field_2": field2,
            }

        payload["model_names"] = field_keys

        with open(filepath, "w") as f:
            json.dump(payload, f)

        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"[Weather] Dual grid saved: {filename} ({file_size_mb:.1f} MB)")

        return io.NodeOutput(ui={"grid_dual_file": [filename]})

    @classmethod
    def _compute_difference(cls, field1, field2, name1, name2):
        """Compute field1 - field2, interpolating field2 onto field1's grid if needed."""
        lat1 = np.array(field1["latitude"])
        lon1 = np.array(field1["longitude"])
        vals1 = np.array(field1["values"])  # [T, rows, cols] or [rows, cols]

        lat2 = np.array(field2["latitude"])
        lon2 = np.array(field2["longitude"])
        vals2 = np.array(field2["values"])

        # Ensure 3D
        if vals1.ndim == 2:
            vals1 = vals1[np.newaxis, :, :]
        if vals2.ndim == 2:
            vals2 = vals2[np.newaxis, :, :]

        # Use minimum number of time steps
        n_times = min(vals1.shape[0], vals2.shape[0])
        vals1 = vals1[:n_times]
        vals2 = vals2[:n_times]

        # Check if grids match
        grids_match = (
            lat1.shape == lat2.shape and lon1.shape == lon2.shape
            and np.allclose(lat1, lat2, atol=1e-3)
            and np.allclose(lon1, lon2, atol=1e-3)
        )

        if grids_match:
            diff = vals1 - vals2
        else:
            # Nearest-neighbor interpolation of vals2 onto grid1
            diff = np.zeros_like(vals1)
            for t in range(n_times):
                for ri in range(len(lat1)):
                    lat_i = lat1[ri]
                    r2 = np.argmin(np.abs(lat2 - lat_i))
                    for ci in range(len(lon1)):
                        lon_i = lon1[ci]
                        c2 = np.argmin(np.abs(lon2 - lon_i))
                        diff[t, ri, ci] = vals1[t, ri, ci] - vals2[t, r2, c2]

        timestamps = field1.get("timestamps", [])[:n_times]

        return {
            "variable": field1.get("variable", "difference"),
            "long_name": f"{name1} \u2212 {name2}",
            "unit": field1.get("unit", ""),
            "timestamps": timestamps,
            "latitude": lat1.tolist() if isinstance(lat1, np.ndarray) else lat1,
            "longitude": lon1.tolist() if isinstance(lon1, np.ndarray) else lon1,
            "values": diff.tolist(),
            "shape": list(diff.shape),
        }
