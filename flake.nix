{
  description = "marimo-mesh-viewer — minimal dev environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, utils }:
    utils.lib.eachSystem [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" ] (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };

        python = pkgs.python312;

        pythonEnv = python.withPackages (ps: with ps; [
          marimo
          anywidget
          traitlets
          numpy
        ]);
      in rec {
        packages = {
          inherit pythonEnv;
          default = pythonEnv;
        };

        apps.default = {
          type = "app";
          program = "${pythonEnv}/bin/marimo";
        };

        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
            pkgs.nodejs_20
            pkgs.yarn
          ];

          shellHook = ''
            unset NODE_OPTIONS
            export PYTHONPATH="$PWD"
            echo "marimo-mesh-viewer minimal dev environment"
            echo ""
            echo "  Tooling"
            echo "    python: ${python.pythonVersion}"
            echo "    node: $(node --version)"
            echo "    yarn: $(yarn --version)"
            echo "    pythonpath: $PYTHONPATH"
            echo ""
            echo "  Quick start"
            echo "    marimo run notebooks/demo.py"
            echo "    yarn --cwd js build"
          '';
        };
      }
    );
}