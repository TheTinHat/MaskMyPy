import os
import shutil

import geopandas as gpd
import pytest

from maskmypy import Atlas, Candidate, Donut, analyst


@pytest.fixture
def points():
    return gpd.read_file("tests/points.geojson").to_crs(epsg=26910)


@pytest.fixture
def masked_points(points):
    points.geometry = points.geometry.translate(0.001)
    return points


@pytest.fixture
def container(points):
    return gpd.read_file("tests/boundary.geojson")


@pytest.fixture()
def tmpdir():
    os.makedirs("./tmp/", exist_ok=True)
    yield
    shutil.rmtree("./tmp")


def test_mean_center_drift(points):
    masked_points = points.copy(deep=True)
    masked_points["geometry"] = masked_points.geometry.translate(50, 0, 0)
    drift = analyst.mean_center_drift(points, masked_points)
    assert drift == 50


def test_k_satisfaction(points):
    pass
