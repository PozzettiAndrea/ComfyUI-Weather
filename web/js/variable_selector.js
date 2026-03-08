import { app } from "../../../scripts/app.js";
import {
    hideWidgetForGood, getSelected, createPopup, addGroupHeader, addRow,
    setupOutsideClose, createSelectorButton,
} from "./popup_utils.js";

// Must match VAR_META / GRID_VARIABLES in fetch_openmeteo.py
const VARIABLE_GROUPS = [
    {
        name: "Temperature",
        vars: [
            { key: "temperature_2m",      label: "2m Temperature",       unit: "°C",   tip: "Air temperature at 2 meters above ground" },
            { key: "soil_temperature_0cm", label: "Soil Temperature (0cm)", unit: "°C", tip: "Temperature at the soil surface" },
        ],
    },
    {
        name: "Wind",
        vars: [
            { key: "wind_speed_10m",      label: "10m Wind Speed",       unit: "m/s",  tip: "Wind speed at 10 meters above ground" },
            { key: "wind_speed_80m",       label: "80m Wind Speed",       unit: "m/s",  tip: "Wind speed at 80m — relevant for wind energy" },
            { key: "wind_speed_120m",      label: "120m Wind Speed",      unit: "m/s",  tip: "Wind speed at 120m" },
            { key: "wind_speed_180m",      label: "180m Wind Speed",      unit: "m/s",  tip: "Wind speed at 180m" },
            { key: "wind_direction_10m",   label: "10m Wind Direction",   unit: "°",    tip: "Wind direction at 10m (0°=N, 90°=E, 180°=S, 270°=W)" },
            { key: "wind_gusts_10m",       label: "10m Wind Gusts",       unit: "m/s",  tip: "Maximum wind gust speed at 10m" },
        ],
    },
    {
        name: "Precipitation",
        vars: [
            { key: "precipitation",        label: "Total Precipitation",  unit: "mm",   tip: "Total precipitation (rain + showers + snow)" },
            { key: "rain",                 label: "Rain",                 unit: "mm",   tip: "Liquid rain amount" },
            { key: "showers",              label: "Showers",              unit: "mm",   tip: "Showers from convective precipitation" },
            { key: "snowfall",             label: "Snowfall",             unit: "cm",   tip: "Snowfall amount in centimeters" },
            { key: "snow_depth",           label: "Snow Depth",           unit: "m",    tip: "Snow depth on the ground" },
        ],
    },
    {
        name: "Atmosphere",
        vars: [
            { key: "relative_humidity_2m", label: "2m Relative Humidity", unit: "%",    tip: "Relative humidity at 2 meters above ground" },
            { key: "pressure_msl",         label: "Mean Sea Level Pressure", unit: "hPa", tip: "Atmospheric pressure reduced to mean sea level" },
            { key: "surface_pressure",     label: "Surface Pressure",     unit: "hPa",  tip: "Atmospheric pressure at the surface" },
            { key: "cloud_cover",          label: "Cloud Cover",          unit: "%",    tip: "Total cloud cover as percentage of sky" },
            { key: "cape",                 label: "CAPE",                 unit: "J/kg", tip: "Convective Available Potential Energy — thunderstorm potential" },
        ],
    },
    {
        name: "Radiation",
        vars: [
            { key: "shortwave_radiation",  label: "Shortwave Radiation",  unit: "W/m²", tip: "Total incoming shortwave solar radiation" },
            { key: "direct_radiation",     label: "Direct Radiation",     unit: "W/m²", tip: "Direct solar radiation on a horizontal surface" },
            { key: "diffuse_radiation",    label: "Diffuse Radiation",    unit: "W/m²", tip: "Diffuse solar radiation (scattered by atmosphere)" },
            { key: "direct_normal_irradiance", label: "Direct Normal Irradiance", unit: "W/m²", tip: "Direct radiation on a surface perpendicular to the sun" },
        ],
    },
];

