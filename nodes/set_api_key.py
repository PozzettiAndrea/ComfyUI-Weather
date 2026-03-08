import os

from comfy_api.latest import io

from . import fetch_openmeteo


class SetOpenMeteoAPIKey(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_SetOpenMeteoAPIKey",
            display_name="Set Open-Meteo API Key",
            category="Weather",
            description=(
                "Set your Open-Meteo API key for higher rate limits. "
                "Get a key at https://open-meteo.com/en/pricing. "
                "Just add this node to your workflow — no connections needed."
            ),
            inputs=[
                io.String.Input(
                    "api_key",
                    default="",
                    tooltip="Your Open-Meteo API key. Leave empty for free tier.",
                ),
            ],
            outputs=[
                io.String.Output(display_name="Info"),
            ],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, api_key):
        key = api_key.strip()
        if key:
            fetch_openmeteo._api_key = key
            os.environ["OPEN_METEO_API_KEY"] = key
            info = f"API key set ({key[:4]}...{key[-4:]}). Using customer API endpoint."
            print(f"[Weather] Open-Meteo API key configured")
        else:
            fetch_openmeteo._api_key = None
            os.environ.pop("OPEN_METEO_API_KEY", None)
            info = "No API key set. Using free tier."
            print(f"[Weather] Open-Meteo API key cleared (free tier)")

        return io.NodeOutput(info)
