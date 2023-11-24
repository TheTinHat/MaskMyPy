import os

import geopandas as gpd
import pytest

from maskmypy import analysis, donut


def test_k_satisfaction(points, address):
    masked = donut(points, 100, 500)
    masked_k = analysis.k_anonymity(points, masked, address)
    k_sat_1 = analysis.k_satisfaction(masked_k, 1)
    k_sat_50 = analysis.k_satisfaction(masked_k, 50)
    k_sat_999 = analysis.k_satisfaction(masked_k, 999)
    assert k_sat_1 > 0.9
    assert 0.1 < k_sat_50 < 0.9
    assert k_sat_999 < 0.1


def test_k_summary(points, address):
    masked = donut(points, 100, 500)
    masked_k = analysis.k_anonymity(points, masked, address)
    k_sum = analysis.summarize_k(masked_k)
    assert k_sum["k_min"] < k_sum["k_mean"] < k_sum["k_max"]


def test_displacement(points):
    masked_points = points.copy()
    masked_points["geometry"] = masked_points.geometry.translate(50, 0, 0)
    displacement = analysis.summarize_displacement(analysis.displacement(points, masked_points))
    assert displacement["displacement_min"] == 50
    assert displacement["displacement_max"] == 50
    assert displacement["displacement_med"] == 50
    assert displacement["displacement_mean"] == 50


def test_estimate_k_address(points, address):
    pass


def test_estimate_k_polygon():
    pass


def test_disaggregate():
    pass


def test_mean_center_drift(points):
    masked_points = points.copy(deep=True)
    masked_points["geometry"] = masked_points.geometry.translate(50, 0, 0)
    drift = analysis.central_drift(points, masked_points)
    assert drift == 50


def test_ripleys_k(points, tmpdir):
    masked = donut(points, 100, 500)
    kresult_sensitive = analysis.ripleys_k(points)
    kresult_masked = analysis.ripleys_k(masked)

    analysis.graph_ripleyresult(kresult_sensitive).savefig("SensitiveResult.png")
    assert os.path.exists("SensitiveResult.png")
    analysis.graph_ripleyresults(kresult_sensitive, kresult_masked, subtitle="Test Data").savefig(
        "ComparisonResult.png"
    )
    assert os.path.exists("ComparisonResult.png")


def test_ripleys_rmse(points):
    masked = donut(points, 1, 5)
    kresult_sensitive = analysis.ripleys_k(points)
    kresult_masked = analysis.ripleys_k(masked)
    rmse_1 = analysis.ripley_rmse(kresult_sensitive, kresult_masked)

    masked = donut(points, 1000, 5000)
    kresult_sensitive = analysis.ripleys_k(points)
    kresult_masked = analysis.ripleys_k(masked)
    rmse_2 = analysis.ripley_rmse(kresult_sensitive, kresult_masked)

    assert rmse_1 < rmse_2


def test_nearest_neighbor_stats(points):
    masked_points = points.copy()
    masked_points["geometry"] = masked_points.geometry.translate(50, 0, 0)
    nnd = analysis.nnd_delta(points, masked_points)
    assert nnd["nnd_min_delta"] == 0
    assert nnd["nnd_max_delta"] == 0
    assert nnd["nnd_mean_delta"] == 0

    masked_points = donut(points, 100, 500)
    nnd = analysis.nnd_delta(points, masked_points)
    assert isinstance(nnd["nnd_min_delta"], float)
    assert isinstance(nnd["nnd_max_delta"], float)
    assert isinstance(nnd["nnd_mean_delta"], float)


def test_map_displacement(points, tmpdir, address):
    masked_points = points.copy()
    masked_points["geometry"] = masked_points.geometry.translate(500, 0, 0)
    analysis.map_displacement(
        points, masked_points, filename="MapDisplacement.png", context_gdf=address
    )
    assert os.path.exists("MapDisplacement.png")
