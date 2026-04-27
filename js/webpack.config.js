const TerserPlugin = require("terser-webpack-plugin");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const path = require("path");

module.exports = {
  entry: "./lib/index.js",
  output: {
    filename: "index.js",
    path: path.resolve(__dirname, "..", "marimo_mesh_viewer", "static"),
    publicPath: "auto",
    library: {
      name: "MarimoMeshViewer",
      type: "window",
    },
  },
  devtool: false,
  resolve: {
    extensions: [".js", ".json"],
  },
  module: {
    rules: [
      { test: /\.css$/, use: [MiniCssExtractPlugin.loader, "css-loader"] },
    ],
  },
  optimization: {
    minimize: false,
    minimizer: [
      new TerserPlugin({
        parallel: true,
        terserOptions: {
          compress: { defaults: false },
          mangle: false,
        },
      }),
    ],
  },
  plugins: [new MiniCssExtractPlugin({ filename: "index.css" })],
};
