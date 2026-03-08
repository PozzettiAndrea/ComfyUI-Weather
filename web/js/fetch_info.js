import { app } from "../../../scripts/app.js";

const TOGGLE_HEIGHT = 28;
const DEFAULT_CONTENT_HEIGHT = 80;

function escapeHTML(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\n/g, "<br>");
}

app.registerExtension({
    name: "weather.fetchinfo",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "Weather_FetchOpenMeteo") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);

            let expanded = false;
            let contentHeight = DEFAULT_CONTENT_HEIGHT;
            let widgetHeight = TOGGLE_HEIGHT;
            const node = this;

            const container = document.createElement("div");
            container.style.cssText =
                "background:#1a1a2e;border:1px solid #333;border-radius:4px;" +
                "overflow:hidden;display:flex;flex-direction:column;height:100%;";

            // Header bar
            const header = document.createElement("div");
            header.style.cssText =
                "display:flex;align-items:center;gap:6px;padding:2px 8px;" +
                "cursor:pointer;user-select:none;font-size:11px;color:#888;flex-shrink:0;";

            const arrow = document.createElement("span");
            arrow.style.cssText = "font-size:8px;display:inline-block;transition:transform 0.15s;";
            arrow.textContent = "\u25B6";

            const label = document.createElement("span");
            label.textContent = "Info";

            header.appendChild(arrow);
            header.appendChild(label);

            // Content
            const content = document.createElement("div");
            content.style.cssText =
                "padding:6px 8px;border-top:1px solid #333;font-size:10px;line-height:1.4;" +
                "color:#ccc;display:none;overflow-y:auto;flex:1;min-height:0;" +
                "font-family:monospace;white-space:pre-wrap;";

            container.appendChild(header);
            container.appendChild(content);

            const widget = this.addDOMWidget("fetch_info_panel", "FETCH_INFO", container, {
                getValue() { return expanded ? "true" : "false"; },
                setValue(v) { if (v === "true") setExpanded(true); },
                getMinHeight: () => widgetHeight,
                getHeight: () => widgetHeight,
            });

            requestAnimationFrame(() => {
                node.setSize([node.size[0], node.computeSize()[1]]);
                node.setDirtyCanvas(true, true);
            });

            function resize() {
                widgetHeight = expanded ? TOGGLE_HEIGHT + contentHeight : TOGGLE_HEIGHT;
                node.setSize([node.size[0], node.computeSize()[1]]);
                node.setDirtyCanvas(true, true);
            }

            function setExpanded(val) {
                expanded = val;
                content.style.display = expanded ? "block" : "none";
                arrow.style.transform = expanded ? "rotate(90deg)" : "";
                resize();
            }

            header.addEventListener("click", () => setExpanded(!expanded));

            // Handle execution results
            const onExecuted = this.onExecuted;
            this.onExecuted = function (message) {
                onExecuted?.apply(this, arguments);

                if (message?.text && message.text.length > 0) {
                    const text = message.text[0];
                    content.innerHTML = escapeHTML(text);

                    // Show first line as label
                    const firstLine = text.split("\n")[0].trim();
                    if (firstLine) label.textContent = firstLine;

                    // Auto-size content height based on line count
                    const lines = text.split("\n").length;
                    contentHeight = Math.min(Math.max(40, lines * 14 + 16), 200);
                    resize();
                }
            };

            return r;
        };
    },
});
