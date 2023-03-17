import os
import shutil

import geopandas as gpd
import pytest

from maskmypy import Atlas, Candidate, Donut, analyst
from .fixtures import points, tmpdir, atlas


@pytest.fixture
def container(points):
    return gpd.read_file("tests/boundary.geojson")


def test_k_satisfaction(points):
    pass


def test_displacement(points):
    pass


def test_estimate_k_address():
    pass


def test_estimate_k_polygon():
    pass


def test_disaggregate():
    pass


def test_mean_center_drift(points):
    masked_points = points.copy(deep=True)
    masked_points["geometry"] = masked_points.geometry.translate(50, 0, 0)
    drift = analyst.central_drift(points, masked_points)
    assert drift == 50


def test_k_satisfaction():
    pass


def test_ripleys_k(atlas):
    atlas.donut(10, 100)
    distance_steps = 10
    max_dist = analyst.ripleys_rot(atlas.sensitive)
    min_dist = max_dist / distance_steps
    kresult_sensitive = analyst.ripleys_k(
        atlas.sensitive, max_dist=max_dist, min_dist=min_dist, steps=distance_steps
    )
    kresult_candidate = analyst.ripleys_k(
        atlas.candidates[0].mdf, max_dist=max_dist, min_dist=min_dist, steps=distance_steps
    )
    analyst.graph_ripleyresult(kresult_sensitive)
    analyst.graph_ripleyresults(
        kresult_candidate, subtitle=atlas.candidates[0].cid, s_result=kresult_sensitive
    )
    atlas.donut(50, 500)
    atlas.benchmark()


def test_nearest_neighbor_stats():
    pass


def test_compare_candidates():
    pass
