{
  description = "Minimal MCP for rocq";

  inputs = {
    # PR #573940 provides memprof-limits 0.3.0 with OCaml 5 support.
    nixpkgs.url = "github:NixOS/nixpkgs/15aabc6e8d56a08f7d2f8dcc94c9b0a251aa1e45";

    flake-parts.url = "github:hercules-ci/flake-parts";
    flake-parts.inputs.nixpkgs-lib.follows = "nixpkgs";
  };

  outputs =
    inputs@{ self, flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      # Nixpkgs 26.11 dropped x86_64-darwin.
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      perSystem =
        { pkgs, self', ... }:
        let
          mkPackage = pkgs.lib.makeOverridable (
            { rocq }:
            let
              # Derive dependencies from Rocq so the server and plugins share its compiler.
              inherit (rocq) ocamlPackages;

              stdlib = (pkgs.mkRocqPackages rocq).stdlib;

              # Pin the embedded runtime even when the shell inherits another Rocq environment.
              runtimeEnvironment = {
                ROCQLIB = "${rocq}/lib/coq";
                ROCQRUNTIMELIB = "${rocq}/lib/rocq-runtime";
              };

              server = ocamlPackages.buildDunePackage {
                pname = "rocq-mcp-evolve";
                version = "0-unstable";
                src = self;

                # Like VsRocq, use Rocq as both a build tool and a linked library.
                nativeBuildInputs = [
                  rocq
                  pkgs.makeWrapper
                ];

                buildInputs = [
                  rocq
                  stdlib
                  ocamlPackages.findlib
                  ocamlPackages.yojson
                  ocamlPackages.memprof-limits
                ];

                # Pin the core runtime while retaining the caller's project libraries and tools.
                postFixup = ''
                  for executable in "$out"/bin/*; do
                    wrapProgram "$executable" \
                      --set ROCQLIB "${rocq}/lib/coq" \
                      --set ROCQRUNTIMELIB "${rocq}/lib/rocq-runtime" \
                      --prefix ROCQPATH : "$ROCQPATH" \
                      --prefix OCAMLPATH : "$OCAMLPATH" \
                      --suffix PATH : "${
                        pkgs.lib.makeBinPath [
                          rocq
                          ocamlPackages.findlib
                        ]
                      }"
                  done
                '';

                passthru = {
                  inherit rocq stdlib ocamlPackages;

                  # Attaching the shell to the package makes it follow downstream Rocq overrides.
                  devShell = pkgs.mkShell {
                    # The inherited dependencies also supply the Rocq and OCaml path setup hooks.
                    inputsFrom = [ server ];
                    env = runtimeEnvironment;
                  };
                };

                meta = {
                  description = "An MCP server for the Rocq proof assistant";
                  homepage = "https://github.com/LLM4Rocq/rocq-mcp-evolve";
                  license = pkgs.lib.licenses.asl20;
                  mainProgram = "rocq-mcp-evolve";
                };
              };
            in
            server
          );

          # Selecting Rocq here determines the compiler and standard library for every output.
          package = mkPackage {
            rocq = pkgs.rocq-core_9_2.override {
              customOCamlPackages = pkgs.ocaml-ng.ocamlPackages_5_3;
            };
          };
        in
        {
          packages = {
            default = package;
            rocq-mcp-evolve = package;
          };

          apps.default = {
            type = "app";
            program = "${package}/bin/rocq-mcp-evolve";
            meta.description = package.meta.description;
          };

          checks.default = self'.packages.default;

          devShells.default = self'.packages.default.devShell;

          formatter = pkgs.nixfmt;
        };
    };
}
