import { app } from "../../../scripts/app.js";

const EXTENSION_FOLDER = (() => {
    const url = import.meta.url;
    const match = url.match(/\/extensions\/([^/]+)\//);
    return match ? match[1] : "ComfyUI-Weather";
})();

function getViewerUrl(viewerName) {
    return `/extensions/${EXTENSION_FOLDER}/${viewerName}.html?v=` + Date.now();
}

function buildViewUrl(filename) {
    const normalized = filename.replace(/\\/g, "/");
    const pathMatch = normalized.match(/(?:^|\/)(output|input|temp)\/(.+)$/);
    if (pathMatch) {
        const [, type, relPath] = pathMatch;
        const parts = relPath.split("/");
        const fname = parts.pop();
        const subfolder = parts.join("/");
        return `/view?filename=${encodeURIComponent(fname)}&type=${type}&subfolder=${encodeURIComponent(subfolder)}`;
    }
    return `/view?filename=${encodeURIComponent(normalized.split("/").pop())}&type=output&subfolder=`;
}

function createViewerManager(iframe) {
    let currentViewerType = null;
    let iframeLoaded = false;
    let pendingMessage = null;

    iframe.addEventListener("load", () => {
        iframeLoaded = true;
        if (pendingMessage && iframe.contentWindow) {
            iframe.contentWindow.postMessage(pendingMessage, "*");
            pendingMessage = null;
        }
    });

    return {
        sendMessage(data) {
            if (iframeLoaded && iframe.contentWindow) {
                iframe.contentWindow.postMessage(data, "*");
            } else {
                pendingMessage = data;
            }
        },
        switchViewer(viewerType, viewerUrl, messageData) {
            if (viewerType === currentViewerType) {
                this.sendMessage(messageData);
                return false;
            }
            currentViewerType = viewerType;
            iframeLoaded = false;
            pendingMessage = messageData;
            iframe.src = viewerUrl;
            return true;
        }
    };
}

app.registerExtension({
    name: "weather.gridpreview",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "Weather_PreviewGrid") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);

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
            iframe.src = getViewerUrl("grid_viewer");
            iframe.style.width = "100%";
            iframe.style.flex = "1 1 0";
            iframe.style.minHeight = "0";
            iframe.style.border = "none";
            iframe.style.backgroundColor = "#1a1a2e";
            container.appendChild(iframe);

            // Info bar
            const infoBar = document.createElement("div");
            infoBar.style.cssText = "padding:4px 8px;font-size:10px;line-height:1.4;color:#aaa;background:#1a1a1a;border-top:1px solid #333;font-family:monospace;white-space:pre;flex-shrink:0;overflow:hidden;";
            infoBar.textContent = "Waiting for data...";
            container.appendChild(infoBar);

            // Viewer manager
            const viewerManager = createViewerManager(iframe);

            // Persisted viewer state (serialized with the workflow)
            const viewerState = { view_state: "" };

            // Messages from iframe
            const onMessage = (event) => {
                if (event.data?.type === "GRID_INFO" && event.data.info) {
                    const i = event.data.info;
                    const frameInfo = i.frames > 1 ? `  Frame ${i.frame}/${i.frames}` : "";
                    infoBar.textContent =
                        `${i.variable} [${i.unit}]  ${i.timestamp}${frameInfo}\n` +
                        `Grid: ${i.rows}\u00d7${i.cols}  Lat: ${i.latRange}  Lon: ${i.lonRange}\n` +
                        `Range: ${i.vmin} to ${i.vmax} ${i.unit}`;
                } else if (event.data?.type === "GRID_ERROR" && event.data.error) {
                    infoBar.innerHTML = `<span style="color:#ff6b6b;">Error: ${event.data.error}</span>`;
                } else if (event.data?.type === "VIEW_STATE") {
                    // Iframe reports its current view state for persistence
                    viewerState.view_state = event.data.state;
                }
            };
            window.addEventListener("message", onMessage);

            // Widget
            const widget = this.addDOMWidget(
                "grid_preview",
                "WEATHER_GRID_PREVIEW",
                container,
                {
                    getValue() { return JSON.stringify(viewerState); },
                    setValue(v) {
                        try { Object.assign(viewerState, JSON.parse(v)); } catch(e) {}
                    },
                }
            );
            widget.computeSize = () => [512, 640];

            // Cleanup
            const origOnRemoved = this.onRemoved;
            this.onRemoved = function () {
                window.removeEventListener("message", onMessage);
                origOnRemoved?.apply(this, arguments);
            };

            // Handle execution
            const origOnExecuted = this.onExecuted;
            this.onExecuted = function (message) {
                origOnExecuted?.apply(this, arguments);

                if (message?.grid_file && message.grid_file[0]) {
                    const filename = message.grid_file[0];
                    const filepath = buildViewUrl(filename);
                    const coastlinesUrl = `/extensions/${EXTENSION_FOLDER}/coastlines.json`;

                    viewerManager.switchViewer("grid", getViewerUrl("grid_viewer"), {
                        type: "LOAD_GRID",
                        filepath: filepath,
                        coastlinesUrl: coastlinesUrl,
                        savedState: viewerState.view_state || "",
                    });
                }
            };

            this.setSize([512, 640]);

            return r;
        };
    },
});
