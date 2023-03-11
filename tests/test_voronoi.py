import os
import shutil

import geopandas as gpd
import pytest

from maskmypy import Atlas, Candidate, Voronoi

from .fixtures import atlas, points, tmpdir, container


def test_voronoi(atlas):
    mdf = Voronoi(atlas.sensitive, street=False).run()
