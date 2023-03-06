import os
import shutil
import geopandas as gpd
import pytest
from copy import deepcopy
from pandas.testing import assert_frame_equal
from maskmypy import Atlas, Donut


@pytest.fixture
def points():
    return gpd.read_file("tests/points.geojson").to_crs(epsg=26910)


@pytest.fixture()
def tmpdir():
    os.makedirs("./tmp/", exist_ok=True)
    yield
    shutil.rmtree("./tmp")


@pytest.fixture
def atlas(points, tmpdir):
    return Atlas(name="test_atlas", directory="./tmp/", sensitive=points)


def test_atlas_autosave_and_load(atlas):
    atlas.donut([10, 20, 30], [110, 120, 130], seed=123)
    del atlas

    atlas = Atlas.load(name="test_atlas", directory="./tmp/")
    assert len(atlas.candidates) == 3


def test_atlas_with_existing_candidates(atlas):
    atlas.donut([10, 20, 30], [110, 120, 130], seed=123)
    atlas.donut([10, 20, 30, 40, 50], [110, 120, 130, 140, 150], seed=123)
    assert len(atlas.candidates) == 5
    atlas.donut([10, 20, 30], [110, 120, 130], seed=456)
    assert len(atlas.candidates) == 8


def test_atlas_get(atlas):
    atlas.donut([10, 20, 30], [110, 120, 130], seed=123)
    result_1 = atlas.get(cid=atlas.cids[0])
    result_2 = atlas.get(0)
    assert result_1 == result_2


def test_atlas_flush_candidates(atlas):
    atlas.donut([10, 20, 30], [110, 120, 130], seed=123)
    atlas.flush_candidates()
    assert atlas.candidates[0].mdf == None
    assert isinstance(atlas.candidates[0].get().mdf, gpd.GeoDataFrame)


def test_multiple_atlases(points, tmpdir):
    atlas_a = Atlas(name="test_atlas_a", directory="./tmp/", sensitive=points)
    atlas_b = Atlas(name="test_atlas_b", directory="./tmp/", sensitive=points)

    atlas_a.donut([10, 20, 30], [110, 120, 130], seed=123)
    atlas_b.donut([10, 20, 30], [110, 120, 130], seed=123)

    atlas_a = Atlas.load(name="test_atlas_a", directory="./tmp/")
    atlas_b = Atlas.load(name="test_atlas_a", directory="./tmp/")

    assert len(atlas_a.candidates) == 3
    assert len(atlas_b.candidates) == 3


# def test_atlas_delete(atlas):
#     atlas.donut([10, 20, 30], [110, 120, 130], seed=123)
#     assert len(atlas.candidates) == 2
#     atlas.delete_candidate(atlas.cids[1])

#     assert len(atlas.storage.list_candidates(sid=atlas.sid)) == 2


def test_atlas_set_candidate_bad_crs(atlas, points):
    mdf, mask_params = Donut(points, 50, 500, seed=123).run()
    mdf = mdf.to_crs(epsg=2955)

    with pytest.raises(AssertionError):
        atlas.create_candidate(mdf, mask_params)

    mdf = mdf.to_crs(atlas.crs)
    atlas.create_candidate(mdf, mask_params)


def test_atlas_set_candidate_unmasked(atlas, points):
    with pytest.raises(AssertionError):
        atlas.create_candidate(points, {})


# def test_atlas_autosave(points, masked_points, tmpdir):
#     atlas = Atlas(points, directory="./tmp/", autosave=True)
#     atlas.create_candidate(masked_points, {})
#     saved = gpd.read_file(atlas.gpkg_path, layer=atlas.get().layer_name)
#     assert saved.equals(masked_points)


# def test_atlas_get(points, masked_points):
#     atlas = Atlas("test-atlas", points)
#     atlas.create_candidate(masked_points, {})
#     assert atlas.get().gdf.equals(masked_points)
#     assert atlas.get().gdf.equals(points) is False
#     assert "checksum" in atlas.get().parameters
#     assert "test_key" not in atlas.get().parameters


# # def test_atlas_flush_candidate(points, masked_points, tmpdir):
# #     atlas = Atlas(points, directory="./tmp")
# #     atlas.create_candidate(masked_points, {})
# #     saved = gpd.read_file(atlas.gpkg_path, layer=atlas.get().layer_name)
# #     assert saved.equals(atlas.get().gdf)


# # def test_atlas_autoflush_candidate(points, masked_points, tmpdir):
# #     atlas = Atlas(points, autoflush=True, directory="./tmp")
# #     atlas.create_candidate(masked_points, {})
# #     saved = gpd.read_file(atlas.gpkg_path, layer=atlas.get().layer_name)
# #     assert saved.equals(atlas.get().gdf)


#     # Test first atlas again with name specified
#     atlas = Atlas.open_atlas(directory="./tmp", name="atlas_open_test")
#     assert len(atlas.candidates) == 1

#     # Test second atlas
#     atlas = Atlas.open_atlas(directory="./tmp", name="atlas_open_test_two")
#     assert len(atlas.candidates) == 2
#     assert atlas.get().parameters["checksum"] == atlas.candidates[0].checksum
#     assert atlas.sensitive.equals(points)
#     assert atlas.get().gdf.equals(masked_points)


# def test_donut(points):
#     atlas = Atlas("test-atlas", points)

#     with pytest.raises(TypeError):
#         donut = atlas.donut()

#     donut = atlas.donut(50, 500)
#     assert isinstance(donut.gdf, gpd.GeoDataFrame)
#     assert isinstance(donut.parameters["author"], str)
#     assert isinstance(donut.parameters["created_at"], int)


def test_geopandas_does_not_modify_sensitive(points):
    atlas = Atlas("test-atlas", points)
    original_sensitive = deepcopy(atlas.sensitive)
    atlas.donut(50, 500)

    assert_frame_equal(atlas.sensitive, original_sensitive)
    with pytest.raises(AssertionError):
        assert_frame_equal(atlas.sensitive, atlas.get().get().mdf)


def test_donut_list(atlas):
    mins = [50, 100, 150, 200, 250]
    maxes = [500, 550, 600, 650, 700]
    donuts = atlas.donut(mins, maxes)
    assert len(donuts) == len(mins)


def test_donut_list_uneven(atlas):
    mins = [50, 100, 150, 200]
    maxes = [500, 550]
    donuts = atlas.donut(mins, maxes)
    assert len(donuts) == len(mins)

    mins = [50, 100]
    maxes = [500, 550, 600, 650, 700]
    donuts = atlas.donut(mins, maxes)
    assert len(donuts) == len(maxes)


@pytest.mark.slow
def test_memory_management(points, tmpdir):
    import gc
    import psutil

    atlas = Atlas(name="test_a", sensitive=points, directory="./tmp")
    mem_start = psutil.Process(os.getpid()).memory_info().rss / 1024**2
    atlas.donut([1], list(range(2, 102)))
    mem_candidates = (psutil.Process(os.getpid()).memory_info().rss / 1024**2) - mem_start
    del atlas
    gc.collect()

    mem_start = psutil.Process(os.getpid()).memory_info().rss / 1024**2
    atlas = Atlas(name="test_b", sensitive=points, directory="./tmp")
    atlas.donut([1], list(range(2, 102)))
    atlas.flush_candidates()
    gc.collect()
    mem_candidates_autoflush = (
        psutil.Process(os.getpid()).memory_info().rss / 1024**2
    ) - mem_start

    assert mem_candidates_autoflush < mem_candidates
