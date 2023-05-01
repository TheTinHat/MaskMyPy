import geopandas as gpd
import pytest

from maskmypy import analysis


@pytest.fixture
def container():
    return gpd.read_file("tests/boundary.geojson")


def test_k_satisfaction():
    pass


def test_displacement():
    pass


def test_estimate_k_address(atlas):
    atlas.donut(50, 500)
    k = analysis.estimate_k(atlas.sensitive, atlas.get().mdf, atlas.population)
    analysis.summarize_k(k)


def test_estimate_k_polygon():
    pass


def test_disaggregate():
    pass


def test_mean_center_drift(points):
    masked_points = points.copy(deep=True)
    masked_points["geometry"] = masked_points.geometry.translate(50, 0, 0)
    drift = analysis.drift(points, masked_points)
    assert drift == 50


def test_ripleys_k(atlas):
    atlas.donut(10, 100)
    distance_steps = 10
    max_dist = analysis.ripleys_rot(atlas.sensitive)
    min_dist = max_dist / distance_steps
    kresult_sensitive = analysis.ripleys_k(
        atlas.sensitive, max_dist=max_dist, min_dist=min_dist, steps=distance_steps
    )
    kresult_candidate = analysis.ripleys_k(
        atlas.get(0).mdf, max_dist=max_dist, min_dist=min_dist, steps=distance_steps
    )
    analysis.graph_ripleyresult(kresult_sensitive)
    analysis.graph_ripleyresults(
        kresult_candidate, kresult_sensitive, subtitle=atlas.candidates[0].cid
    )


def test_nearest_neighbor_stats():
    pass


def test_compare_candidates():
    pass