const PRESETS = {
    "Temperature & Wind":  ["temperature_2m", "wind_speed_10m", "wind_direction_10m"],
    "Full Weather":        ["temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m", "cloud_cover", "pressure_msl"],
    "Solar & Radiation":   ["shortwave_radiation", "direct_radiation", "diffuse_radiation", "direct_normal_irradiance"],
    "Precipitation":       ["precipitation", "rain", "showers", "snowfall"],
    "Wind (all heights)":  ["wind_speed_10m", "wind_speed_80m", "wind_speed_120m", "wind_speed_180m", "wind_gusts_10m"],
};

const GRID_KEYS = new Set([
    "temperature_2m", "relative_humidity_2m", "pressure_msl", "surface_pressure",
    "cloud_cover", "wind_speed_10m", "wind_speed_80m", "wind_direction_10m",
    "wind_gusts_10m", "precipitation", "rain", "snowfall",
    "shortwave_radiation", "direct_radiation", "diffuse_radiation",
    "cape", "soil_temperature_0cm", "snow_depth",
]);

const ALL_VARS = {};
for (const g of VARIABLE_GROUPS) for (const v of g.vars) ALL_VARS[v.key] = v;


function makeMultiLabel(selected) {
    if (!Array.isArray(selected)) {
        try { selected = JSON.parse(selected); } catch { selected = []; }
    }
    if (selected.length === 0) return "Select Variables...";
    if (selected.length === 1) {
        const v = ALL_VARS[selected[0]];
        return v ? v.label : selected[0];
    }
    if (selected.length <= 3) return selected.map(k => ALL_VARS[k]?.label || k).join(", ");
    return `${selected.length} variables selected`;
}


// Build a multi-select checkbox popup for variables
function buildVariablePopup(btn, storeWidget, filterFn, closePopup) {
    const selected = new Set(getSelected(storeWidget));
    const popup = createPopup(btn);

    // Presets row
    const presetsRow = document.createElement("div");
    presetsRow.style.cssText = "display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid #333;";
    for (const [name, vars] of Object.entries(PRESETS)) {
        // Only show preset if at least one of its vars passes the filter
        const filteredVars = vars.filter(filterFn);
        if (filteredVars.length === 0) continue;
        const tag = document.createElement("button");
        tag.textContent = name;
        tag.style.cssText =
            "background:#2a2a3e;color:#aaa;border:1px solid #444;border-radius:3px;" +
            "padding:2px 6px;font-size:10px;cursor:pointer;font-family:sans-serif;";
        tag.addEventListener("mouseenter", () => { tag.style.background = "#3a3a5e"; });
        tag.addEventListener("mouseleave", () => { tag.style.background = "#2a2a3e"; });
        tag.addEventListener("click", (e) => {
            e.preventDefault();
            popup.querySelectorAll("input[type=checkbox]").forEach(cb => { cb.checked = filteredVars.includes(cb.value); });
            sync();
        });
        presetsRow.appendChild(tag);
    }

    const allBtn = document.createElement("button");
    allBtn.textContent = "All";
    allBtn.style.cssText = "background:none;color:#6aa;border:none;font-size:10px;cursor:pointer;font-family:sans-serif;";
    allBtn.addEventListener("click", (e) => { e.preventDefault(); popup.querySelectorAll("input[type=checkbox]").forEach(cb => { cb.checked = true; }); sync(); });
    presetsRow.appendChild(allBtn);

    const clearBtn = document.createElement("button");
    clearBtn.textContent = "Clear";
    clearBtn.style.cssText = "background:none;color:#a66;border:none;font-size:10px;cursor:pointer;font-family:sans-serif;";
    clearBtn.addEventListener("click", (e) => { e.preventDefault(); popup.querySelectorAll("input[type=checkbox]").forEach(cb => { cb.checked = false; }); sync(); });
    presetsRow.appendChild(clearBtn);

    popup.appendChild(presetsRow);

    for (const group of VARIABLE_GROUPS) {
        const groupVars = group.vars.filter(v => filterFn(v.key));
        if (groupVars.length === 0) continue;
        addGroupHeader(popup, group.name);
        for (const v of groupVars) {
            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.value = v.key;
            cb.checked = selected.has(v.key);
            cb.style.cssText = "margin:0;accent-color:#6a6;";
            cb.addEventListener("change", sync);
            addRow(popup, v, cb);
        }
    }

    document.body.appendChild(popup);
    setupOutsideClose(popup, btn, closePopup);

    function sync() {
        const sel = [];
        popup.querySelectorAll("input[type=checkbox]").forEach(cb => { if (cb.checked) sel.push(cb.value); });
        storeWidget.value = JSON.stringify(sel);
        btn.textContent = makeMultiLabel(sel);
    }

    return popup;
}


