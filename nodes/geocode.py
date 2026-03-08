import requests
from comfy_api.latest import io


class GeocodeCityName(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_GeocodeCityName",
            display_name="Geocode City Name",
            category="Weather",
            description="Convert a city name to latitude and longitude using the Open-Meteo geocoding API.",
            inputs=[
                io.String.Input(
                    "city_name",
                    default="Berlin",
                    tooltip="Name of the city to geocode (e.g. 'Berlin', 'New York', 'Tokyo').",
                ),
            ],
            outputs=[
                io.Float.Output(display_name="Latitude"),
                io.Float.Output(display_name="Longitude"),
                io.String.Output(display_name="Display Name"),
            ],
            not_idempotent=True,
        )

    @classmethod
    def execute(cls, city_name):
        print(f"[Weather] Geocoding city: '{city_name}'")
        if not city_name or not city_name.strip():
            raise ValueError("City name cannot be empty.")

        resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city_name.strip(), "count": 1, "language": "en"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results")
        if not results:
            raise ValueError(f"No results found for city: '{city_name}'")

        result = results[0]
        lat = float(result["latitude"])
        lon = float(result["longitude"])
        name = result.get("name", city_name)
        country = result.get("country", "")
        admin1 = result.get("admin1", "")
        display = f"{name}, {admin1}, {country}" if admin1 else f"{name}, {country}"
        print(f"[Weather] Geocoded '{city_name}' -> {display} ({lat}, {lon})")

        return io.NodeOutput(lat, lon, display)
