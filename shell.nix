{ pkgs ? import <nixpkgs> { }
}:

pkgs.mkShell {

  buildInputs = [
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.python311Packages.virtualenv
  ];
  LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc ];
  shellHook = ''
    source env/bin/activate
  '';
}
