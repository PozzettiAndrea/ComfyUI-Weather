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
    name: "weather.latloncollector",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "Weather_LatLonCollector") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);

            // Find and hide the points_store widget
            const storeWidget = this.widgets.find(w => w.name === "points_store");
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
            iframe.src = `/extensions/${EXTENSION_FOLDER}/latlon_map.html?v=` + Date.now();
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
            infoBar.textContent = "Click on the map to select a location";
            container.appendChild(infoBar);

            // Iframe load management
            let iframeLoaded = false;
            let pendingMessage = null;
            const viewerState = { view_state: "" };

            iframe.addEventListener("load", () => {
                iframeLoaded = true;
                // Send initial map load message with coastlines + saved state
                const markers = storeWidget ? storeWidget.value : "[]";
                const msg = {
                    type: "LOAD_MAP",
                    coastlinesUrl: `/extensions/${EXTENSION_FOLDER}/coastlines.json`,
                    savedMarkers: markers,
                    savedViewState: viewerState.view_state || "",
                };
                iframe.contentWindow.postMessage(msg, "*");
                if (pendingMessage) {
                    iframe.contentWindow.postMessage(pendingMessage, "*");
                    pendingMessage = null;
                }
            });

            // Messages from iframe
            const onMessage = (event) => {
                if (event.data?.type === "VIEW_STATE") {
                    viewerState.view_state = event.data.state;
                } else if (event.data?.type === "LATLON_UPDATE" && Array.isArray(event.data.markers)) {
                    const markers = event.data.markers;

                    // Update hidden widget
                    if (storeWidget) {
                        storeWidget.value = JSON.stringify(markers);
                    }

                    // Update info bar
                    if (markers.length === 0) {
                        infoBar.textContent = "Click on the map to select a location";
                    } else {
                        const last = markers[markers.length - 1];
                        let text = `Selected: (${last.lat.toFixed(4)}, ${last.lon.toFixed(4)})`;
                        if (markers.length > 1) {
                            text += `  |  ${markers.length} points total`;
                        }
                        infoBar.textContent = text;
                    }
                }
            };
            window.addEventListener("message", onMessage);

            // Widget
            const widget = this.addDOMWidget(
                "map_preview",
                "LATLON_MAP_PREVIEW",
                container,
                {
                    getValue() {
                        return JSON.stringify({
                            markers: storeWidget ? storeWidget.value : "[]",
                            view_state: viewerState.view_state,
                        });
                    },
                    setValue(v) {
                        try {
                            const parsed = JSON.parse(v);
                            if (parsed.markers && storeWidget) {
                                storeWidget.value = parsed.markers;
                            }
                            if (parsed.view_state) {
                                viewerState.view_state = parsed.view_state;
                            }
                        } catch (e) {
                            // Legacy: plain markers array
                            if (storeWidget && v) {
                                storeWidget.value = v;
                            }
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
