import { app } from "../../../scripts/app.js";

const EXTENSION_FOLDER = (() => {
    const url = import.meta.url;
    const match = url.match(/\/extensions\/([^/]+)\//);
    return match ? match[1] : "ComfyUI-Weather";
})();

function getViewerUrl(name) {
    return `/extensions/${EXTENSION_FOLDER}/${name}.html?v=` + Date.now();
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

app.registerExtension({
    name: "weather.datapreview",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "Weather_PreviewData") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);

            const container = document.createElement("div");
            container.style.cssText = "width:100%;height:100%;display:flex;flex-direction:column;background:#0d1117;overflow:hidden;";

            const iframe = document.createElement("iframe");
            iframe.src = getViewerUrl("data_viewer");
            iframe.style.cssText = "width:100%;flex:1 1 0;min-height:0;border:none;background:#0d1117;";
            container.appendChild(iframe);

            const infoBar = document.createElement("div");
            infoBar.style.cssText = "padding:4px 8px;font-size:10px;line-height:1.4;color:#8b949e;background:#161b22;border-top:1px solid #30363d;font-family:monospace;white-space:pre;flex-shrink:0;overflow:hidden;";
            infoBar.textContent = "Waiting for data...";
            container.appendChild(infoBar);

            let iframeLoaded = false;
            let pendingMessage = null;
            const viewerState = { view_state: "" };

            iframe.addEventListener("load", () => {
                iframeLoaded = true;
                if (pendingMessage && iframe.contentWindow) {
                    iframe.contentWindow.postMessage(pendingMessage, "*");
                    pendingMessage = null;
                }
            });

            function sendToIframe(msg) {
                if (iframeLoaded && iframe.contentWindow) {
                    iframe.contentWindow.postMessage(msg, "*");
                } else {
                    pendingMessage = msg;
                }
            }

            const onMessage = (event) => {
                if (event.data?.type === "DATA_INFO") {
                    infoBar.textContent = event.data.info || "";
                } else if (event.data?.type === "DATA_ERROR") {
                    infoBar.innerHTML = `<span style="color:#f85149;">Error: ${event.data.error}</span>`;
                } else if (event.data?.type === "DATA_VIEW_STATE") {
                    viewerState.view_state = event.data.state;
                }
            };
            window.addEventListener("message", onMessage);

            const widget = this.addDOMWidget(
                "data_preview",
                "WEATHER_DATA_PREVIEW",
                container,
                {
                    getValue() { return JSON.stringify(viewerState); },
                    setValue(v) {
                        try { Object.assign(viewerState, JSON.parse(v)); } catch(e) {}
                    },
                }
            );
            widget.computeSize = () => [512, 520];

            const origOnRemoved = this.onRemoved;
            this.onRemoved = function () {
                window.removeEventListener("message", onMessage);
                origOnRemoved?.apply(this, arguments);
            };

            const origOnExecuted = this.onExecuted;
            this.onExecuted = function (message) {
                origOnExecuted?.apply(this, arguments);

                if (message?.data_file && message.data_file[0]) {
                    const filename = message.data_file[0];
                    const filepath = buildViewUrl(filename);

                    // Reset iframe to reload viewer with new data
                    iframeLoaded = false;
                    pendingMessage = {
                        type: "LOAD_DATA",
                        filepath,
                        savedState: viewerState.view_state || "",
                    };
                    iframe.src = getViewerUrl("data_viewer");
                }
            };

            this.setSize([512, 520]);
            return r;
        };
    },
});
