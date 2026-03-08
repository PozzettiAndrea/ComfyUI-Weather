import os
import glob
import xarray as xr
import numpy as np
import folder_paths
from comfy_api.latest import io

WEATHER_GRID = io.Custom("WEATHER_GRID")


def _list_grib2_files():
    """List all .grib2 files in ComfyUI's input directory."""
    input_dir = folder_paths.get_input_directory()
    files = []
    for ext in ("*.grib2", "*.grib", "*.grb2", "*.grb"):
        files.extend(glob.glob(os.path.join(input_dir, ext)))
        files.extend(glob.glob(os.path.join(input_dir, "**", ext), recursive=True))
    # Return relative paths from input dir
    result = sorted(set(os.path.relpath(f, input_dir) for f in files))
    return result if result else [""]


class LoadGRIB2(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_LoadGRIB2",
            display_name="Load GRIB2",
            category="Weather",
            description="Load a GRIB2 file and extract a variable as a gridded field. Supports GFS, ECMWF, ICON, and any standard GRIB2 file. Searches ComfyUI's input/ folder.",
            inputs=[
                io.Combo.Input(
                    "file_name",
                    options=_list_grib2_files(),
                    tooltip="GRIB2 file from ComfyUI's input/ folder.",
                ),
                io.String.Input(
                    "variable",
                    default="",
                    optional=True,
                    tooltip="Variable short name (e.g. 't2m', 'u10'). Leave empty to load the first available variable.",
                ),
                io.Int.Input(
                    "timestep",
                    default=0,
                    min=0,
                    max=100,
                    step=1,
                    tooltip="Timestep index to extract (0 = first/only timestep).",
                ),
            ],
            outputs=[
                WEATHER_GRID.Output(display_name="WEATHER_GRID"),
                io.String.Output(display_name="Grid Info"),
            ],
        )

    @classmethod
    def execute(cls, file_name, timestep=0, variable=""):
        input_dir = folder_paths.get_input_directory()
        file_path = os.path.join(input_dir, file_name)

        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"GRIB2 file not found: '{file_path}' (looked in {input_dir})")

        print(f"[Weather] Loading GRIB2: {file_path}")

        # Open with cfgrib - filter by variable if specified
        backend_kwargs = {}
        if variable:
            backend_kwargs["filter_by_keys"] = {"shortName": variable}

        try:
            ds = xr.open_dataset(file_path, engine="cfgrib", backend_kwargs=backend_kwargs)
        except Exception as e:
            # If filtering fails, try without filter and list available variables
            try:
                ds_all = xr.open_dataset(file_path, engine="cfgrib")
                available = list(ds_all.data_vars)
                ds_all.close()
                raise RuntimeError(
                    f"Could not load variable '{variable}'. Available: {available}"
                ) from e
            except Exception:
                raise RuntimeError(f"Failed to open GRIB2 file: {e}") from e

        # Pick the first data variable if none specified
        data_vars = list(ds.data_vars)
        if not data_vars:
            raise RuntimeError("GRIB2 file contains no data variables.")

        var_name = data_vars[0]
        da = ds[var_name]

        # Handle time dimension
        if "valid_time" in da.dims and da.sizes["valid_time"] > 1:
            if timestep >= da.sizes["valid_time"]:
                raise ValueError(
                    f"Timestep {timestep} out of range (file has {da.sizes['valid_time']} timesteps)"
                )
            da = da.isel(valid_time=timestep)
            ts = str(da.coords["valid_time"].values)[:16]
        elif "time" in da.dims and da.sizes.get("time", 1) > 1:
            if timestep >= da.sizes["time"]:
                raise ValueError(
                    f"Timestep {timestep} out of range (file has {da.sizes['time']} timesteps)"
                )
            da = da.isel(time=timestep)
            ts = str(da.coords["time"].values)[:16]
        else:
            # Single timestep
            if "valid_time" in da.coords:
                ts = str(da.coords["valid_time"].values)[:16]
            elif "time" in da.coords:
                ts = str(da.coords["time"].values)[:16]
            else:
                ts = "unknown"

        lats = da.coords["latitude"].values.astype(np.float64)
        lons = da.coords["longitude"].values.astype(np.float64)
        values = da.values.astype(np.float64)

        # Handle NaN
        values = np.nan_to_num(values, nan=0.0)

        unit = da.attrs.get("units", "")
        long_name = da.attrs.get("long_name", var_name)

        grid_data = {
            "variable": var_name,
            "long_name": long_name,
            "unit": unit,
            "timestamp": ts,
            "latitude": lats.tolist(),
            "longitude": lons.tolist(),
            "values": values.tolist(),
            "shape": list(values.shape),
        }

        lat_step = abs(lats[1] - lats[0]) if len(lats) > 1 else 0
        lon_step = abs(lons[1] - lons[0]) if len(lons) > 1 else 0

        info_lines = [
            f"Variable: {var_name} ({long_name})",
            f"Unit: {unit}",
            f"Timestamp: {ts}",
            f"Grid: {len(lats)} x {len(lons)} ({lat_step:.4f}° x {lon_step:.4f}°)",
            f"Lat: {lats.min():.2f}° to {lats.max():.2f}°",
            f"Lon: {lons.min():.2f}° to {lons.max():.2f}°",
            f"Value range: {values.min():.2f} to {values.max():.2f} {unit}",
        ]
        grid_info = "\n".join(info_lines)

        print(f"[Weather] Loaded {var_name}: {values.shape} grid, {unit}, range [{values.min():.1f}, {values.max():.1f}]")

        ds.close()
        return io.NodeOutput(grid_data, grid_info)
