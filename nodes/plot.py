import io as stdlib_io
import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image as PILImage
from comfy_api.latest import io
from .fetch_openmeteo import WEATHER_DATA


def _get_first_location(weather_data):
    locations = weather_data.get("locations", [])
    if locations:
        return locations[0]
    return weather_data

# Distinct colors for model comparison
MODEL_COLORS = [
    "#2196F3",  # blue
    "#FF5722",  # deep orange
    "#4CAF50",  # green
    "#9C27B0",  # purple
    "#FF9800",  # orange
    "#00BCD4",  # cyan
    "#E91E63",  # pink
    "#607D8B",  # blue-grey
]


class WeatherPlot(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Weather_Plot",
            display_name="Weather Plot",
            category="Weather",
            description=(
                "Render weather data as line charts. "
                "When WEATHER_DATA contains multiple models, plots them stacked vertically for comparison."
            ),
            inputs=[
                WEATHER_DATA.Input(
                    "weather_data",
                    tooltip="Weather data from a fetch node.",
                ),
                io.String.Input(
                    "variable",
                    default="",
                    optional=True,
                    tooltip="Variable to plot (e.g. 'temperature_2m'). Leave empty for first available.",
                ),
                io.Int.Input(
                    "width",
                    default=1024,
                    min=256,
                    max=4096,
                    step=64,
                ),
                io.Int.Input(
                    "height",
                    default=512,
                    min=256,
                    max=4096,
                    step=64,
                    tooltip="Height per subplot when comparing multiple models.",
                ),
                io.String.Input(
                    "title",
                    default="",
                    optional=True,
                    tooltip="Chart title. Auto-generated if empty.",
                ),
            ],
            outputs=[
                io.Image.Output(display_name="IMAGE"),
            ],
        )

    @classmethod
    def execute(cls, weather_data, width, height, variable="", title=""):
        loc_data = _get_first_location(weather_data)
        models_dict = loc_data.get("models")

        if models_dict and len(models_dict) > 1:
            return cls._plot_multi_model(loc_data, models_dict, width, height, variable, title)
        else:
            return cls._plot_single(loc_data, width, height, variable, title)

    @classmethod
    def _resolve_variable(cls, variables, variable):
        """Pick the variable to plot, returning (var_name, values)."""
        if not variables:
            raise ValueError("WEATHER_DATA contains no variables.")
        if variable and variable in variables:
            return variable
        elif variable and variable not in variables:
            available = ", ".join(variables.keys())
            raise ValueError(f"Variable '{variable}' not found. Available: {available}")
        return next(iter(variables))

    @classmethod
    def _add_xtick_labels(cls, ax, timestamps, n):
        if n <= 0:
            return
        step = max(1, n // 10)
        tick_positions = list(range(0, n, step))
        tick_labels = [
            timestamps[i][5:16] if i < len(timestamps) else ""
            for i in tick_positions
        ]
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, rotation=45, ha="right", fontsize=8)

    @classmethod
    def _plot_single(cls, weather_data, width, height, variable, title):
        """Single-model plot (original behavior)."""
        variables = weather_data.get("variables", {})
        timestamps = weather_data.get("timestamps", [])
        units = weather_data.get("units", {})

        var_name = cls._resolve_variable(variables, variable)
        values = variables[var_name]
        unit = units.get(var_name, "")
        n = len(values)
        x = list(range(n))

        if not title:
            loc = weather_data.get("location_name", "")
            source = weather_data.get("source", "")
            # If single model in models dict, show model name
            models_dict = weather_data.get("models")
            if models_dict and len(models_dict) == 1:
                model_name = next(iter(models_dict.keys()))
                source = f"open-meteo ({model_name})"
            title = var_name
            if loc:
                title += f" - {loc}"
            if source:
                title += f" ({source})"

        dpi = 100
        fig, ax = plt.subplots(figsize=(width / dpi, height / dpi), dpi=dpi)

        ax.plot(x, values, linewidth=1.5, color=MODEL_COLORS[0])
        ax.fill_between(x, values, alpha=0.15, color=MODEL_COLORS[0])
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.set_ylabel(f"{var_name} ({unit})" if unit else var_name, fontsize=11)
        ax.set_xlabel("Time", fontsize=11)
        ax.grid(True, alpha=0.3)
        cls._add_xtick_labels(ax, timestamps, n)

        fig.tight_layout()
        tensor = cls._fig_to_tensor(fig, dpi)
        print(f"[Weather] Plot rendered: {var_name}, {n} points -> {tensor.shape}")
        return io.NodeOutput(tensor)

    @classmethod
    def _plot_multi_model(cls, weather_data, models_dict, width, height, variable, title):
        """Multi-model stacked subplots."""
        model_keys = list(models_dict.keys())
        n_models = len(model_keys)

        # Resolve variable name from first model
        first_model = models_dict[model_keys[0]]
        var_name = cls._resolve_variable(first_model["variables"], variable)

        lat = weather_data.get("latitude", "?")
        lon = weather_data.get("longitude", "?")
        loc = weather_data.get("location_name", "")
        suptitle = title or f"{var_name} — model comparison"
        if loc:
            suptitle += f" ({loc})"
        elif lat != "?":
            suptitle += f" ({lat:.2f}°, {lon:.2f}°)"

        dpi = 100
        fig_h = (height / dpi) * n_models + 0.8  # extra for suptitle
        fig, axes = plt.subplots(
            n_models, 1,
            figsize=(width / dpi, fig_h),
            dpi=dpi,
            sharex=False,
            squeeze=False,
        )

        fig.suptitle(suptitle, fontsize=14, fontweight="bold", y=1.0 - 0.3 / fig_h)

        for idx, model_key in enumerate(model_keys):
            ax = axes[idx, 0]
            model_data = models_dict[model_key]
            variables = model_data.get("variables", {})
            timestamps = model_data.get("timestamps", [])
            units = model_data.get("units", {})

            if var_name not in variables:
                ax.text(0.5, 0.5, f"{var_name} not available",
                        transform=ax.transAxes, ha="center", va="center",
                        fontsize=12, color="#999")
                ax.set_title(model_key, fontsize=11, fontweight="bold", loc="left")
                continue

            values = variables[var_name]
            unit = units.get(var_name, "")
            n = len(values)
            x = list(range(n))
            color = MODEL_COLORS[idx % len(MODEL_COLORS)]

            ax.plot(x, values, linewidth=1.5, color=color)
            ax.fill_between(x, values, alpha=0.12, color=color)
            ax.set_title(model_key, fontsize=11, fontweight="bold", loc="left", color=color)
            ax.set_ylabel(f"{unit}" if unit else var_name, fontsize=10)
            ax.grid(True, alpha=0.3)

            # Only show x-axis labels on the bottom subplot
            if idx == n_models - 1:
                cls._add_xtick_labels(ax, timestamps, n)
                ax.set_xlabel("Time", fontsize=11)
            else:
                ax.set_xticklabels([])

        fig.tight_layout()
        tensor = cls._fig_to_tensor(fig, dpi)
        print(f"[Weather] Multi-model plot: {var_name}, {n_models} models -> {tensor.shape}")
        return io.NodeOutput(tensor)

    @classmethod
    def _fig_to_tensor(cls, fig, dpi):
        """Render matplotlib figure to ComfyUI IMAGE tensor [1, H, W, 3]."""
        buf = stdlib_io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        pil_img = PILImage.open(buf).convert("RGB")
        np_img = np.array(pil_img).astype(np.float32) / 255.0
        return torch.from_numpy(np_img).unsqueeze(0)
