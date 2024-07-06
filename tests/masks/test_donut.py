from statistics import mean

import pytest
from geopandas import GeoDataFrame

from maskmypy import analysis, donut, tools


@pytest.mark.parametrize("distribution", ["uniform", "gaussian", "areal"])
def test_donut_displacement(points, distribution):
    for i in range(50):
        low = 100
        high = 200
        masked = donut(points, low=low, high=high, distribution=distribution)

        masked = analysis.displacement(points, masked)

        if distribution == "gaussian":
            mid = (high - low) / 2 + low
            assert (mid * 0.9) < mean(masked.loc[:, "_distance"]) < (mid * 1.1)
            low = low * 0.5
            high = high * 1.5

        assert min(masked.loc[:, "_distance"]) >= low
        assert max(masked.loc[:, "_distance"]) <= high


def test_donut_does_not_affect_input(points):
    initial_checksum = tools.checksum(points)
    donut(points, low=100, high=500)
    assert tools.checksum(points) == initial_checksum


def test_donut_seed(points):
    checksum_1 = tools.checksum(donut(points, low=100, high=500, seed=12345))
    checksum_2 = tools.checksum(donut(points, low=100, high=500, seed=12345))
    checksum_3 = tools.checksum(donut(points, low=100, high=500, seed=98765))
    assert checksum_1 == checksum_2 != checksum_3


def test_donut_containment(points, container):
    buffers = GeoDataFrame(geometry=points.buffer(50))
    masked = donut(points, 25, 500, container=buffers, distribution="areal")
    masked = analysis.displacement(points, masked)
    assert all(buffers.intersects(points))
    assert all(buffers.intersects(masked))
    assert max(masked["_distance"]) <= 100


def test_donut_validation(points, container):
    with pytest.raises(ValueError):
        container_crsmismatch = container.to_crs(4326)
        donut(points, 10, 100, container=container_crsmismatch)

    with pytest.raises(ValueError):
        donut(points, 100, 10)

    with pytest.raises(ValueError):
        buffers = points.buffer(100)  # This does not a GeoDataFrame
        donut(points, 10, 100, container=buffers)

    with pytest.raises(ValueError):
        container_as_points = container.copy()
        container_as_points.geometry = container.centroid
        donut(points, 10, 100, container=container_as_points)
