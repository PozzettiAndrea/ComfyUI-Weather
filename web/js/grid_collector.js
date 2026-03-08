import { app } from "../../../scripts/app.js";

const EXTENSION_FOLDER = (() => {
    const url = import.meta.url;
    const match = url.match(/\/extensions\/([^/]+)\//);
    return match ? match[1] : "ComfyUI-Weather";
})();

function hideWidgetForGood(node, widget) {
    widget.origType = widget.type;
    widget.origComputeSize = widget.computeSize;
    widget.computeSize = () => [0, -4];
    widget.type = "converted-widget";
    widget.hidden = true;
    if (widget.element) {
        widget.element.style.display = "none";
        widget.element.style.visibility = "hidden";
    }
}

app.registerExtension({
    name: "weather.gridcollector",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "Weather_GridCollector") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);

            // Find and hide the bbox_store widget
            const storeWidget = this.widgets.find(w => w.name === "bbox_store");
            if (storeWidget) {
                hideWidgetForGood(this, storeWidget);
            }

            // Container
            const container = document.createElement("div");
            container.style.width = "100%";
            container.style.height = "100%";
            container.style.display = "flex";
            container.style.flexDirection = "column";
            container.style.backgroundColor = "#1a1a2e";
            container.style.overflow = "hidden";

            // Iframe
            const iframe = document.createElement("iframe");
            iframe.src = `/extensions/${EXTENSION_FOLDER}/grid_map.html?v=` + Date.now();
            iframe.style.width = "100%";
            iframe.style.flex = "1 1 0";
            iframe.style.minHeight = "0";
            iframe.style.border = "none";
            iframe.style.backgroundColor = "#1a1a2e";
            container.appendChild(iframe);

            // Info bar
            const infoBar = document.createElement("div");
            infoBar.style.cssText =
                "padding:4px 8px;font-size:10px;line-height:1.4;color:#aaa;background:#1a1a1a;" +
                "border-top:1px solid #333;font-family:monospace;white-space:pre;flex-shrink:0;overflow:hidden;";
            infoBar.textContent = "Click and drag to draw a bounding box";
            container.appendChild(infoBar);

            // Iframe load management
            let iframeLoaded = false;

            iframe.addEventListener("load", () => {
                iframeLoaded = true;
                const saved = storeWidget ? storeWidget.value : "{}";
                let savedBbox = null;
                try { savedBbox = JSON.parse(saved); } catch (e) {}
                iframe.contentWindow.postMessage({
                    type: "LOAD_MAP",
                    coastlinesUrl: `/extensions/${EXTENSION_FOLDER}/coastlines.json`,
                    savedBbox: savedBbox,
                }, "*");
            });

            // Messages from iframe
            const onMessage = (event) => {
                if (event.data?.type === "BBOX_UPDATE") {
                    const bbox = event.data.bbox;

                    if (storeWidget) {
                        storeWidget.value = bbox ? JSON.stringify(bbox) : "{}";
                    }

                    if (bbox) {
                        const latR = Math.abs(bbox.lat_north - bbox.lat_south);
                        const lonR = Math.abs(bbox.lon_east - bbox.lon_west);
                        infoBar.textContent =
                            `N: ${bbox.lat_north.toFixed(2)}°  S: ${bbox.lat_south.toFixed(2)}°  ` +
                            `W: ${bbox.lon_west.toFixed(2)}°  E: ${bbox.lon_east.toFixed(2)}°  ` +
                            `(${latR.toFixed(1)}° × ${lonR.toFixed(1)}°)`;
                    } else {
                        infoBar.textContent = "Click and drag to draw a bounding box";
                    }
                }
            };
            window.addEventListener("message", onMessage);

            // Widget
            const widget = this.addDOMWidget(
                "grid_map_preview",
                "GRID_MAP_PREVIEW",
                container,
                {
                    getValue() {
                        return storeWidget ? storeWidget.value : "{}";
                    },
                    setValue(v) {
                        if (storeWidget && v) {
                            storeWidget.value = v;
                        }
                    },
                }
            );
            widget.computeSize = () => [400, 300];

            // Cleanup
            const origOnRemoved = this.onRemoved;
            this.onRemoved = function () {
                window.removeEventListener("message", onMessage);
                origOnRemoved?.apply(this, arguments);
            };

            this.setSize([400, 340]);

            return r;
        };
    },
});
