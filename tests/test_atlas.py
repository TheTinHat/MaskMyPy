from maskmypy import Atlas, Candidate
import geopandas as gpd
import pytest
from numpy import random
from shapely.affinity import translate
import os
import shutil
from pathlib import Path
import json


@pytest.fixture
def points():
    return gpd.read_file("tests/points.geojson")


@pytest.fixture
def masked_points(points):
    points = points.copy(deep=True)
    points.geometry = points.geometry.translate(0.001)
    return points


@pytest.fixture()
def tmpdir():
    os.makedirs("./tmp/", exist_ok=True)
    yield
    shutil.rmtree("./tmp")


def test_atlas_checksum_mismatch(points):
    atlas = Atlas(points)
    checksum = atlas.checksum
    points.at[0, "geometry"] = translate(points.at[0, "geometry"], 0.001)
    assert checksum != Atlas(points).checksum


def test_atlas_checksum_match(points, tmpdir):
    checksum = Atlas(points).checksum
    points.to_file("./tmp/points.shp")
    points.to_file("./tmp/points.gpkg", driver="GPKG")

    shp_points = gpd.read_file("./tmp/points.shp")
    gpkg_points = gpd.read_file("./tmp/points.gpkg")

    assert checksum == Atlas(shp_points).checksum
    assert checksum == Atlas(gpkg_points).checksum


def test_atlas_gpkg_path(points):
    gpkg_path = Atlas(points, name="test_atlas").gpkg_path
    expected_path = Path.cwd() / "test_atlas.atlas.gpkg"
    assert gpkg_path == expected_path


def test_atlas_archive_path(points):
    archive_path = Atlas(points, name="test_atlas").archive_path
    expected_path = Path.cwd() / "test_atlas.atlas.json"
    assert archive_path == expected_path


def test_atlas_metadata(points):
    atlas = Atlas(points)
    metadata = atlas.metadata
    expected_keys = ["autosave", "directory", "keep_last", "name"]
    for key in expected_keys:
        assert key in metadata


def test_atlas_set(points, masked_points):
    atlas = Atlas(points, keep_last=1)
    atlas.set(Candidate(masked_points))
    atlas.set(Candidate(masked_points))
    assert len(atlas.candidates) == 1


def test_atlas_set_candidate_bad_crs(points, masked_points):
    atlas = Atlas(points)
    masked_points = masked_points.to_crs(epsg=26910)
    with pytest.raises(AssertionError):
        atlas.set(Candidate(masked_points))


def test_atlas_set_candidate_unmasked(points):
    atlas = Atlas(points)
    with pytest.raises(AssertionError):
        atlas.set(Candidate(points))


def test_atlas_autosave(points, masked_points, tmpdir):
    atlas = Atlas(points, directory="./tmp/", autosave=True)
    atlas.set(Candidate(masked_points))
    saved = gpd.read_file(atlas.gpkg_path, layer=atlas.get().layer_name)
    assert saved.equals(masked_points)


def test_atlas_get(points, masked_points):
    atlas = Atlas(points)
    atlas.set(Candidate(masked_points))
    assert atlas.get().df.equals(masked_points)
    assert atlas.get().df.equals(points) is False
    assert "checksum" in atlas.get().parameters
    assert "test_key" not in atlas.get().parameters


def test_atlas_flush_candidate(points, masked_points, tmpdir):
    atlas = Atlas(points, directory="./tmp")
    atlas.set(Candidate(masked_points))
    atlas.save_candidate(0, flush=True)
    assert atlas.candidates[0].df == None
    saved = gpd.read_file(atlas.gpkg_path, layer=atlas.get().layer_name)
    assert saved.equals(atlas.get().df)


def test_atlas_autoflush_candidate(points, masked_points, tmpdir):
    atlas = Atlas(points, autoflush=True, directory="./tmp")
    atlas.set(Candidate(masked_points))
    atlas.save_candidate(0)
    assert atlas.candidates[0].df == None
    saved = gpd.read_file(atlas.gpkg_path, layer=atlas.get().layer_name)
    assert saved.equals(atlas.get().df)


def test_atlas_save_atlas(points, masked_points, tmpdir):
    atlas = Atlas(points, name="atlas_save_test", directory="./tmp")
    atlas.set(Candidate(masked_points))
    atlas.save_atlas()

    saved = gpd.read_file(atlas.gpkg_path, layer=atlas.get().layer_name)
    assert saved.equals(masked_points)

    with open(atlas.archive_path, "r") as file:
        archive = json.load(file)

    assert "metadata" in archive
    assert "candidates" in archive

    assert archive["metadata"]["directory"] == "tmp"
    assert atlas.get().layer_name in archive["candidates"]


def test_atlas_open_atlas(points, masked_points, tmpdir):
    # Create first atlas
    atlas = Atlas(points, name="atlas_open_test", directory="./tmp")
    atlas.set(Candidate(masked_points))
    atlas.save_atlas()

    # Test first atlas and autodetect the name
    atlas = Atlas.open_atlas(directory="./tmp")
    assert atlas.get().parameters["checksum"][0:8] == "26b7538a"
    assert atlas.sensitive.equals(points)
    assert atlas.get().df.equals(masked_points)

    # Create a second atlas
    atlas = Atlas(points, name="atlas_open_test_two", directory="./tmp")
    atlas.set(Candidate(masked_points))
    atlas.set(Candidate(masked_points))
    atlas.save_atlas()

    # Test that atlas open fails without name specified
    with pytest.raises(Exception):
        atlas = Atlas.open_atlas(directory="./tmp")

    # Test first atlas again with name specified
    atlas = Atlas.open_atlas(directory="./tmp", name="atlas_open_test")
    assert len(atlas.candidates) == 1

    # Test second atlas
    atlas = Atlas.open_atlas(directory="./tmp", name="atlas_open_test_two")
    assert len(atlas.candidates) == 2
    assert atlas.get().parameters["checksum"] == atlas.candidates[0].checksum
    assert atlas.sensitive.equals(points)
    assert atlas.get().df.equals(masked_points)
