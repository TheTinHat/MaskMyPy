from statistics import mean

import osmnx
import pytest

from maskmypy import analysis, street, tools


def test_street_displacement(points_small):
    masked = street(points_small, low=1, high=5, max_length=1000)
    masked = analysis.displacement(points_small, masked)

    assert min(masked.loc[:, "_distance"]) >= 10
    assert max(masked.loc[:, "_distance"]) <= 5 * 1000


def test_street_does_not_affect_input(points_small):
    initial_checksum = tools.checksum(points_small)
    street(points_small, low=1, high=5)
    assert tools.checksum(points_small) == initial_checksum


def test_street_seed(points_small):
    checksum_1 = tools.checksum(street(points_small, low=1, high=5, seed=12345))
    checksum_2 = tools.checksum(street(points_small, low=1, high=5, seed=12345))
    checksum_3 = tools.checksum(street(points_small, low=1, high=5, seed=98765))
    assert checksum_1 == checksum_2 != checksum_3


def test_street_validation(points_small):
    with pytest.raises(ValueError):
        street(points_small, low=5, high=1)


def test_street_returns_correct_crs(points_small):
    initial_crs = points_small.crs
    masked = street(points_small, 1, 5)
    assert masked.crs == initial_crs


def test_street_intersects_osm(points_small):
    points_small_4326 = points_small.to_crs(epsg=4326)
    masked = street(points_small, 1, 5)
    masked_4326 = masked.to_crs(epsg=4326)

    for index, row in masked_4326.iterrows():
        # Test original points do not intersect OSM
        with pytest.raises(osmnx._errors.InsufficientResponseError):
            unmasked_point = points_small_4326.loc[index, "geometry"]
            osmnx.features.features_from_point(
                (unmasked_point.y, unmasked_point.x), tags={"highway": True}, dist=1
            )

        # Test masked points intersect OSM
        osmnx.features.features_from_point(
            (row.geometry.y, row.geometry.x), tags={"highway": True}, dist=1
        )  # This will error if it cannot find anything within the distance
        assert points_small.loc[index, "geometry"] != masked.loc[index, "geometry"]


def test_street_higher_values_displace_further(points_small):
    for i in range(5):
        masked_small = analysis.displacement(street(points_small, 1, 3), points_small)
        masked_large = analysis.displacement(street(points_small, 4, 5), points_small)
        assert mean(masked_small.loc[:, "_distance"]) < mean(masked_large.loc[:, "_distance"])
