import os
import shutil

import geopandas as gpd
import pytest

from maskmypy import Atlas, Candidate, donut


@pytest.fixture
def points():
    return gpd.read_file("tests/points.geojson")


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


def test_random_seed(points):
    candidate = donut(points, 10, 100)
    assert isinstance(candidate.parameters["seed"], int)

    candidate = donut(points, 10, 100, seed=123456)
    assert candidate.parameters["seed"] == 123456


def test_container(points, container):
    candidate = donut(points, 0.0005, 0.005, container=container)
