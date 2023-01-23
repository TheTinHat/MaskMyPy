import os
import shutil

import geopandas as gpd
import pytest

from maskmypy import Atlas, Candidate, Street
from pandas.testing import assert_frame_equal


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
    #points = points[0:5]
    candidate_1 = Street(points, 18, 20, seed=12345).run()
    candidate_2 = Street(points, 18, 20, seed=12345).run()
    candidate_3 = Street(points, 18, 20, seed=98765).run()

    assert_frame_equal(candidate_1.gdf, candidate_2.gdf)

    with pytest.raises(AssertionError):
        assert_frame_equal(candidate_1.gdf, candidate_3.gdf)


# def test_street(points):
#     candidate_0 = Street(points, 15, 20, seed=12345).run()
