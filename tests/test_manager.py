import pytest
import os
from maskmypy import Atlas, Sensitive, Candidate, Donut
from geopandas import GeoDataFrame


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


def test_in_memory_does_not_write_to_disk(points):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    assert os.path.exists("atlas.db") is False
    assert os.path.exists("atlas.gpkg") is False


def test_in_memory_immutability(points):
    crs_1 = points.crs
    atlas = Atlas("test", in_memory=True)
    atlas.save_gdf(points, "123")
    crs_2 = atlas.read_gdf("123").crs
    points = points.to_crs(4326)
    crs_3 = points.crs
    assert crs_1 == crs_2
    assert crs_1 != crs_3
    assert crs_2 != crs_3


def test_load(points, tmpdir):
    atlas = Atlas("test")
    atlas.add_sensitive(points)
    donut = Donut(points, 50, 500)
    atlas.add_candidate(donut.run(), donut.params)
    del atlas
    atlas_loaded = Atlas.load("test", "./atlas.db")
    cand = atlas_loaded.candidates[0]
    assert atlas_loaded.sensitive.name == "test"
    assert isinstance(atlas_loaded.sdf, GeoDataFrame)
    assert isinstance(atlas_loaded.mdf(cand), GeoDataFrame)
    assert isinstance(cand.id, str)


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


def test_add_layers_before_sensitive(points, addresses, container, tmpdir):
    atlas = Atlas("test")
    donut = Donut(points, 50, 500)

    with pytest.raises(ValueError):
        atlas.add_candidate(donut.run(), donut.params)

    with pytest.raises(ValueError):
        atlas.add_container(container, "BoundaryPolygons")

    with pytest.raises(ValueError):
        atlas.add_population(addresses, "AddressPoints")


def test_generic_mask(points, tmpdir):
    atlas = Atlas("test")
    atlas.add_sensitive(points)
    atlas.mask(Donut, low=50, high=500)
    assert len(atlas.candidates) == 1


def test_gpkg_layer_deduplication(points, tmpdir):
    atlas = Atlas("test")
    atlas.add_sensitive(points)
    atlas_clone = Atlas("test_clone")
    atlas_clone.add_sensitive(points)
    # Assertion required


def test_add_container(points, container, tmpdir):
    atlas = Atlas("test")
    atlas.add_sensitive(points)
    atlas.add_container(container, "BoundaryPolygons")
    assert isinstance(atlas.read_gdf(atlas.containers[0].id), GeoDataFrame)
    assert atlas.sensitive.containers[0].name == "BoundaryPolygons"


def test_add_duplicate_containers(points, container, tmpdir):
    atlas = Atlas("test")
    atlas.add_sensitive(points)
    atlas.add_container(container, "BoundaryPolygons")
    atlas.add_container(container, "BoundaryAreas")
    # Assertion required


def test_add_population(points, addresses):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    atlas.add_population(addresses, "AddressPoints")
    assert isinstance(atlas.read_gdf(atlas.populations[0].id), GeoDataFrame)
    assert atlas.sensitive.populations[0].name == "AddressPoints"


def test_add_layers_on_disk(points, addresses, container, tmpdir):
    atlas = Atlas("test")
    donut = Donut(points, 50, 500)
    atlas.add_sensitive(points)
    atlas.add_candidate(donut.run(), donut.params)
    atlas.add_container(container, "BoundaryPolygons")
    atlas.add_population(addresses, "AddressPoints")

    assert isinstance(atlas.sdf, GeoDataFrame)
    assert isinstance(atlas.read_gdf(atlas.candidates[0].id), GeoDataFrame)
    assert isinstance(atlas.read_gdf(atlas.containers[0].id), GeoDataFrame)
    assert isinstance(atlas.read_gdf(atlas.populations[0].id), GeoDataFrame)


def test_add_layers_in_memory(points, addresses, container, tmpdir):
    atlas = Atlas("test", in_memory=True)
    donut = Donut(points, 50, 500)
    atlas.add_sensitive(points)
    atlas.add_candidate(donut.run(), donut.params)
    atlas.add_container(container, "BoundaryPolygons")
    atlas.add_population(addresses, "AddressPoints")

    assert isinstance(atlas.sdf, GeoDataFrame)
    assert isinstance(atlas.read_gdf(atlas.candidates[0].id), GeoDataFrame)
    assert isinstance(atlas.read_gdf(atlas.containers[0].id), GeoDataFrame)
    assert isinstance(atlas.read_gdf(atlas.populations[0].id), GeoDataFrame)