app.registerExtension({
    name: "weather.variableselector",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "Weather_FetchOpenMeteo") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);
            const node = this;

            function getBackend() {
                const w = node.widgets?.find(w => w.name === "backend");
                return w?.value || "latlon";
            }

            function findAndHide(name) {
                const w = node.widgets?.find(w => w.name === name);
                if (w && w.type !== "converted-widget") {
                    hideWidgetForGood(node, w);
                }
                return w || null;
            }

            let popup = null;
            function closePopup() { if (popup) { popup.remove(); popup = null; } }

            const { btnContainer, btn } = createSelectorButton("Select Variables...");

            function updateLabel() {
                const backend = getBackend();
                const widgetName = backend === "grid"
                    ? "backend.grid_variables_selection"
                    : "backend.variables_selection";
                const w = node.widgets?.find(w => w.name === widgetName);
                btn.textContent = makeMultiLabel(getSelected(w || { value: "[]" }));
            }

            function openLatlonPopup() {
                const sw = node.widgets?.find(w => w.name === "backend.variables_selection");
                if (!sw) return;
                popup = buildVariablePopup(btn, sw, () => true, closePopup);
            }

            function openGridPopup() {
                const sw = node.widgets?.find(w => w.name === "backend.grid_variables_selection");
                if (!sw) return;
                popup = buildVariablePopup(btn, sw, k => GRID_KEYS.has(k), closePopup);
            }

            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                if (popup) { closePopup(); return; }
                const backend = getBackend();
                console.log("[weather.varselector] click, backend:", backend,
                    "widgets:", node.widgets?.map(w => `${w.name}(${w.type})`));
                if (backend === "grid") openGridPopup();
                else openLatlonPopup();
            });

            const domWidget = this.addDOMWidget("variable_selector_btn", "VAR_SELECTOR", btnContainer, {
                getValue() { return ""; },
                setValue() { updateLabel(); },
            });
            domWidget.computeSize = () => [200, 26];

            let pollCount = 0;
            const pollInterval = setInterval(() => {
                findAndHide("backend.variables_selection");
                findAndHide("backend.grid_variables_selection");
                updateLabel();
                pollCount++;
                if (pollCount > 200) clearInterval(pollInterval);
            }, 100);

            const origOnConfigure = this.onConfigure;
            this.onConfigure = function (config) {
                origOnConfigure?.apply(this, arguments);
                setTimeout(() => { findAndHide("backend.variables_selection"); findAndHide("backend.grid_variables_selection"); updateLabel(); }, 50);
                setTimeout(() => { findAndHide("backend.variables_selection"); findAndHide("backend.grid_variables_selection"); updateLabel(); }, 200);
                setTimeout(() => { findAndHide("backend.variables_selection"); findAndHide("backend.grid_variables_selection"); updateLabel(); }, 500);
            };

            const origOnRemoved = this.onRemoved;
            this.onRemoved = function () {
                closePopup();
                clearInterval(pollInterval);
                origOnRemoved?.apply(this, arguments);
            };

            return r;
        };
    },
});
