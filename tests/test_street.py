import os
import shutil

import geopandas as gpd
import pytest
from pandas.testing import assert_frame_equal

from maskmypy import Atlas, Candidate, Street
from .fixtures import points, tmpdir, atlas


@pytest.fixture
def points():
    return gpd.read_file("tests/points.geojson")
    # return gpd.read_file("2019_StreetMasking/kam_addresses_pop.shp")[0:1000]


@pytest.fixture
def masked_points(points):
    points.geometry = points.geometry.translate(0.001)
    return points


@pytest.fixture()
def tmpdir():
    os.makedirs("./tmp/", exist_ok=True)
    yield
    shutil.rmtree("./tmp")


def test_random_seed(points):
    points = points[0:10]
    candidate_1 = Street(points, 18, 20, seed=12345).run()
    candidate_2 = Street(points, 18, 20, seed=12345).run()
    candidate_3 = Street(points, 18, 20, seed=98765).run()

    assert_frame_equal(candidate_1, candidate_2)

    with pytest.raises(AssertionError):
        assert_frame_equal(candidate_1, candidate_3)


# def test_street(points):
#     candidate_0 = Street(points, 15, 20, seed=12345).run()
