import io as stdlib_io
import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from PIL import Image as PILImage
from comfy_api.latest import io

WEATHER_GRID = io.Custom("WEATHER_GRID")

COLORMAPS = [
    "RdBu_r",       # temperature (red=hot, blue=cold)
    "viridis",       # general purpose
    "plasma",        # general purpose (brighter)
    "coolwarm",      # diverging
    "YlOrRd",        # precipitation / intensity
    "Blues",          # precipitation / water
    "RdYlGn_r",      # risk (red=bad, green=good)
    "twilight_shifted", # wind direction (cyclic)
    "gray",          # neutral
]


class WeatherHeatmap(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_Heatmap",
            display_name="Weather Heatmap",
            category="Weather",
            description="Render gridded weather data as a heatmap image. Works with GRIB2/NetCDF grid data.",
            inputs=[
                WEATHER_GRID.Input(
                    "grid_data",
                    tooltip="Gridded weather data from Load GRIB2 or similar.",
                ),
                io.Combo.Input(
                    "colormap",
                    options=COLORMAPS,
                    default="RdBu_r",
                    tooltip="Color scheme for the heatmap.",
                ),
                io.Int.Input(
                    "width",
                    default=1920,
                    min=256,
                    max=8192,
                    step=64,
                ),
                io.Int.Input(
                    "height",
                    default=1080,
                    min=256,
                    max=8192,
                    step=64,
                ),
                io.Boolean.Input(
                    "show_colorbar",
                    default=True,
                    tooltip="Show a colorbar with value scale.",
                ),
                io.Boolean.Input(
                    "show_gridlines",
                    default=True,
                    tooltip="Show latitude/longitude grid lines.",
                ),
                io.String.Input(
                    "title",
                    default="",
                    optional=True,
                    tooltip="Title. Auto-generated if empty.",
                ),
            ],
            outputs=[
                io.Image.Output(display_name="IMAGE"),
            ],
        )

    @classmethod
    def execute(cls, grid_data, colormap, width, height, show_colorbar, show_gridlines, title=""):
        print(f"[Weather] Rendering heatmap ({width}x{height}, cmap={colormap})")

        values = np.array(grid_data["values"], dtype=np.float64)
        lats = np.array(grid_data["latitude"])
        lons = np.array(grid_data["longitude"])
        var_name = grid_data.get("variable", "")
        long_name = grid_data.get("long_name", var_name)
        unit = grid_data.get("unit", "")
        timestamp = grid_data.get("timestamp", "")

        if not title:
            title = f"{long_name}"
            if timestamp:
                title += f" - {timestamp}"

        dpi = 100
        fig, ax = plt.subplots(figsize=(width / dpi, height / dpi), dpi=dpi)

        # Determine extent [left, right, bottom, top]
        lon_min, lon_max = float(lons.min()), float(lons.max())
        lat_min, lat_max = float(lats.min()), float(lats.max())

        # Check if lats are descending (common in GRIB2: 90 to -90)
        if len(lats) > 1 and lats[0] > lats[-1]:
            extent = [lon_min, lon_max, lat_min, lat_max]
            origin = "upper"
        else:
            extent = [lon_min, lon_max, lat_min, lat_max]
            origin = "lower"

        im = ax.imshow(
            values,
            extent=extent,
            origin=origin,
            cmap=colormap,
            aspect="auto",
            interpolation="bilinear",
        )

        ax.set_title(title, fontsize=14, fontweight="bold", pad=10)
        ax.set_xlabel("Longitude (°)", fontsize=11)
        ax.set_ylabel("Latitude (°)", fontsize=11)

        if show_colorbar:
            label = f"{var_name} ({unit})" if unit else var_name
            cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
            cbar.set_label(label, fontsize=11)

        if show_gridlines:
            ax.grid(True, alpha=0.3, linestyle="--", color="white")

        fig.tight_layout()

        # Render to IMAGE tensor
        buf = stdlib_io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        pil_img = PILImage.open(buf).convert("RGB")
        np_img = np.array(pil_img).astype(np.float32) / 255.0
        tensor = torch.from_numpy(np_img).unsqueeze(0)

        print(f"[Weather] Heatmap rendered: {values.shape} grid -> {tensor.shape}")
        return io.NodeOutput(tensor)
