from typing_extensions import override
from comfy_api.latest import ComfyExtension, io

WEB_DIRECTORY = "./web"


class WeatherExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        from .nodes import NODE_CLASSES
        return NODE_CLASSES


async def comfy_entrypoint() -> WeatherExtension:
    return WeatherExtension()
