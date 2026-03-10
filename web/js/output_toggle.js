import { app } from "../../../scripts/app.js";

// Hide/show output slots based on backend selection.
// When latlon: hide WEATHER_GRID output. When grid: hide WEATHER_DATA output.
app.registerExtension({
    name: "weather.outputtoggle",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "Weather_FetchOpenMeteo" && nodeData.name !== "Weather_FetchJua") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);
            const node = this;

            // Output indices: 0 = WEATHER_DATA, 1 = WEATHER_GRID, 2 = Info
            function updateOutputVisibility() {
                if (!node.outputs || node.outputs.length < 2) return;
                const backendWidget = node.widgets?.find(w => w.name === "backend");
                const backend = backendWidget?.value || "latlon";

                if (backend === "grid") {
                    // Hide WEATHER_DATA (index 0), show WEATHER_GRID (index 1)
                    hideOutput(node, 0);
                    showOutput(node, 1);
                } else {
                    // Show WEATHER_DATA (index 0), hide WEATHER_GRID (index 1)
                    showOutput(node, 0);
                    hideOutput(node, 1);
                }
                node.setDirtyCanvas(true, true);
            }

            // Poll for backend changes
            let lastBackend = null;
            const interval = setInterval(() => {
                const backendWidget = node.widgets?.find(w => w.name === "backend");
                const current = backendWidget?.value || "latlon";
                if (current !== lastBackend) {
                    lastBackend = current;
                    updateOutputVisibility();
                }
            }, 200);

            // Initial update
            setTimeout(updateOutputVisibility, 100);

            const origOnRemoved = this.onRemoved;
            this.onRemoved = function () {
                clearInterval(interval);
                origOnRemoved?.apply(this, arguments);
            };

            return r;
        };
    },
});

function hideOutput(node, index) {
    if (!node.outputs[index]) return;
    // Disconnect any links from this output
    if (node.outputs[index].links && node.outputs[index].links.length > 0) {
        // Don't disconnect existing links — just visually hide
    }
    node.outputs[index]._visible = false;
    // Store original name if not already stored
    if (!node.outputs[index]._origName) {
        node.outputs[index]._origName = node.outputs[index].name;
    }
    node.outputs[index].name = "";
    node.outputs[index].type = -1; // Makes LiteGraph not render the slot
}

function showOutput(node, index) {
    if (!node.outputs[index]) return;
    node.outputs[index]._visible = true;
    if (node.outputs[index]._origName) {
        node.outputs[index].name = node.outputs[index]._origName;
    }
    // Restore the type
    if (index === 0) node.outputs[index].type = "WEATHER_DATA";
    if (index === 1) node.outputs[index].type = "WEATHER_GRID";
}
