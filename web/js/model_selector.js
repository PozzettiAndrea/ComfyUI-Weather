import { app } from "../../../scripts/app.js";
import {
    hideWidgetForGood, getSelected, createPopup, addGroupHeader, addRow,
    addActionsRow, setupOutsideClose, createSelectorButton, addDOMSelectorWidget,
} from "./popup_utils.js";

// Must match LATLON_MODELS in fetch_openmeteo.py
const LATLON_MODELS = [
    { key: "ecmwf_ifs025",         label: "ECMWF IFS 0.25°",       res: "0.25°" },
    { key: "gfs_seamless",          label: "GFS (NOAA)",             res: "0.25°" },
    { key: "icon_seamless",         label: "ICON (DWD)",             res: "0.125°" },
    { key: "meteofrance_seamless",  label: "Météo-France",           res: "0.1°" },
    { key: "ukmo_seamless",         label: "UKMO",                   res: "0.09°" },
    { key: "jma_seamless",          label: "JMA (Japan)",            res: "0.05°" },
    { key: "gem_seamless",          label: "GEM (Canada)",           res: "0.25°" },
];

// Must match GRID_MODELS in fetch_openmeteo.py
const GRID_MODELS = [
    { key: "ecmwf_ifs025",                    label: "ECMWF IFS 0.25°",        res: "0.25°" },
    { key: "icon_global",                     label: "ICON Global (DWD)",      res: "0.1°" },
    { key: "icon_eu",                         label: "ICON EU (DWD)",          res: "0.0625°" },
    { key: "icon_d2",                         label: "ICON D2 (DWD)",          res: "0.02°" },
    { key: "meteofrance_arpege_world025",     label: "ARPEGE World 0.25°",     res: "0.25°" },
    { key: "meteofrance_arpege_europe",       label: "ARPEGE Europe 0.1°",     res: "0.1°" },
    { key: "meteofrance_arome_france",        label: "AROME France 0.025°",    res: "0.025°" },
    { key: "ukmo_global_deterministic_10km",  label: "UKMO Global 10km",       res: "0.09°" },
    { key: "gem_global",                      label: "GEM Global (Canada)",    res: "0.15°" },
    { key: "jma_gsm",                         label: "JMA GSM (Japan)",        res: "0.5°" },
    { key: "cma_grapes_global",               label: "GRAPES Global (CMA)",    res: "0.1°" },
    { key: "knmi_harmonie_arome_europe",      label: "HARMONIE AROME (KNMI)",  res: "0.04°" },
];

// Must match JUA_MODELS in fetch_jua.py
const JUA_MODELS = [
    { key: "ept2", label: "EPT-2 (Jua)", res: "~11km" },
];

const ALL_MODELS = [...LATLON_MODELS, ...GRID_MODELS, ...JUA_MODELS];

function makeLabel(selected) {
    if (selected.length === 0) return "Select Models...";
    if (selected.length === 1) {
        const m = ALL_MODELS.find(m => m.key === selected[0]);
        return m ? m.label : selected[0];
    }
    return `${selected.length} models selected`;
}

function getBackendValue(node) {
    const w = node.widgets?.find(w => w.name === "backend");
    return w?.value || "latlon";
}

function getModelsForNode(node) {
    if (node.comfyClass === "Weather_FetchJua") return JUA_MODELS;
    return getBackendValue(node) === "grid" ? GRID_MODELS : LATLON_MODELS;
}

function getModelsForBackend(backend) {
    return backend === "grid" ? GRID_MODELS : LATLON_MODELS;
}

app.registerExtension({
    name: "weather.modelselector",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "Weather_FetchOpenMeteo" && nodeData.name !== "Weather_FetchJua") return;
        const isJua = nodeData.name === "Weather_FetchJua";

        const onNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);

            const storeWidget = this.widgets.find(w => w.name === "models_selection");
            if (!storeWidget) return r;

            hideWidgetForGood(this, storeWidget);

            const node = this;
            const { btnContainer, btn } = createSelectorButton(makeLabel(getSelected(storeWidget)));

            let popup = null;
            function closePopup() { if (popup) { popup.remove(); popup = null; } }

            function updateFromPopup() {
                if (!popup) return;
                const checks = popup.querySelectorAll("input[type=checkbox]");
                const selected = [];
                checks.forEach(cb => { if (cb.checked) selected.push(cb.value); });
                storeWidget.value = JSON.stringify(selected);
                btn.textContent = makeLabel(selected);
            }

            function openPopup() {
                if (popup) { closePopup(); return; }

                const selected = new Set(getSelected(storeWidget));
                const models = isJua ? getModelsForNode(node) : getModelsForBackend(getBackendValue(node));

                popup = createPopup(btn);

                // Title
                const backend = getBackendValue(node);
                addGroupHeader(popup, isJua ? "Jua Models" : (backend === "grid" ? "Grid Models (bbox)" : "NWP Models"));

                // Select all / clear
                addActionsRow(popup, {
                    onSelectAll: () => {
                        popup.querySelectorAll("input[type=checkbox]").forEach(cb => { cb.checked = true; });
                        updateFromPopup();
                    },
                    onClear: () => {
                        popup.querySelectorAll("input[type=checkbox]").forEach(cb => { cb.checked = false; });
                        updateFromPopup();
                    },
                });

                // Model checkboxes
                for (const model of models) {
                    const cb = document.createElement("input");
                    cb.type = "checkbox";
                    cb.value = model.key;
                    cb.checked = selected.has(model.key);
                    cb.style.cssText = "margin:0;accent-color:#6a6;";
                    cb.addEventListener("change", updateFromPopup);
                    addRow(popup, model, cb);
                }

                document.body.appendChild(popup);
                setupOutsideClose(popup, btn, closePopup);
            }

            btn.addEventListener("click", (e) => { e.stopPropagation(); openPopup(); });

            addDOMSelectorWidget(
                this, "model_selector_btn", "MODEL_SELECTOR",
                btnContainer, storeWidget, btn, makeLabel,
                () => getSelected(storeWidget),
            );

            const origOnRemoved = this.onRemoved;
            this.onRemoved = function () { closePopup(); origOnRemoved?.apply(this, arguments); };

            return r;
        };
    },
});
