from maskmypy import Voronoi


def test_voronoi(atlas):
    Voronoi(atlas.sensitive, snap=False).run()
