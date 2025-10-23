import os

import geopandas as gpd
from numpy import floor
from shapely.geometry import Point, Polygon

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


def test_estimate_k_address():
    addr_points = {
        "geometry": [
            Point(0, 0),
            Point(1, 0),
            Point(2, 0),
            Point(3, 0),
            Point(4, 0),
            Point(5, 0),
            Point(7, 0),
        ]
    }
    sens_gdf = gpd.GeoDataFrame({"geometry": [Point(0, 0)]}, crs="EPSG:32630")
    addr_gdf = gpd.GeoDataFrame(addr_points, crs="EPSG:32630")

    mask1_gdf = gpd.GeoDataFrame({"geometry": [Point(1, 0)]}, crs="EPSG:32630")
    results1 = analysis._calculate_k(
        sensitive_gdf=sens_gdf, candidate_gdf=mask1_gdf, address_gdf=addr_gdf
    )
    assert results1.loc[0, "k_anonymity"] == 3

    mask2_gdf = gpd.GeoDataFrame({"geometry": [Point(2, 0)]}, crs="EPSG:32630")
    results2 = analysis._calculate_k(
        sensitive_gdf=sens_gdf, candidate_gdf=mask2_gdf, address_gdf=addr_gdf
    )
    assert results2.loc[0, "k_anonymity"] == 5

    mask3_gdf = gpd.GeoDataFrame({"geometry": [Point(3, 0)]}, crs="EPSG:32630")
    results3 = analysis._calculate_k(
        sensitive_gdf=sens_gdf, candidate_gdf=mask3_gdf, address_gdf=addr_gdf
    )
    assert results3.loc[0, "k_anonymity"] == 6

    mask4_gdf = gpd.GeoDataFrame({"geometry": [Point(-1, 0)]}, crs="EPSG:32630")
    results4 = analysis._calculate_k(
        sensitive_gdf=sens_gdf, candidate_gdf=mask4_gdf, address_gdf=addr_gdf
    )
    assert results4.loc[0, "k_anonymity"] == 2

    sens_gdf = gpd.GeoDataFrame({"geometry": [Point(-7, 0)]}, crs="EPSG:32630")
    mask5_gdf = gpd.GeoDataFrame({"geometry": [Point(0, 0)]}, crs="EPSG:32630")
    results5 = analysis._calculate_k(
        sensitive_gdf=sens_gdf, candidate_gdf=mask5_gdf, address_gdf=addr_gdf
    )
    assert results5.loc[0, "k_anonymity"] == 8

def test_estimate_k_polygon():
    poly1 = Polygon([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)])
    poly10 = Polygon([(0, 0), (1, 0), (1, -1), (-1, 0), (0, 0)])
    poly100 = Polygon([(0, 0), (0, -1), (-1, -1), (-1, 0), (0, 0)])
    poly1000 = Polygon([(0, 0), (-1, 0), (-1, 1), (0, 1), (0, 0)])
    census_poly = {
        "pop": [1, 10, 100, 1000],
        "geometry": [poly1, poly10, poly100, poly1000],
    }
    pop_gdf = gpd.GeoDataFrame(census_poly, crs="EPSG:32630")

    # uncertainty area includes entirety of all four areas, thus k equals sum of all population
    # across all four, minus one
    sens1_gdf = gpd.GeoDataFrame({"geometry": [Point(3, 0)]}, crs="EPSG:32630")
    mask1_gdf = gpd.GeoDataFrame({"geometry": [Point(0, 0)]}, crs="EPSG:32630")
    results1 = analysis._estimate_k(
        sensitive_gdf=sens1_gdf, candidate_gdf=mask1_gdf, population_gdf=pop_gdf
    )
    assert results1.loc[0, "k_anonymity"] == sum(census_poly["pop"])

    # uncertainty area only covers part of the 1000 pop area. As pop = 1000, and
    # coverage is bottom right quadrant of a buffer centered on top left corner
    # of top left quadrant, k should roughly equal ((population * pi * radius)/4)
    sens2_gdf = gpd.GeoDataFrame({"geometry": [Point(0, 1)]}, crs="EPSG:32630")
    mask2_gdf = gpd.GeoDataFrame({"geometry": [Point(-1, 1)]}, crs="EPSG:32630")
    expected_k = ((mask2_gdf.buffer(mask2_gdf.distance(sens2_gdf)).area * 1000) / 4).apply(floor)

    results2 = analysis._estimate_k(
        sensitive_gdf=sens2_gdf, candidate_gdf=mask2_gdf, population_gdf=pop_gdf
    )
    assert results2.loc[0, "k_anonymity"] == expected_k[0]

    # Uncertainty area is a circle from the center at 0,0, with only partial
    # but equal coverage of each quadrant.
    sens3_gdf = gpd.GeoDataFrame({"geometry": [Point(1, 0)]}, crs="EPSG:32630")
    mask3_gdf = gpd.GeoDataFrame({"geometry": [Point(0, 0)]}, crs="EPSG:32630")
    results3 = analysis._estimate_k(
        sensitive_gdf=sens3_gdf, candidate_gdf=mask3_gdf, population_gdf=pop_gdf
    )

    area = mask3_gdf.buffer(mask3_gdf.distance(sens3_gdf)).area / 4
    expected_k = ((1 * area) + (10 * area) + (100 * area) + (1000 * area)).apply(floor)
    assert results3.loc[0, "k_anonymity"] == expected_k[0]


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


def test_evaluate(points, address):
    masked_points = points.copy(deep=True)
    masked_points["geometry"] = masked_points.geometry.translate(50, 0, 0)
    stats = analysis.evaluate(points, masked_points, address, skip_slow=False)

    assert stats["central_drift"] == 50
    assert stats["displacement_min"] == 50
    assert stats["k_max"] > stats["k_min"]
    assert stats["k_satisfaction_50"] == 0.0
    assert stats["nnd_min_delta"] == 0.0
    assert stats["ripley_rmse"] == 0.0
