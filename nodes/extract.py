import json
from comfy_api.latest import io
from .fetch_openmeteo import WEATHER_DATA


def _get_first_location(weather_data):
    locations = weather_data.get("locations", [])
    if locations:
        return locations[0]
    return weather_data


class ExtractWeatherVariable(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_ExtractVariable",
            display_name="Extract Weather Variable",
            category="Weather",
            description="Extract a single variable's time series from weather data as JSON.",
            inputs=[
                WEATHER_DATA.Input("weather_data"),
                io.String.Input(
                    "variable_name",
                    default="temperature_2m",
                    tooltip="Variable to extract (e.g. 'temperature_2m').",
                ),
            ],
            outputs=[
                io.String.Output(display_name="Data (JSON)"),
                io.String.Output(display_name="Variable Info"),
            ],
        )

    @classmethod
    def execute(cls, weather_data, variable_name):
        print(f"[Weather] Extracting variable: '{variable_name}'")
        loc_data = _get_first_location(weather_data)
        variables = loc_data.get("variables", {})
        timestamps = loc_data.get("timestamps", [])
        units = loc_data.get("units", {})

        if variable_name not in variables:
            available = ", ".join(variables.keys())
            raise ValueError(f"Variable '{variable_name}' not found. Available: {available}")

        values = variables[variable_name]
        unit = units.get(variable_name, "")

        data_points = []
        for i, ts in enumerate(timestamps):
            val = values[i] if i < len(values) else None
            data_points.append({"timestamp": ts, "value": val})

        data_json = json.dumps(data_points, indent=2)

        numeric = [v for v in values if v is not None and isinstance(v, (int, float))]
        info_parts = [
            f"Variable: {variable_name}",
            f"Unit: {unit}" if unit else "Unit: unknown",
            f"Data points: {len(values)}",
        ]
        if numeric:
            info_parts.extend([
                f"Min: {min(numeric):.2f}",
                f"Max: {max(numeric):.2f}",
                f"Mean: {sum(numeric) / len(numeric):.2f}",
            ])
        variable_info = "\n".join(info_parts)

        return io.NodeOutput(data_json, variable_info)
