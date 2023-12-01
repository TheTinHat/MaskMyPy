import pytest
from shapely.geometry import Point

from maskmypy import analysis, locationswap, tools


def test_locationswap_displacement(points, address):
    for i in range(10):
        low = 100
        high = 200
        masked = locationswap(points, low=low, high=high, address=address)

        masked = analysis.displacement(points, masked)

        assert round(min(masked.loc[:, "_distance"])) >= low
        assert round(max(masked.loc[:, "_distance"])) <= high


def test_locationswap_does_not_affect_input(points, address):
    initial_checksum = tools.checksum(points)
    locationswap(points, low=100, high=500, address=address)
    assert tools.checksum(points) == initial_checksum


def test_locationswap_seed(points, address):
    checksum_1 = tools.checksum(
        locationswap(points, low=100, high=500, address=address, seed=12345)
    )
    checksum_2 = tools.checksum(
        locationswap(points, low=100, high=500, address=address, seed=12345)
    )
    checksum_3 = tools.checksum(
        locationswap(points, low=100, high=500, address=address, seed=98765)
    )
    assert checksum_1 == checksum_2 != checksum_3


def test_locationswap_intersects_addresses(points, address):
    masked = locationswap(points, low=100, high=500, address=address)
    address_disolved = address.dissolve()

    for index, row in masked.iterrows():
        assert row.geometry in address.loc[:, "geometry"]
        assert row.geometry.distance(address_disolved.geometry)[0] == 0


def test_locationswap_validation(points, address):
    with pytest.raises(ValueError):
        address_crsmismatch = address.to_crs(4326)
        locationswap(points, 100, 500, address=address_crsmismatch)

    with pytest.raises(ValueError):
        locationswap(points, 100, 10, address=address)

    with pytest.raises(ValueError):
        address_as_polygons = address.copy()
        address_as_polygons.geometry = address_as_polygons.geometry.buffer(10)
        locationswap(points, 10, 100, address_as_polygons)


def test_locationswap_sets_impossible_points_as_null(points, address):
    masked = locationswap(points, low=1, high=2, address=address)
    assert all(masked.geometry == Point(0, 0))
