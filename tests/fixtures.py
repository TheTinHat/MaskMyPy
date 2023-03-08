import geopandas as gpd
import pytest
from maskmypy import Atlas
import os
import shutil


@pytest.fixture
def points():
    return gpd.read_file("tests/points.geojson").to_crs(epsg=26910)


@pytest.fixture()
def tmpdir():
    os.makedirs("./tmp/", exist_ok=True)
    yield
    shutil.rmtree("./tmp")


@pytest.fixture
def container():
    return gpd.read_file("tests/boundary.geojson").to_crs(epsg=26910)


@pytest.fixture
def atlas(points, tmpdir):
    return Atlas(name="test_atlas", directory="./tmp/", sensitive=points)


@pytest.fixture
def atlas_contained(points, container, tmpdir):
    return Atlas(name="test_atlas", container=container, directory="./tmp/", sensitive=points)
