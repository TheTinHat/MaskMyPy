import os
import shutil

import geopandas as gpd
import pytest

from maskmypy import Atlas, Candidate, Donut


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
    candidate = Donut(points, 10, 100).run()
    assert isinstance(candidate.parameters["seed"], int)

    candidate = Donut(points, 10, 100, seed=123456).run()
    assert candidate.parameters["seed"] == 123456


def test_container(points, container):
    candidate = Donut(points, 0.01, 0.05, container=container).run()
