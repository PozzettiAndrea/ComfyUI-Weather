from comfy_api.latest import io
from .fetch_openmeteo import WEATHER_DATA


def _get_first_location(weather_data):
    """Extract first location from WEATHER_DATA (handles both old and new format)."""
    locations = weather_data.get("locations", [])
    if locations:
        return locations[0]
    return weather_data


class WeatherToText(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_ToText",
            display_name="Weather to Text",
            category="Weather",
            description="Convert weather data to a human-readable text summary, detailed listing, or CSV.",
            inputs=[
                WEATHER_DATA.Input("weather_data"),
                io.Combo.Input(
                    "format",
                    options=["summary", "detailed", "csv"],
                    default="summary",
                    tooltip="Output format: summary (stats), detailed (all data points), or csv.",
                ),
            ],
            outputs=[
                io.String.Output(display_name="TEXT"),
            ],
        )

    @classmethod
    def execute(cls, weather_data, format="summary"):
        print(f"[Weather] Converting weather data to text (format={format})")
        loc_data = _get_first_location(weather_data)
        variables = loc_data.get("variables", {})
        timestamps = loc_data.get("timestamps", [])
        units = loc_data.get("units", {})
        source = loc_data.get("source", "unknown")
        lat = loc_data.get("latitude", "?")
        lon = loc_data.get("longitude", "?")
        location = loc_data.get("location_name", "")

        if format == "summary":
            lines = []
            header = "Weather Forecast"
            if location:
                header += f" for {location}"
            header += f" ({lat}, {lon})"
            lines.append(header)
            lines.append(f"Source: {source}")
            if timestamps:
                lines.append(f"Period: {timestamps[0]} to {timestamps[-1]}")
                lines.append(f"Data points: {len(timestamps)}")
            lines.append("")

            for var_name, values in variables.items():
                unit = units.get(var_name, "")
                numeric = [v for v in values if v is not None]
                if not numeric:
                    continue
                unit_str = f" {unit}" if unit else ""
                lines.append(f"{var_name}:")
                lines.append(f"  Min: {min(numeric):.1f}{unit_str}")
                lines.append(f"  Max: {max(numeric):.1f}{unit_str}")
                lines.append(f"  Avg: {sum(numeric) / len(numeric):.1f}{unit_str}")
                lines.append("")

            text = "\n".join(lines)

        elif format == "detailed":
            lines = [f"Weather Data ({source}) - {location or f'{lat},{lon}'}"]
            lines.append("=" * 60)
            for i, ts in enumerate(timestamps):
                parts = [ts]
                for var_name, values in variables.items():
                    unit = units.get(var_name, "")
                    val = values[i] if i < len(values) else "N/A"
                    if isinstance(val, float):
                        parts.append(f"{var_name}={val:.1f}{unit}")
                    else:
                        parts.append(f"{var_name}={val}{unit}")
                lines.append(" | ".join(parts))
            text = "\n".join(lines)

        elif format == "csv":
            var_names = list(variables.keys())
            header = "timestamp," + ",".join(
                f"{v} ({units.get(v, '')})" for v in var_names
            )
            lines = [header]
            for i, ts in enumerate(timestamps):
                row = [ts]
                for var_name in var_names:
                    vals = variables[var_name]
                    val = vals[i] if i < len(vals) else ""
                    row.append(str(val) if val is not None else "")
                lines.append(",".join(row))
            text = "\n".join(lines)

        else:
            text = str(weather_data)

        return io.NodeOutput(text)
