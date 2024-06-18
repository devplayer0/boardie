{
  description = "Linux soundboard";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    devshell.url = "github:numtide/devshell";
    poetry2nix.url = "github:nix-community/poetry2nix";
  };

  outputs = { self, nixpkgs, flake-utils, devshell, poetry2nix }:
  let
    inherit (nixpkgs.lib) composeManyExtensions;
    inherit (flake-utils.lib) eachDefaultSystem;

    pyOverrides = pkgs: pkgs.poetry2nix.overrides.withDefaults (self: super: {
      pyaudio = super.pyaudio.overridePythonAttrs (old: {
        buildInputs = old.buildInputs ++ [ pkgs.portaudio ];
      });
      evdev = super.evdev.overridePythonAttrs (old: {
        patchPhase = ''
          substituteInPlace setup.py \
            --replace-fail /usr/include ${pkgs.linuxHeaders}/include
        '';
      });
    });
  in
  {
    overlays = rec {
      boardie = composeManyExtensions [
        poetry2nix.overlays.default
        (final: prev: {
          boardie = prev.poetry2nix.mkPoetryApplication {
            projectDir = ./.;
            overrides = pyOverrides prev;

            makeWrapperArgs = [
              ''--prefix PATH ':' "${prev.ffmpeg}/bin"''
            ];
            meta.mainProgram = "boardie";
          };
        })
      ];
      default = boardie;
    };
  } // (eachDefaultSystem (system:
    let
      pkgs = import nixpkgs {
        inherit system;
        overlays = [
          devshell.overlays.default
          self.overlays.default
        ];
      };
    in
    {
      devShells.default = pkgs.devshell.mkShell {
        packages = with pkgs; [
          ffmpeg

          poetry
          (pkgs.poetry2nix.mkPoetryEnv {
            projectDir = ./.;
            overrides = pyOverrides pkgs;
          })
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
    }));
}
