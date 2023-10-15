import json

import pytest

from maskmypy import Atlas2, donut, tools


def test_atlas_mask(points):
    atlas = Atlas2(points)
    atlas.mask(donut, low=50, high=500)
    assert len(atlas[:]) == 1
    assert atlas[0]["checksum"] != tools._checksum(points)


def test_atlas_as_df(points):
    atlas = Atlas2(points)
    atlas.mask(donut, low=50, high=500)
    df = atlas.as_df()
    assert df.iloc[0]["high"] == 500
    assert df.iloc[0]["mask"] == "donut"


def test_atlas_restore_from_json(points):
    atlas = Atlas2(points)

    atlas.mask(donut, low=10, high=100)
    atlas.mask(donut, low=50, high=500)
    check_1a = atlas[0]["checksum"]
    check_2a = atlas[1]["checksum"]

    atlas.save_candidates("tmp_test.json")
    del atlas

    with open("tmp_test.json") as f:
        candidates = json.load(f)

    atlas2 = Atlas2(points, candidates=candidates)

    gdf_0 = atlas2.gen_gdf(0, persist=True)
    check_1b = tools._checksum(gdf_0)
    assert check_1a == check_1b

    gdf_1 = atlas2.gen_gdf(1, persist=True)
    check_2b = tools._checksum(gdf_1)
    assert check_2a == check_2b


def test_atlas_context_hydration(points, container):
    atlas = Atlas2(points)
    atlas.mask(donut, container=container, low=50, high=500)
    atlas.save_candidates("tmp_test.json")
    del atlas

    with open("tmp_test.json") as f:
        candidates = json.load(f)

    atlas2 = Atlas2(points, candidates=candidates)
    atlas2.add_contexts(container)
    atlas2.gen_gdf(0)


def test_atlas_context_hydration_missing_context(points, container):
    atlas = Atlas2(points)
    atlas.mask(donut, container=container, low=50, high=500)
    atlas.save_candidates("tmp_test.json")
    del atlas

    with open("tmp_test.json") as f:
        candidates = json.load(f)

    atlas2 = Atlas2(points, candidates=candidates)
    with pytest.raises(KeyError):
        atlas2.gen_gdf(0)
