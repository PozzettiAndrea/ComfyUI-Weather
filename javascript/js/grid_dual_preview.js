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
    name: "weather.griddualpreview",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "Weather_PreviewGridDual") return;

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
            iframe.src = getViewerUrl("grid_dual_viewer");
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

            // Persisted viewer state
            const viewerState = { view_state: "" };

            // Messages from iframe
            const onMessage = (event) => {
                // Provenance guard: the 'message' event is window-wide, so
                // without this we also handle every OTHER pack's iframe messages.
                if (event.source !== iframe.contentWindow) return;
                if (event.data?.type === "DUAL_INFO" && event.data.info) {
                    infoBar.textContent = event.data.info;
                } else if (event.data?.type === "DUAL_ERROR" && event.data.error) {
                    infoBar.innerHTML = `<span style="color:#ff6b6b;">Error: ${event.data.error}</span>`;
                } else if (event.data?.type === "VIEW_STATE") {
                    viewerState.view_state = event.data.state;
                }
            };
            window.addEventListener("message", onMessage);

            // Widget
            const widget = this.addDOMWidget(
                "grid_dual_preview",
                "WEATHER_GRID_DUAL_PREVIEW",
                container,
                {
                    getValue() { return JSON.stringify(viewerState); },
                    setValue(v) {
                        try { Object.assign(viewerState, JSON.parse(v)); } catch(e) {}
                    },
                }
            );
            widget.computeSize = () => [720, 520];

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

                if (message?.grid_dual_file && message.grid_dual_file[0]) {
                    const filename = message.grid_dual_file[0];
                    const filepath = buildViewUrl(filename);
                    const coastlinesUrl = `/extensions/${EXTENSION_FOLDER}/coastlines.json`;

                    viewerManager.switchViewer("grid_dual", getViewerUrl("grid_dual_viewer"), {
                        type: "LOAD_DUAL_GRID",
                        filepath: filepath,
                        coastlinesUrl: coastlinesUrl,
                        savedState: viewerState.view_state || "",
                    });
                }
            };

            this.setSize([720, 520]);

            return r;
        };
    },
});
