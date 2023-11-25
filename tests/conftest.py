import os
import shutil

import geopandas as gpd
import pytest


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", default=False, help="run slow tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


@pytest.fixture()
def tmpdir():
    os.makedirs("./tmp/", exist_ok=True)
    os.chdir("./tmp")
    yield
    os.chdir("../")
    shutil.rmtree("./tmp")


POINTS = gpd.read_file("tests/data/points.geojson").to_crs(epsg=26910)
ADDRESS = gpd.read_file("tests/data/addresses.geojson").to_crs(epsg=26910)
CONTAINER = gpd.read_file("tests/data/boundary.geojson").to_crs(epsg=26910)


@pytest.fixture
def points():
    return POINTS.copy()


@pytest.fixture
def points_small():
    points = POINTS.copy()
    return points.clip(points.iloc[0].geometry.buffer(1500))


@pytest.fixture
def address():
    return ADDRESS.copy()


@pytest.fixture
def container():
    return CONTAINER.copy()


# @pytest.fixture
# def atlas(points, addresses, tmpdir):
#     return Atlas(name="test_atlas", directory="./tmp/", input=points, population=addresses)


# @pytest.fixture
# def atlas_contained(points, container, tmpdir):
#     return Atlas(name="test_atlas", container=container, directory="./tmp/", input=points)
