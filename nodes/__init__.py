from .geocode import GeocodeCityName
from .fetch_openmeteo import FetchWeatherForecast
from .fetch_jua import FetchJuaForecast
from .plot import WeatherPlot
from .to_text import WeatherToText
from .extract import ExtractWeatherVariable
from .load_grib2 import LoadGRIB2
from .heatmap import WeatherHeatmap
from .preview_grid import PreviewWeatherGrid
from .latlon_collector import LatLonCollector
from .grid_collector import GridCollector
from .set_api_key import SetOpenMeteoAPIKey
from .preview_data import PreviewWeatherData
from .preview_grid_dual import PreviewWeatherGridDual

NODE_CLASSES = [
    GeocodeCityName,
    FetchWeatherForecast,
    FetchJuaForecast,
    WeatherPlot,
    WeatherToText,
    ExtractWeatherVariable,
    LoadGRIB2,
    WeatherHeatmap,
    PreviewWeatherGrid,
    PreviewWeatherGridDual,
    PreviewWeatherData,
    LatLonCollector,
    GridCollector,
    SetOpenMeteoAPIKey,
]
