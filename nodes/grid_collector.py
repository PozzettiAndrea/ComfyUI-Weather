import json
from comfy_api.latest import io
from .fetch_openmeteo import GRID_COORDS


class GridCollector(io.ComfyNode):
    """Interactive map widget for drawing a bounding box (grid region)."""

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_GridCollector",
            display_name="Grid Collector",
            category="Weather",
            description=(
                "Draw a bounding box on a world map to define a grid region. "
                "Outputs a GRID_COORDS dict with lat_south, lon_west, lat_north, lon_east."
            ),
            inputs=[
                io.String.Input(
                    "bbox_store",
                    multiline=False,
                    default="{}",
                ),
            ],
            outputs=[
                GRID_COORDS.Output(display_name="GRID_COORDS"),
                io.String.Output(display_name="Info"),
            ],
        )

    @classmethod
    def execute(cls, bbox_store):
        bbox = {}
        if bbox_store and bbox_store.strip():
            try:
                bbox = json.loads(bbox_store)
            except json.JSONDecodeError:
                pass

        if not bbox or "lat_south" not in bbox:
            raise ValueError("No bounding box drawn. Click and drag on the map to select a region.")

        grid_coords = {
            "lat_south": float(bbox["lat_south"]),
            "lon_west": float(bbox["lon_west"]),
            "lat_north": float(bbox["lat_north"]),
            "lon_east": float(bbox["lon_east"]),
        }

        lat_range = abs(grid_coords["lat_north"] - grid_coords["lat_south"])
        lon_range = abs(grid_coords["lon_east"] - grid_coords["lon_west"])

        info = (
            f"Bounding Box:\n"
            f"  N: {grid_coords['lat_north']:.4f}°  S: {grid_coords['lat_south']:.4f}°\n"
            f"  W: {grid_coords['lon_west']:.4f}°  E: {grid_coords['lon_east']:.4f}°\n"
            f"  Size: {lat_range:.2f}° x {lon_range:.2f}°"
        )
        print(f"[Weather] Grid Collector: ({grid_coords['lat_south']:.4f}, {grid_coords['lon_west']:.4f}) "
              f"to ({grid_coords['lat_north']:.4f}, {grid_coords['lon_east']:.4f})")

        return io.NodeOutput(grid_coords, info)
