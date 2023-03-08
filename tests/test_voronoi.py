import os
import shutil

import geopandas as gpd
import pytest

from maskmypy import Atlas, Candidate, Voronoi

from .fixtures import atlas, points, tmpdir, container


def test_voronoi(atlas):
    v = Voronoi(atlas.sensitive)
    mdf, parameters = v.run()

    mdf.to_file("voronoi.gpkg", layer="points", driver="GPKG")
    v.voronoi.to_file("voronoi.gpkg", layer="polygon", driver="GPKG")
    atlas.sensitive.to_file("voronoi.gpkg", layer="original", driver="GPKG")
