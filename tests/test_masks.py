import os
import shutil

import geopandas as gpd
import pytest

from maskmypy import Atlas, Candidate, masks


@pytest.fixture
def points():
    return gpd.read_file("tests/points.geojson")


@pytest.fixture
def masked_points(points):
    points.geometry = points.geometry.translate(0.001)
    return points


@pytest.fixture()
def tmpdir():
    os.makedirs("./tmp/", exist_ok=True)
    yield
    shutil.rmtree("./tmp")
