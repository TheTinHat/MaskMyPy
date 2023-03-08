import json
import os
import shutil
from copy import deepcopy
from pathlib import Path

import geopandas as gpd
import psutil
import pytest
from numpy import random
from pandas.testing import assert_frame_equal
from shapely.affinity import translate

from maskmypy import Atlas, Candidate


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


# def test_atlas_delete(points, tmpdir):
#     atlas = Atlas("test-atlas", points, directory="./tmp/")
#     atlas.donut([10, 20, 30], [110, 120, 130], seed=123)
#     assert len(atlas.candidates) == 2
#     atlas.delete_candidate(atlas.cids[1])

#     assert len(atlas.storage.list_candidates(sid=atlas.sid)) == 2


# def test_atlas_set_candidate_bad_crs(points, masked_points):
#     atlas = Atlas("test-atlas", points)
#     masked_points = masked_points.to_crs(epsg=2955)
#     with pytest.raises(AssertionError):
#         atlas.create_candidate(masked_points, {})


# def test_atlas_set_candidate_unmasked(points):
#     atlas = Atlas("test-atlas", points)
#     with pytest.raises(AssertionError):
#         atlas.create_candidate(masked_points, {})


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


# def test_atlas_save_atlas(points, masked_points, tmpdir):
#     atlas = Atlas(points, name="atlas_save_test", directory="./tmp")
#     atlas.create_candidate(masked_points, {})
#     atlas.save_atlas()

#     saved = gpd.read_file(atlas.gpkg_path, layer=atlas.get().layer_name)
#     assert saved.equals(masked_points)

#     with open(atlas.archive_path, "r") as file:
#         archive = json.load(file)

#     assert "metadata" in archive
#     assert "candidates" in archive

#     assert archive["metadata"]["directory"] == "tmp"
#     assert atlas.get().layer_name in archive["candidates"]


def test_donut(points):
    atlas = Atlas("test-atlas", points)

    with pytest.raises(TypeError):
        donut = atlas.donut()

    donut = atlas.donut(50, 500)
    assert isinstance(donut.gdf, gpd.GeoDataFrame)
    assert isinstance(donut.parameters["author"], str)
    assert isinstance(donut.parameters["created_at"], int)


def test_geopandas_does_not_modify_sensitive(points):
    atlas = Atlas("test-atlas", points)
    original_sensitive = deepcopy(atlas.sensitive)
    atlas.donut(50, 500)

    assert_frame_equal(atlas.sensitive, original_sensitive)
    with pytest.raises(AssertionError):
        assert_frame_equal(atlas.sensitive, atlas.get().gdf)


# def test_donut_list(points):
#     atlas = Atlas("test-atlas", points)

#     mins = [50, 100, 150, 200, 250]
#     maxes = [500, 550, 600, 650, 700]
#     donuts = atlas.donut(mins, maxes)
#     assert len(donuts) == len(mins)


# def test_donut_list_uneven(points):
#     atlas = Atlas("test-atlas", points)
#     mins = [50, 100, 150, 200]
#     maxes = [500, 550]
#     donuts = atlas.donut(mins, maxes)
#     assert len(donuts) == len(mins)

#     mins = [50, 100]
#     maxes = [500, 550, 600, 650, 700]
#     donuts = atlas.donut(mins, maxes)
#     assert len(donuts) == len(maxes)


# @pytest.mark.slow
# def test_memory_management(points, tmpdir):
#     import gc

#     atlas = Atlas(points, directory="./tmp", keep_last=99999)
#     mem_start = psutil.Process(os.getpid()).memory_info().rss / 1024**2
#     atlas.donut([1], list(range(2, 252)))
#     mem_candidates = (psutil.Process(os.getpid()).memory_info().rss / 1024**2) - mem_start
#     del atlas
#     gc.collect()

#     mem_start = psutil.Process(os.getpid()).memory_info().rss / 1024**2
#     atlas = Atlas(points, directory="./tmp", keep_last=99999, autoflush=True, autosave=True)
#     atlas.donut([1], list(range(2, 252)))
#     gc.collect()
#     mem_candidates_autoflush = (
#         psutil.Process(os.getpid()).memory_info().rss / 1024**2
#     ) - mem_start

#     assert mem_candidates_autoflush < mem_candidates
