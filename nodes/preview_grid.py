import os
import json
import time
import folder_paths
from comfy_api.latest import io

WEATHER_GRID = io.Custom("WEATHER_GRID")


class PreviewWeatherGrid(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_PreviewGrid",
            display_name="Preview Weather Grid",
            category="Weather",
            description="Interactive preview of gridded weather data in the browser. Supports hover, zoom/pan, and coastline overlay.",
            inputs=[
                WEATHER_GRID.Input(
                    "grid_data",
                    tooltip="Gridded weather data from Load GRIB2 or similar.",
                ),
            ],
            outputs=[],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, grid_data):
        print("[Weather] Saving grid data for preview widget")

        output_dir = folder_paths.get_output_directory()
        filename = f"weather_grid_{int(time.time() * 1000)}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w") as f:
            json.dump(grid_data, f)

        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"[Weather] Grid saved: {filename} ({file_size_mb:.1f} MB)")

        return io.NodeOutput(ui={"grid_file": [filename]})
