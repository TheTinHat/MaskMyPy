import pytest
import os
from maskmypy import Atlas, Sensitive, Candidate, Donut


def test_filename_appends_db_suffix(tmpdir):
    Atlas("test", "./test_file")
    assert os.path.exists("./test_file.db")


def test_filename_appends_db_existing_suffix(tmpdir):
    Atlas("test", "./test_file.test")
    assert os.path.exists("./test_file.test.db")


def test_filename_preserves_db_suffix(tmpdir):
    Atlas("test", "./test_file.db")
    assert os.path.exists("./test_file.db")


def test_filename_default(tmpdir):
    Atlas("test")
    assert os.path.exists("atlas.db")


def test_load(points, tmpdir):
    atlas = Atlas("test")
    atlas.add_sensitive(points)
    donut = Donut(points, 50, 500)
    atlas.add_candidate(donut.run(), donut.params)
    del atlas
    atlas_loaded = Atlas.load("test", "./atlas.db")
    assert atlas_loaded.sensitive.name == "test"
    assert isinstance(atlas_loaded.candidates[0].id, str)


def test_load_without_sensitive(tmpdir):
    atlas = Atlas("test")
    del atlas
    atlas_loaded = Atlas.load("test", "./atlas.db")
    assert atlas_loaded.sensitive is None


def test_add_multiple_sensitive(points, addresses, tmpdir):
    atlas = Atlas("test")
    atlas.add_sensitive(points)
    with pytest.raises(ValueError):
        atlas.add_sensitive(addresses)


def test_add_candidate(points, tmpdir):
    atlas = Atlas("test")
    atlas.add_sensitive(points)
    donut = Donut(points, 50, 500)
    mdf = donut.run()
    params = donut.params
    atlas.add_candidate(mdf, params)
    assert len(atlas.candidates) == 1
    assert len(atlas.read_gdf(atlas.candidates[0].id)) == len(points)


def test_add_identical_candidates(points, tmpdir):
    atlas = Atlas("test")
    atlas.add_sensitive(points)
    donut1 = Donut(points, 50, 500, seed=123)
    donut2 = Donut(points, 50, 500, seed=123)
    atlas.add_candidate(donut1.run(), donut1.params)
    with pytest.raises(ValueError):
        atlas.add_candidate(donut2.run(), donut2.params)


def test_add_candidate_before_sensitive(points, tmpdir):
    atlas = Atlas("test")
    donut = Donut(points, 50, 500)
    with pytest.raises(ValueError):
        atlas.add_candidate(donut.run(), donut.params)
