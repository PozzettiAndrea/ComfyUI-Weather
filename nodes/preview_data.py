import os
import json
import time
import folder_paths
from comfy_api.latest import io
from .fetch_openmeteo import WEATHER_DATA


class PreviewWeatherData(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_PreviewData",
            display_name="Preview Weather Data",
            category="Weather",
            description=(
                "Interactive time-series preview of weather data. "
                "Multiple locations are shown as stacked plots. "
                "Supports multi-variable and multi-model overlay."
            ),
            inputs=[
                WEATHER_DATA.Input("data", tooltip="Weather data from Fetch Weather Forecast."),
            ],
            outputs=[],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, data):
        # WEATHER_DATA now has {"locations": [...]} structure
        locations = data.get("locations", [])
        if not locations:
            raise ValueError("No location data found.")

        # Tag each location with a label
        for i, d in enumerate(locations, 1):
            lat = d.get("latitude", "?")
            lon = d.get("longitude", "?")
            loc = d.get("location_name")
            if loc:
                d["_label"] = loc
            elif lat != "?" and lon != "?":
                d["_label"] = f"({lat:.2f}°, {lon:.2f}°)"
            else:
                d["_label"] = f"Location {i}"

        print(f"[Weather] Saving {len(locations)} location(s) for preview widget")

        output_dir = folder_paths.get_output_directory()
        filename = f"weather_data_{int(time.time() * 1000)}.json"
        filepath = os.path.join(output_dir, filename)

        payload = {"locations": locations}
        with open(filepath, "w") as f:
            json.dump(payload, f)

        file_size_kb = os.path.getsize(filepath) / 1024
        print(f"[Weather] Data saved: {filename} ({file_size_kb:.0f} KB, {len(locations)} location(s))")

        return io.NodeOutput(ui={"data_file": [filename]})
