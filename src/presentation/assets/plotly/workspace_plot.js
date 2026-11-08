/* Local renderer for the graphing workspace. Data arrives as JSON from Qt. */
"use strict";

const workspaceColors = [
    "#216653", "#305A9D", "#A7442A", "#75458F", "#006B78", "#8D590B",
    "#A63763", "#455E65",
];
const workspaceDashes = ["solid", "dash", "dot", "dashdot"];
let pendingWorkspace = null;
let workspaceRendering = null;
let workspaceReady = false;
let workspaceMode = "2d";
let workspaceViewport = null;
let workspaceReset = null;
let supportsWebGL;

function hasWebGL() {
    if (supportsWebGL === undefined) {
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("webgl");
        supportsWebGL = Boolean(context);
        context?.getExtension("WEBGL_lose_context")?.loseContext();
    }
    return supportsWebGL;
}

function workspaceLayout(payload) {
    const { paper, ink, grid, axis } = document.body.dataset;
    const axisStyle = {
        gridcolor: grid,
        zerolinecolor: axis,
        zerolinewidth: 1.3,
        showline: false,
        ticks: "outside",
        tickcolor: grid,
        automargin: true,
    };
    const xaxis = { ...axisStyle, title: { text: "x" }, range: payload.xRange };
    const yaxis = { ...axisStyle, title: { text: "y" }, range: payload.yRange };
    const layout = {
        margin: { t: 35, r: 20, b: 60, l: 52 },
        paper_bgcolor: paper,
        plot_bgcolor: paper,
        font: { color: ink, family: "Segoe UI, sans-serif", size: 12 },
        colorway: workspaceColors,
        hovermode: "closest",
        showlegend: true,
        legend: { x: 0, y: 1.02, yanchor: "bottom", orientation: "h" },
        uirevision: payload.revision,
    };
    if (payload.view === "3d") {
        layout.margin = { t: 35, r: 0, b: 0, l: 0 };
        layout.scene = {
            xaxis,
            yaxis,
            zaxis: { ...axisStyle, title: { text: "z" } },
            aspectmode: "auto",
        };
    } else {
        layout.xaxis = { ...xaxis, constrain: "domain" };
        layout.yaxis = { ...yaxis, constrain: "domain", scaleanchor: "x" };
        layout.dragmode = "pan";
    }
    return layout;
}

function applyWorkspace() {
    const payload = pendingWorkspace;
    pendingWorkspace = null;
    const plot = document.getElementById("plot");
    const contourFallback = payload.view === "3d" && !hasWebGL();
    if (contourFallback) payload.view = "2d";
    const traces = payload.traces.flatMap((trace, i) => {
        if (contourFallback) {
            return trace.type === "surface" ? [{
                type: "contour", x: trace.x, y: trace.y, z: trace.z,
                name: trace.name, colorscale: trace.colorscale,
                contours: { coloring: "lines", showlabels: true },
            }] : [];
        }
        if (trace.type !== "scatter") return trace;
        return {
            ...trace,
            line: { width: 2.5, dash: workspaceDashes[i % 4], ...trace.line },
        };
    });
    const layout = workspaceLayout(payload);
    if (contourFallback) {
        layout.annotations = [{
            text: "Vista de contornos · WebGL no disponible",
            xref: "paper", yref: "paper", x: 0, y: 1.07,
            xanchor: "left", showarrow: false,
        }];
    }
    return Plotly.react(plot, traces, layout, {
        responsive: true,
        displaylogo: false,
        displayModeBar: true,
        scrollZoom: true,
        modeBarButtonsToRemove: ["toImage", "lasso2d", "select2d"],
    }).then(() => {
        workspaceMode = contourFallback ? "contour" : payload.view;
        workspaceReset = { x: payload.xRange.slice(), y: payload.yRange.slice() };
        workspaceReady = true;
        if (!plot.workspaceEvents) {
            plot.on("plotly_relayout", event => reportViewport(plot, event));
            plot.on("plotly_click", data => {
                const pt = data?.points?.[0];
                if (!pt || !pt.customdata || !pt.customdata.is_notable) return;
                const label = pt.customdata.label || pt.text || "Punto notable";
                const existing = plot.layout.annotations || [];
                const idx = existing.findIndex(
                    a => Math.abs(a.x - pt.x) < 1e-5 && Math.abs(a.y - pt.y) < 1e-5
                );
                let annotations;
                if (idx >= 0) {
                    annotations = existing.filter((_, i) => i !== idx);
                } else {
                    annotations = [...existing, {
                        x: pt.x, y: pt.y,
                        text: label,
                        showarrow: true,
                        arrowhead: 2,
                        arrowcolor: "#24332F",
                        bgcolor: "#FFFFFF",
                        bordercolor: "#CCD3C8",
                        borderwidth: 1,
                        borderpad: 4,
                        font: { family: "Segoe UI, sans-serif", size: 12, color: "#24332F" },
                    }];
                }
                Plotly.relayout(plot, { annotations });
            });
            plot.workspaceEvents = true;
        }
    });
}

