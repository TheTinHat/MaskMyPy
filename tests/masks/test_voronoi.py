from maskmypy import analysis, tools, voronoi


def test_voronoi_displacement(points):
    masked = voronoi(points)
    masked = analysis.displacement(points, masked)

    assert min(masked.loc[:, "_distance"]) > 0


def test_donut_does_not_affect_input(points):
    initial_checksum = tools.checksum(points)
    voronoi(points)
    assert tools.checksum(points) == initial_checksum
