# ComfyUI-Weather

Weather data nodes for ComfyUI. Fetch forecasts from [Open-Meteo](https://open-meteo.com/) and [Jua.ai](https://jua.ai/), visualize and process weather data.


https://github.com/user-attachments/assets/e497ffcb-65c8-4f72-8ed4-9f59f9fc720e


## Nodes

| Node | Description |
|------|-------------|
| **Fetch Weather Forecast (Open-Meteo)** | Fetch weather data from Open-Meteo. Supports single-point time-series (`latlon`) or 2D spatial grid (`grid`) backends. Multi-model comparison. |
| **Fetch Jua Forecast** | Fetch weather data from the Jua.ai EPT2 model API. |
| **LatLon Collector** | Interactive map widget — click to place a lat/lon marker. Outputs `LATLON_COORDS`. |
| **Grid Collector** | Interactive map widget — click and drag to draw a bounding box. Outputs `GRID_COORDS`. |
| **Geocode City Name** | Convert a city name to latitude/longitude using Open-Meteo geocoding. |
| **Weather Plot** | Plot weather time-series as line charts. Supports multi-model comparison (stacked subplots). |
| **Weather Heatmap** | Render a `WEATHER_GRID` as a heatmap image with colorbar. |
| **Preview Weather Grid** | Interactive grid viewer with coastlines, pan/zoom, hover tooltip. |
| **Weather To Text** | Convert `WEATHER_DATA` to a formatted text summary. |
| **Extract Weather Variable** | Extract a single variable from `WEATHER_DATA` as a list of values. |
| **Load GRIB2** | Load weather data from GRIB2 files. |

## Available Open-Meteo Models

The Fetch Weather Forecast node supports multiple NWP (Numerical Weather Prediction) models via the model selector popup. You can select one or more models and compare their forecasts side-by-side.

### Global Models

| Model Key | Name | Resolution | Provider | Coverage |
|-----------|------|------------|----------|----------|
| `best_match` | Best Match | varies | Open-Meteo | Global (auto-selects best available) |
| `ecmwf_ifs025` | ECMWF IFS 0.25° | 0.25° (~25 km) | ECMWF (Europe) | Global |
| `ecmwf_aifs025` | ECMWF AIFS 0.25° | 0.25° (~25 km) | ECMWF (AI model) | Global |
| `gfs_seamless` | GFS Seamless | 0.25° (~25 km) | NCEP/NOAA (USA) | Global |
| `gfs_global` | GFS Global | 0.25° (~25 km) | NCEP/NOAA (USA) | Global |
| `gfs025` | GFS 0.25° | 0.25° (~25 km) | NCEP/NOAA (USA) | Global |
| `gfs013` | GFS 0.13° | 0.13° (~13 km) | NCEP/NOAA (USA) | Global |
| `gfs_graphcast025` | GFS GraphCast | 0.25° (~25 km) | NOAA (AI model) | Global |
| `icon_seamless` | ICON Seamless | 0.125° (~13 km) | DWD (Germany) | Global |
| `icon_global` | ICON Global | 0.125° (~13 km) | DWD (Germany) | Global |
| `gem_seamless` | GEM Seamless | 0.25° (~25 km) | CMC (Canada) | Global |
| `gem_global` | GEM Global | 0.25° (~25 km) | CMC (Canada) | Global |
| `jma_seamless` | JMA Seamless | 0.05° (~5 km) | JMA (Japan) | Global |
| `jma_gsm` | JMA GSM | 0.5° (~55 km) | JMA (Japan) | Global |
| `meteofrance_seamless` | Meteo-France Seamless | 0.1° (~10 km) | Meteo-France | Global |
| `ukmo_seamless` | UKMO Seamless | 0.09° (~10 km) | Met Office (UK) | Global |
| `ukmo_global_deterministic_10km` | UKMO Global 10km | 0.09° (~10 km) | Met Office (UK) | Global |
| `bom_access_global` | ACCESS-G | 0.25° (~25 km) | BoM (Australia) | Global |
| `cma_grapes_global` | GRAPES Global | 0.25° (~25 km) | CMA (China) | Global |
| `kma_seamless` | KMA Seamless | varies | KMA (South Korea) | Global + Regional |

### Regional / High-Resolution Models

| Model Key | Name | Resolution | Provider | Coverage |
|-----------|------|------------|----------|----------|
| `gfs_hrrr` | HRRR | 3 km | NCEP/NOAA | CONUS (USA) |
| `icon_eu` | ICON-EU | 0.0625° (~7 km) | DWD | Europe |
| `icon_d2` | ICON-D2 | 0.02° (~2 km) | DWD | Germany |
| `meteofrance_arpege_europe` | ARPEGE Europe | 0.1° (~10 km) | Meteo-France | Europe |
| `meteofrance_arome_france` | AROME France | 0.025° (~2.5 km) | Meteo-France | France |
| `meteofrance_arome_france_hd` | AROME France HD | 0.01° (~1 km) | Meteo-France | France |
| `gem_regional` | GEM Regional (RDPS) | 10 km | CMC | North America |
| `gem_hrdps_continental` | GEM HRDPS | 2.5 km | CMC | Canada |
| `jma_msm` | JMA MSM | 0.05° (~5 km) | JMA | Japan |
| `ukmo_uk_deterministic_2km` | UKMO UK 2km | 2 km | Met Office | UK |
| `kma_ldps` | KMA LDPS | 1.5 km | KMA | South Korea |
| `metno_nordic` | MetNo Nordic | 2.5 km | MET Norway | Scandinavia |
| `knmi_harmonie_arome_europe` | KNMI HARMONIE Europe | 5.5 km | KNMI | Europe |
| `dmi_harmonie_arome_europe` | DMI HARMONIE Europe | 2 km | DMI | Europe |
| `arpae_cosmo_2i` | COSMO 2I | 2.2 km | ARPAE | Italy |
| `arpae_cosmo_5m` | COSMO 5M | 5 km | ARPAE | Mediterranean |
| `meteoswiss_icon_ch1` | MeteoSwiss ICON-CH1 | 1 km | MeteoSwiss | Switzerland |
| `meteoswiss_icon_ch2` | MeteoSwiss ICON-CH2 | 2 km | MeteoSwiss | Switzerland |

### Ensemble Models

| Model Key | Name | Provider |
|-----------|------|----------|
| `ecmwf_ifs025_ensemble` | ECMWF IFS Ensemble | ECMWF |
| `ecmwf_aifs025_ensemble` | ECMWF AIFS Ensemble | ECMWF |
| `icon_seamless_eps` | ICON EPS Seamless | DWD |
| `icon_global_eps` | ICON Global EPS | DWD |
| `icon_eu_eps` | ICON-EU EPS | DWD |
| `gem_global_ensemble` | GEM Global Ensemble | CMC |
| `ncep_gefs_seamless` | GEFS Seamless | NCEP/NOAA |
| `ukmo_global_ensemble_20km` | UKMO Global Ensemble | Met Office |
| `bom_access_global_ensemble` | ACCESS-G Ensemble | BoM |

### Currently Enabled in Node

The model selector popup includes these 7 models by default:

- **ECMWF IFS 0.25°** — European Centre, global, 0.25° resolution
- **GFS (NOAA)** — US National Weather Service, global, 0.25°
- **ICON (DWD)** — German Weather Service, global, 0.125°
- **Meteo-France** — Meteo-France seamless, global, 0.1°
- **UKMO** — UK Met Office, global, 0.09°
- **JMA (Japan)** — Japan Meteorological Agency, global, 0.05°
- **GEM (Canada)** — Canadian Meteorological Centre, global, 0.25°

Additional models can be added to `MODELS` in `fetch_openmeteo.py` and `AVAILABLE_MODELS` in `web/js/model_selector.js`.

## Weather Variables

### Hourly Variables (LatLon mode)

Available via presets or custom selection:

| Variable | Description | Unit |
|----------|-------------|------|
| `temperature_2m` | 2m Temperature | °C |
| `relative_humidity_2m` | 2m Relative Humidity | % |
| `pressure_msl` | Pressure reduced to MSL | hPa |
| `surface_pressure` | Surface Pressure | hPa |
| `cloud_cover` | Cloud Cover | % |
| `wind_speed_10m` | 10m Wind Speed | m/s |
| `wind_speed_80m` | 80m Wind Speed | m/s |
| `wind_speed_120m` | 120m Wind Speed | m/s |
| `wind_speed_180m` | 180m Wind Speed | m/s |
| `wind_direction_10m` | 10m Wind Direction | ° |
| `wind_gusts_10m` | 10m Wind Gusts | m/s |
| `precipitation` | Precipitation | mm |
| `rain` | Rain | mm |
| `showers` | Showers | mm |
| `snowfall` | Snowfall | cm |
| `snow_depth` | Snow Depth | m |
| `shortwave_radiation` | Shortwave Radiation | W/m² |
| `direct_radiation` | Direct Radiation | W/m² |
| `diffuse_radiation` | Diffuse Radiation | W/m² |
| `direct_normal_irradiance` | Direct Normal Irradiance | W/m² |
| `cape` | CAPE | J/kg |
| `soil_temperature_0cm` | Soil Temperature (0cm) | °C |

### Variable Presets

| Preset | Variables |
|--------|-----------|
| Temperature & Wind | temperature_2m, wind_speed_10m, wind_direction_10m |
| Full Weather | temperature_2m, relative_humidity_2m, precipitation, wind_speed_10m, cloud_cover, pressure_msl |
| Solar & Radiation | shortwave_radiation, direct_radiation, diffuse_radiation, direct_normal_irradiance |
| Precipitation | precipitation, rain, showers, snowfall |
| Wind (all heights) | wind_speed_10m, wind_speed_80m, wind_speed_120m, wind_speed_180m, wind_gusts_10m |
| Custom | User-specified comma-separated list |

## Data Types

| Type | Description |
|------|-------------|
| `WEATHER_DATA` | Time-series weather data dict (timestamps, variables, units, model info) |
| `WEATHER_GRID` | 2D spatial grid dict (variable, lat/lon arrays, values matrix, metadata) |
| `LATLON_COORDS` | Single point dict (`latitude`, `longitude`) |
| `GRID_COORDS` | Bounding box dict (`lat_south`, `lon_west`, `lat_north`, `lon_east`) |

## Installation

Install via ComfyUI Manager or clone into `custom_nodes/`:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/PozzettiAndrea/ComfyUI-Weather.git
```

Dependencies are installed automatically. Key packages: `openmeteo-requests`, `numpy`, `matplotlib`, `requests`.

## License

MIT
