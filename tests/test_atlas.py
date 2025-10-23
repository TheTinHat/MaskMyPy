import statistics
import time

import pytest

from maskmypy import Atlas, analysis, donut, tools, voronoi, street_k


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


def test_atlas_restore_from_json(points_small):
    points = points_small
    atlas = Atlas(points)

    atlas.mask(donut, low=10, high=100)
    atlas.mask(donut, low=50, high=500, snap_to_streets=True)

    check_1a = atlas[0]["checksum"]
    check_2a = atlas[1]["checksum"]

    atlas.to_json("/tmp/tmp_test.json")
    del atlas

    # Test by index value
    atlas2 = Atlas.from_json(points, "/tmp/tmp_test.json")

    gdf_0 = atlas2.gen_gdf(0)
    check_1b = tools.checksum(gdf_0)
    assert check_1a == check_1b

    gdf_1 = atlas2.gen_gdf(1)
    check_2b = tools.checksum(gdf_1)
    assert check_2a == check_2b

    # Test by checksum value
    atlas3 = Atlas.from_json(points, "/tmp/tmp_test.json")

    gdf_0 = atlas3.gen_gdf(checksum=check_1a)
    check_1c = tools.checksum(gdf_0)
    assert check_1a == check_1c

    gdf_1 = atlas3.gen_gdf(checksum=check_2a)
    check_2c = tools.checksum(gdf_1)
    assert check_2a == check_2c

    with pytest.raises(ValueError):
        atlas3.gen_gdf(checksum="aaaaaa")

def test_atlas_reproduces_street_k(points, address):
    atlas = Atlas(points)

    atlas.mask(street_k, population_gdf=address, start=1, spread=4, min_k=5, suppression=0.8, seed=12345)

    check_1a = atlas[0]["checksum"]

    atlas.to_json("/tmp/tmp_test.json")
    del atlas

    # Test by index value
    atlas2 = Atlas.from_json(points, "/tmp/tmp_test.json")
    atlas2.add_layers(address)

    gdf_0 = atlas2.gen_gdf(0)
    check_1b = tools.checksum(gdf_0)
    assert check_1a == check_1b


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

    assert (
        atlas[0]["stats"]["displacement_mean"]
        > atlas[1]["stats"]["displacement_mean"]
        > atlas[2]["stats"]["displacement_mean"]
    )

    atlas.sort(by="displacement_mean")
    assert (
        atlas[0]["stats"]["displacement_mean"]
        < atlas[1]["stats"]["displacement_mean"]
        < atlas[2]["stats"]["displacement_mean"]
    )

    atlas.sort(by="displacement_mean", desc=True)
    assert (
        atlas[0]["stats"]["displacement_mean"]
        > atlas[1]["stats"]["displacement_mean"]
        > atlas[2]["stats"]["displacement_mean"]
    )


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

    atlas.prune(by="displacement_min", min=0, max=299)
    assert len(atlas.candidates) == 1


def test_atlas_crs_mismatch(points, address):
    address = address.to_crs(epsg=4326)
    with pytest.raises(ValueError):
        atlas = Atlas(points, population=address)


def test_execution_time(points):
    atlas = Atlas(points)

    def mask_mock(sensitive, seed):
        time.sleep(0.1)
        return sensitive

    atlas.mask(mask_mock, measure_execution_time=True)
    assert round(atlas[0]["stats"]["execution_time"], 1) == 0.1


def test_peak_memory(points):
    points = points[0:2]
    atlas = Atlas(points)

    def mask_mock(sensitive, memory_mb, seed):
        peakmemory_size = memory_mb * 1024 * 1024  # 500MB
        byte_array = bytearray(peakmemory_size)
        return sensitive

    atlas.mask(mask_mock, memory_mb=1, measure_peak_memory=True, measure_execution_time=False)
    assert round(atlas[0]["stats"]["memory_peak_mb"]) == 1

    atlas.mask(mask_mock, memory_mb=100, measure_peak_memory=True, measure_execution_time=False)
    assert round(atlas[1]["stats"]["memory_peak_mb"]) == 100

    atlas.mask(mask_mock, memory_mb=10, measure_peak_memory=True, measure_execution_time=False)
    assert round(atlas[2]["stats"]["memory_peak_mb"]) == 10


def test_seed_not_in_voronoi_candidate(points):
    atlas = Atlas(points)
    atlas.mask(voronoi, snap_to_streets=False)
    assert "seed" not in atlas[0]["kwargs"]
    atlas.gen_gdf(idx=0)


def test_memory_and_speed_are_exclusive(points):
    atlas = Atlas(points)
    with pytest.raises(ValueError):
        atlas.mask(donut, low=1, high=2, measure_peak_memory=True, measure_execution_time=True)
