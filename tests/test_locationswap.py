def test_location_swap(atlas):
    atlas.locationswap(50, 100)
    atlas.locationswap_i([10, 20, 30], [100, 200, 300, 400])
    assert len(atlas.candidates) == 5
