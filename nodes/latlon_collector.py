import json
from comfy_api.latest import io
from .fetch_openmeteo import LATLON_COORDS


class LatLonCollector(io.ComfyNode):
    """Interactive map widget for collecting lat/lon coordinates by clicking."""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_LatLonCollector",
            display_name="LatLon Collector",
            category="Weather",
            description=(
                "Click on a world map to select a lat/lon coordinate. "
                "Outputs LATLON_COORDS dict for the Fetch Weather Forecast node."
            ),
            inputs=[
                io.String.Input(
                    "points_store",
                    multiline=False,
                    default="[]",
                ),
            ],
            outputs=[
                LATLON_COORDS.Output(display_name="LATLON_COORDS"),
                io.String.Output(display_name="Info"),
            ],
        )

    @classmethod
    def execute(cls, points_store):
        points = []
        if points_store and points_store.strip():
            try:
                points = json.loads(points_store)
            except json.JSONDecodeError:
                pass

        if not points:
            raise ValueError("No point selected. Click on the map to place a marker.")

        latlon_coords = {
            "points": [{"latitude": float(p["lat"]), "longitude": float(p["lon"])} for p in points],
        }

        lines = [f"{len(points)} location(s):"]
        for i, p in enumerate(points):
            lines.append(f"  [{i+1}] ({p['lat']:.4f}, {p['lon']:.4f})")

        info = "\n".join(lines)
        print(f"[Weather] LatLon Collector: {len(points)} point(s)")

        return io.NodeOutput(latlon_coords, info)
