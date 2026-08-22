// Shared popup builder utilities for dropdown selectors

export function hideWidgetForGood(node, widget) {
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

export function getSelected(widget) {
    try {
        const arr = JSON.parse(widget.value);
        return Array.isArray(arr) ? arr : [];
    } catch { return []; }
}

export function createPopup(btn) {
    const popup = document.createElement("div");
    // Top-layer popover rather than a bare div: it renders above everything
    // without z-index games, is not clipped by any ancestor overflow, and gives
    // light dismiss (outside click / Esc) for free -- so no pack needs a
    // document-level listener. `inset:auto;margin:0` overrides the UA default
    // ([popover] is inset:0;margin:auto), which would otherwise centre it.
    popup.popover = "auto";
    popup.style.cssText =
        "position:fixed;inset:auto;margin:0;z-index:99999;background:#1e1e2e;border:1px solid #555;" +
        "border-radius:6px;padding:8px;box-shadow:0 4px 20px rgba(0,0,0,0.5);" +
        "font-family:sans-serif;font-size:12px;color:#ddd;min-width:280px;" +
        "max-height:420px;overflow-y:auto;";
    const rect = btn.getBoundingClientRect();
    popup.style.left = rect.left + "px";
    popup.style.top = (rect.bottom + 4) + "px";

    requestAnimationFrame(() => {
        const pr = popup.getBoundingClientRect();
        if (pr.right > window.innerWidth) popup.style.left = (window.innerWidth - pr.width - 8) + "px";
        if (pr.bottom > window.innerHeight) popup.style.top = (rect.top - pr.height - 4) + "px";
    });

    return popup;
}

export function addGroupHeader(popup, name) {
    const h = document.createElement("div");
    h.style.cssText =
        "font-weight:bold;margin-top:6px;margin-bottom:4px;padding:2px 4px;" +
        "font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;";
    h.textContent = name;
    popup.appendChild(h);
}

export function addRow(popup, item, inputEl) {
    const row = document.createElement("label");
    row.style.cssText =
        "display:flex;align-items:center;gap:6px;padding:4px 6px;cursor:pointer;border-radius:3px;";
    if (item.tip) row.title = item.tip;
    row.addEventListener("mouseenter", () => { row.style.background = "#2a2a4a"; });
    row.addEventListener("mouseleave", () => { row.style.background = ""; });
    row.appendChild(inputEl);

    const labelText = document.createElement("span");
    labelText.style.cssText = "flex:1;";
    labelText.textContent = item.label;
    row.appendChild(labelText);

    // Right-side detail text (resolution for models, unit for variables)
    const detail = item.res || item.unit;
    if (detail) {
        const detailText = document.createElement("span");
        detailText.style.cssText = "color:#666;font-size:10px;min-width:36px;text-align:right;";
        detailText.textContent = detail;
        row.appendChild(detailText);
    }

    popup.appendChild(row);
    return row;
}

export function addActionsRow(popup, { onSelectAll, onClear }) {
    const actionsRow = document.createElement("div");
    actionsRow.style.cssText =
        "display:flex;gap:8px;margin-bottom:6px;padding-bottom:6px;border-bottom:1px solid #333;";

    const selectAll = document.createElement("span");
    selectAll.textContent = "Select All";
    selectAll.style.cssText = "color:#6aa;cursor:pointer;font-size:11px;";
    selectAll.addEventListener("click", onSelectAll);
    actionsRow.appendChild(selectAll);

    const selectNone = document.createElement("span");
    selectNone.textContent = "Clear";
    selectNone.style.cssText = "color:#a66;cursor:pointer;font-size:11px;";
    selectNone.addEventListener("click", onClear);
    actionsRow.appendChild(selectNone);

    popup.appendChild(actionsRow);
}

export function setupOutsideClose(popup, btn, closeFunc) {
    // The popover is `auto`, so the browser closes it on outside click or Esc.
    // We only need to hear about it. The previous implementation attached a
    // capture-phase pointerdown listener to `document`, which sees every click
    // in the whole ComfyUI page -- including other packs' -- and had to be
    // removed by hand.
    popup.addEventListener("toggle", (e) => {
        if (e.newState !== "closed") return;
        // Light dismiss runs on pointerdown, which precedes the button's click.
        // Without this stamp, clicking the button while the popup is open would
        // close it and then immediately re-open it, so it could never be
        // toggled shut. `justDismissed(btn)` lets the click handler bail.
        btn._popoverClosedAt = performance.now();
        closeFunc();
    });
}

export function justDismissed(btn, ms = 250) {
    return performance.now() - (btn._popoverClosedAt || 0) < ms;
}

export function createSelectorButton(text) {
    const btnContainer = document.createElement("div");
    btnContainer.style.cssText = "width:100%;display:flex;align-items:center;padding:2px 0;";

    const btn = document.createElement("button");
    btn.style.cssText =
        "flex:1;padding:4px 8px;border:1px solid #555;border-radius:4px;" +
        "background:#2a2a3e;color:#ccc;font-size:11px;cursor:pointer;" +
        "font-family:sans-serif;text-align:left;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;";
    btn.textContent = text;
    btnContainer.appendChild(btn);

    return { btnContainer, btn };
}

export function addDOMSelectorWidget(node, name, type, btnContainer, storeWidget, btn, makeLabel, getValueFn) {
    const widget = node.addDOMWidget(name, type, btnContainer, {
        getValue() { return storeWidget.value; },
        setValue(v) {
            if (v) storeWidget.value = v;
            btn.textContent = makeLabel(getValueFn());
        },
    });
    widget.computeSize = () => [200, 26];
    return widget;
}
