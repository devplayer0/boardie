{
  description = "Linux soundboard";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    devshell.url = "github:numtide/devshell";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = {
    self, nixpkgs,
    flake-utils, devshell,
    pyproject-nix,
    ...
  }:
  let
    inherit (flake-utils.lib) eachDefaultSystem;

    project = pyproject-nix.lib.project.loadPyproject {
      projectRoot = ./.;
    };
  in
  {
    overlays = rec {
      boardie = (final: prev:
        let
          python = prev.python3;
          attrs = project.renderers.buildPythonPackage { inherit python; };
        in
        {
          boardie = python.pkgs.buildPythonPackage attrs;
        }
      );
      default = boardie;
    };
    inherit project;
  } // (eachDefaultSystem (system:
    let
      pkgs = import nixpkgs {
        inherit system;
        overlays = [
          devshell.overlays.default
          self.overlays.default
        ];
      };

      python' = pkgs.python3;
      python = python'.withPackages (project.renderers.withPackages { python = python'; });
    in
    {
      devShells.default = pkgs.devshell.mkShell {
        packages = with pkgs; [
          ffmpeg

          python
        ];

        commands = [
          {
            name = "boardie";
            command = "${python}/bin/python -m boardie";
          }
        ];
      };

      packages = rec {
        inherit (pkgs) boardie;
        default = boardie;
      };

      apps = rec {
        inherit (pkgs) boardie;
        default = boardie;
      };

      checks.versionConstraints = assert project.validators.validateVersionConstraints { python = python'; } == { }; pkgs.boardie;
    }));
}
