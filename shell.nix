{ pkgs ? import <nixpkgs> { }
}:

pkgs.mkShell {

  buildInputs = [
    pkgs.python311
  ];
  LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc ];
}
