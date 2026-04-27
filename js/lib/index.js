require("../style/index.css");

// eslint-disable-next-line no-undef
const widgetExports = require("./widget.js");

function mountMeshViewer(element, state) {
  if (!element) {
    throw new Error("mountMeshViewer requires a target element");
  }

  const model = new widgetExports.MeshViewerModel(state || {});
  const view = new widgetExports.MeshViewerView({ model, el: element });
  view.render();
  return { model, view };
}

// eslint-disable-next-line no-undef
module.exports = { ...widgetExports, mountMeshViewer };

// eslint-disable-next-line no-undef
module.exports["version"] = require("../package.json").version;
