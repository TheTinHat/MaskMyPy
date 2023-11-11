import json
import statistics

import pytest

from maskmypy import Atlas, analysis, donut, tools


def test_atlas_mask(points):
    atlas = Atlas(points)
    atlas.mask(donut, low=50, high=500)
    assert len(atlas[:]) == 1
    assert atlas[0]["checksum"] != tools.checksum(points)


def test_atlas_as_df(points):
    atlas = Atlas(points)
    atlas.mask(donut, low=50, high=500)
    df = atlas.as_df()
    assert df.iloc[0]["high"] == 500
    assert df.iloc[0]["mask"] == "donut"


def test_atlas_restore_from_json(points):
    atlas = Atlas(points)

    atlas.mask(donut, low=10, high=100)
    atlas.mask(donut, low=50, high=500)
    check_1a = atlas[0]["checksum"]
    check_2a = atlas[1]["checksum"]

    atlas.to_json("/tmp/tmp_test.json")
    del atlas

    atlas2 = Atlas.from_json(points, "/tmp/tmp_test.json")

    gdf_0 = atlas2.gen_gdf(0)
    check_1b = tools.checksum(gdf_0)
    assert check_1a == check_1b

    gdf_1 = atlas2.gen_gdf(1)
    check_2b = tools.checksum(gdf_1)
    assert check_2a == check_2b


def test_atlas_context_hydration(points, container):
    atlas = Atlas(points)
    atlas.mask(donut, container=container, low=50, high=500)
    atlas.to_json("/tmp/tmp_test.json")
    del atlas

    atlas2 = Atlas.from_json(points, "/tmp/tmp_test.json")
    with pytest.raises(KeyError):
        atlas2.gen_gdf(0)

    atlas2.add_layers(container)
    atlas2.gen_gdf(0)
    del atlas2

    atlas3 = Atlas.from_json(points, "/tmp/tmp_test.json", layers=[container])
    atlas3.gen_gdf(0)


def test_atlas_sort(points):
    atlas = Atlas(points)
    atlas.mask(donut, low=300, high=399)
    atlas.mask(donut, low=200, high=299)
    atlas.mask(donut, low=100, high=199)

    assert atlas[0]["kwargs"]["low"] > atlas[1]["kwargs"]["low"] > atlas[2]["kwargs"]["low"]

    atlas.sort(by="low")
    assert atlas[0]["kwargs"]["low"] < atlas[1]["kwargs"]["low"] < atlas[2]["kwargs"]["low"]

    atlas.sort(by="timestamp")
    assert atlas[0]["timestamp"] < atlas[1]["timestamp"] < atlas[2]["timestamp"]


def test_displacement(points):
    masked_gdf = donut(points, 50, 500)
    displacement_gdf = analysis.displacement(points, masked_gdf)
    assert "_distance" not in points.columns
    assert "_distance" not in masked_gdf.columns
    assert "_distance" in displacement_gdf.columns


def test_evaluate(points, address):
    atlas = Atlas(points, population=address)
    atlas.mask(donut, low=100, high=199, skip_slow_evaluators=False)
    atlas.mask(donut, low=300, high=399, skip_slow_evaluators=False)
    assert atlas[0]["stats"]["displacement_min"] < atlas[1]["stats"]["displacement_max"]
    assert atlas[0]["stats"]["k_satisfaction_50"] < atlas[0]["stats"]["k_satisfaction_5"]


def test_ripley(points):
    atlas = Atlas(points)
    lows = []
    for i in range(0, 4):
        atlas.mask(donut, low=1, high=100, skip_slow_evaluators=False)
        lows.append(atlas[i]["stats"]["ripley_rmse"])

    highs = []
    for i in range(4, 7):
        atlas.mask(donut, low=100, high=200, skip_slow_evaluators=False)
        highs.append(atlas[i]["stats"]["ripley_rmse"])

    assert (statistics.mean(lows)) < (statistics.mean(highs))

def test_atlas_prune(points, address):
    atlas = Atlas(points, population=address)
    atlas.mask(donut, low=300, high=399)
    atlas.mask(donut, low=200, high=299)
    atlas.mask(donut, low=100, high=199)

    atlas.prune(by="displacement_min", min=200, max=9999)
    assert len(atlas.candidates) == 2

    atlas.prune(by="low", min=0, max=299)
    assert len(atlas.candidates) == 1
        











