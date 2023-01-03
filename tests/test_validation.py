import os
import shutil

import geopandas as gpd
import pytest
from shapely.geometry import Point, MultiPoint
from maskmypy import Atlas, Candidate, validation


@pytest.fixture
def points():
    return gpd.read_file("tests/points.geojson")


@pytest.fixture
def masked_points(points):
    points = points.copy(deep=True)
    points.geometry = points.geometry.translate(0.001)
    return points


@pytest.fixture()
def tmpdir():
    os.makedirs("./tmp/", exist_ok=True)
    yield
    shutil.rmtree("./tmp")


def test_validate_input_geom(points):
    kwargs = {}
    kwargs["sensitive_gdf"] = points
    validation.validate_input(**kwargs)
    points.loc[0, "geometry"] = points.loc[0].geometry.buffer(10)
    with pytest.raises(AssertionError):
        validation.validate_input(**kwargs)


def test_validate_input_multiple_args(points):
    points.loc[0, "geometry"] = MultiPoint([(-123.06397, 49.24249), (-123.08397, 49.24249)])
    with pytest.raises(AssertionError):
        validation.assert_geom_type(points, "Point")
    validation.assert_geom_type(points, "Point", "MultiPoint")
