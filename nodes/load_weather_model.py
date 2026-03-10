"""Load Weather Model node — downloads and loads ML weather prediction models."""

import importlib
import torch
import comfy.model_management as mm
from comfy_api.latest import io

from ._weather_ml_registry import WEATHER_ML_MODELS, get_model_list

WEATHER_MODEL = io.Custom("WEATHER_MODEL")


class LoadWeatherModel(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_LoadModel",
            display_name="(Down)Load Weather Model",
            category="Weather",
            description=(
                "Load an ML weather prediction model. Auto-downloads weights on first use. "
                "Supports Aurora, Pangu-Weather, FuXi, and more via Earth2Studio."
            ),
            inputs=[
                io.Combo.Input(
                    "model_name",
                    options=get_model_list(),
                    default=get_model_list()[0],
                    tooltip="Select a weather ML model. Weights are auto-downloaded on first use.",
                ),
                io.Combo.Input(
                    "device",
                    options=["auto", "cuda", "cpu"],
                    default="auto",
                    tooltip="Device to load model on. 'auto' uses GPU if available.",
                ),
            ],
            outputs=[
                WEATHER_MODEL.Output(display_name="WEATHER_MODEL"),
                io.String.Output(display_name="Info"),
            ],
        )

    @classmethod
    def execute(cls, model_name, device="auto"):
        meta = WEATHER_ML_MODELS[model_name]

        # Resolve device
        if device == "auto":
            dev = mm.get_torch_device()
        elif device == "cuda":
            dev = torch.device("cuda")
        else:
            dev = torch.device("cpu")

        print(f"[Weather ML] Loading {model_name} on {dev}...")

        # Import the model class from earth2studio
        try:
            module = importlib.import_module(meta["e2s_module"])
            model_cls = getattr(module, meta["e2s_class"])
            model = model_cls.from_pretrained()
        except Exception as e:
            extra = meta.get("extra", "")
            err = str(e)
            if "OptionalDependency" in type(e).__name__:
                raise RuntimeError(
                    f"{model_name} requires extra dependencies.\n"
                    f"Install with: pip install 'earth2studio[{extra}]'"
                ) from e
            if "not found" in err or "HTTPException" in type(e).__name__:
                raise RuntimeError(
                    f"{model_name}: failed to download model weights.\n{err}"
                ) from e
            raise

        model = model.to(dev)

        # Get model's variable list
        input_coords = model.input_coords()
        variables = list(input_coords.get("variable", []))

        info_lines = [
            f"Model: {model_name}",
            f"Class: {meta['e2s_class']}",
            f"Resolution: {meta['resolution']}",
            f"Step: {meta['step_hours']}h",
            f"License: {meta['license']}",
            f"Device: {dev}",
            f"Variables: {len(variables)}",
            f"Est. VRAM: ~{meta['vram_gb']} GB",
        ]
        info = "\n".join(info_lines)
        print(f"[Weather ML] {model_name} loaded: {len(variables)} vars, {meta['resolution']}")

        weather_model = {
            "model": model,
            "model_name": model_name,
            "metadata": meta,
            "device": dev,
            "variables": variables,
        }

        return io.NodeOutput(weather_model, info)