function renderWorkspace(serialized) {
    pendingWorkspace = JSON.parse(serialized);
    if (workspaceRendering) return;
    workspaceRendering = Promise.resolve().then(async () => {
        try {
            while (pendingWorkspace) await applyWorkspace();
        } catch {
            workspaceReady = false;
            const plot = document.getElementById("plot");
            plot.textContent = "No se pudo dibujar la gráfica.";
            plot.setAttribute("aria-label", "No se pudo dibujar la gráfica.");
        } finally {
            workspaceRendering = null;
        }
    });
}

function reportViewport(plot, event) {
    if (!workspaceViewport || workspaceMode !== "2d" || workspaceRendering) return;
    if (!Object.keys(event).some(key => /^[xy]axis\.(range|autorange)/.test(key))) return;
    const { xaxis, yaxis } = plot._fullLayout;
    workspaceViewport.viewportChanged(...xaxis.range, ...yaxis.range);
}

function axisAfterKey(range, key, direction) {
    const width = range[1] - range[0];
    if (key === "+" || key === "=") return [range[0] + width / 8, range[1] - width / 8];
    if (key === "-") return [range[0] - width / 6, range[1] + width / 6];
    return range.map(value => value + direction * width / 10);
}

function orientCamera(scene, key) {
    const camera = scene.camera;
    if (key === "0") return { eye: { x: 1.25, y: 1.25, z: 1.25 } };
    const { x, y, z } = camera.eye;
    const radius = Math.hypot(x, y, z);
    if (radius === 0) return camera;
    const azimuth = Math.atan2(y, x) + (key === "ArrowLeft" ? -0.14 :
        key === "ArrowRight" ? 0.14 : 0);
    const elevation = Math.max(-1.48, Math.min(1.48, Math.asin(z / radius) +
        (key === "ArrowUp" ? 0.14 : key === "ArrowDown" ? -0.14 : 0)));
    const zoom = key === "-" ? 1.2 : key === "+" || key === "=" ? 0.84 : 1;
    return { ...camera, eye: {
        x: radius * zoom * Math.cos(elevation) * Math.cos(azimuth),
        y: radius * zoom * Math.cos(elevation) * Math.sin(azimuth),
        z: radius * zoom * Math.sin(elevation),
    } };
}

document.addEventListener("DOMContentLoaded", () => {
    const plot = document.getElementById("plot");
    plot.setAttribute("aria-description",
        "Usa las flechas para mover u orientar, más y menos para ampliar y cero para restablecer.");
    plot.addEventListener("keydown", event => {
        const key = event.key;
        if (!workspaceReady || event.target !== plot || event.ctrlKey ||
            event.altKey || event.metaKey ||
            !["+", "=", "-", "0", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(key)) {
            return;
        }
        event.preventDefault();
        const layout = plot._fullLayout;
        if (workspaceMode === "3d" && layout.scene) {
            Plotly.relayout(plot, { "scene.camera": orientCamera(layout.scene, key) });
        } else if (key === "0" && workspaceReset) {
            Plotly.relayout(plot, {
                "xaxis.range": workspaceReset.x,
                "yaxis.range": workspaceReset.y,
            });
        } else {
            Plotly.relayout(plot, {
                "xaxis.range": axisAfterKey(layout.xaxis.range, key,
                    key === "ArrowLeft" ? -1 : key === "ArrowRight" ? 1 : 0),
                "yaxis.range": axisAfterKey(layout.yaxis.range, key,
                    key === "ArrowDown" ? -1 : key === "ArrowUp" ? 1 : 0),
            });
        }
    });
    if (typeof QWebChannel === "function" && window.qt?.webChannelTransport) {
        new QWebChannel(window.qt.webChannelTransport, channel => {
            workspaceViewport = channel.objects.viewport;
        });
    }
});

async function startWorkspacePng() {
    window.workspacePng = "pending";
    try {
        if (workspaceRendering) await workspaceRendering;
        if (!workspaceReady) throw new Error("Gráfica no disponible");
        const plot = document.getElementById("plot");
        window.workspacePng = await Plotly.toImage(plot, { format: "png", scale: 2 });
    } catch {
        window.workspacePng = "error";
    }
}
