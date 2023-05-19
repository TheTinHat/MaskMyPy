import pytest
import os
from maskmypy import Atlas, Sensitive, Candidate, Donut
from geopandas import GeoDataFrame
from pandas.testing import assert_frame_equal


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
    atlas._save_gdf(points, "123")
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


def test_add_multiple_sensitive(points, address, tmpdir):
    atlas = Atlas("test")
    atlas.add_sensitive(points)
    with pytest.raises(ValueError):
        atlas.add_sensitive(address)


def test_add_candidate(points, tmpdir):
    atlas = Atlas("test")
    atlas.add_sensitive(points)
    donut = Donut(points, 50, 500)
    mdf = donut.run()
    params = donut.params
    atlas.add_candidate(mdf, params)
    assert len(atlas.candidates) == 1
    assert len(atlas.read_gdf(atlas.candidates[0].id)) == len(points)


def test_add_candidate_with_container_address(points, container, address):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    container_layer = atlas.add_container(container, "container_layer")
    address_layer = atlas.add_address(address, "address_layer")

    donut = Donut(points, 50, 500)
    mdf = donut.run()
    params = donut.params
    atlas.add_candidate(mdf, params, container=container_layer, address=address_layer)

    assert atlas.candidates[0].container.name == "container_layer"
    assert atlas.candidates[0].address.name == "address_layer"


def test_add_identical_candidates(points):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    donut1 = Donut(points, 50, 500, seed=123)
    donut2 = Donut(points, 50, 500, seed=123)
    atlas.add_candidate(donut1.run(), donut1.params)
    with pytest.raises(ValueError):
        atlas.add_candidate(donut2.run(), donut2.params)


def test_add_layers_before_sensitive(points, address, container):
    atlas = Atlas("test", in_memory=True)
    donut = Donut(points, 50, 500)

    with pytest.raises(ValueError):
        atlas.add_candidate(donut.run(), donut.params)

    with pytest.raises(ValueError):
        atlas.add_container(container, "BoundaryPolygons")

    with pytest.raises(ValueError):
        atlas.add_address(address, "AddressPoints")


def test_generic_mask(points):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    atlas.mask(Donut, low=50, high=500)
    assert len(atlas.candidates) == 1


def test_generic_mask_with_container_name(points, container, address):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    atlas.add_container(container, "BoundaryPolygons")
    atlas.mask(Donut, low=50, high=500, distribution="areal", container="BoundaryPolygons")
    assert atlas.candidates[0].params["distribution"] == "areal"
    assert atlas.candidates[0].container.name == "BoundaryPolygons"


def test_generic_mask_with_container_object(points, container, address):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    cont_obj = atlas.add_container(container, "BoundaryPolygons")
    atlas.mask(Donut, low=50, high=500, distribution="areal", container=cont_obj)
    assert atlas.candidates[0].params["distribution"] == "areal"
    assert atlas.candidates[0].container.name == "BoundaryPolygons"


def test_donut_mask_with_container(points, container):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    atlas.add_container(container, "BoundaryPolygons")
    atlas.donut(50, 500, container="BoundaryPolygons", distribution="areal")
    assert atlas.candidates[0].params["distribution"] == "areal"
    assert atlas.candidates[0].container.name == "BoundaryPolygons"


def test_donut_iterate_mask_with_container(points, container):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    atlas.add_container(container, "BoundaryPolygons")
    atlas.donut_i(
        distance_list=[(50, 500), (100, 500), (150, 500), (200, 1000)],
        container="BoundaryPolygons",
        distribution="areal",
    )
    with pytest.raises(ValueError):
        atlas.donut_i(
            distance_list=[
                (500, 50),
                (100, 500),
            ],
            container="BoundaryPolygons",
            distribution="areal",
        )

    for candidate in atlas.candidates:
        assert candidate.params["distribution"] == "areal"
        assert candidate.container.name == "BoundaryPolygons"
    assert len(atlas.candidates) == 4


def test_many_to_many_container_relationships(points, container, tmpdir):
    atlas_a = Atlas("test_a")
    atlas_a.add_sensitive(points)
    atlas_a.add_container(container, "BoundaryPolygons_A")
    atlas_a.add_container(container, "BoundaryPolygons_B")
    atlas_a.donut(50, 500, container="BoundaryPolygons_A")

    atlas_b = Atlas("test_b")
    atlas_b.add_sensitive(points)
    atlas_b.add_container(container, "BoundaryPolygons_A")
    atlas_b.relate_container("BoundaryPolygons_B")
    atlas_b.add_container(container, "BoundaryPolygons_C")
    atlas_b.donut(50, 500, container="BoundaryPolygons_B")
    atlas_b.donut(50, 500, container="BoundaryPolygons_C")

    assert len(atlas_a.containers) == 2
    assert atlas_a.candidates[0].container.name == "BoundaryPolygons_A"

    assert len(atlas_b.containers) == 3
    assert atlas_b.candidates[0].container.name == "BoundaryPolygons_B"
    assert atlas_b.candidates[1].container.name == "BoundaryPolygons_C"


def test_voronoi_mask_without_snapping(points):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    atlas.voronoi(snap=False)
    assert atlas.candidates[0].params["snap"] is False


def test_location_swap_with_address_name(points, address):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    atlas.add_address(address, "AddressPoints")
    atlas.location_swap(5, 10, address_name="AddressPoints")
    assert isinstance(atlas.read_gdf(atlas.candidates[0].id), GeoDataFrame)


def test_gpkg_layer_deduplication(points, tmpdir):
    atlas_a = Atlas("test_a", "file.db")
    atlas_a.add_sensitive(points)
    initial_size = os.path.getsize("file.gpkg")

    atlas_b = Atlas("test_b", "file.db")
    atlas_b.add_sensitive(points)
    final_size = os.path.getsize("file.gpkg")

    assert initial_size == final_size


def test_add_container(points, container, tmpdir):
    atlas = Atlas("test")
    atlas.add_sensitive(points)
    atlas.add_container(container, "BoundaryPolygons")
    assert isinstance(atlas.read_gdf(atlas.containers[0].id), GeoDataFrame)
    assert atlas.sensitive.containers[0].name == "BoundaryPolygons"


def test_get_container_address(points, container, address):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    container_layer = atlas.add_container(container, "container_layer")
    address_layer = atlas.add_address(address, "address_layer")
    assert atlas.get_container("container_layer") == container_layer
    assert atlas.get_address("address_layer") == address_layer


def test_add_existing_container(points, container, address, tmpdir):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    atlas.add_container(container, "container")
    atlas.add_container(container, "container")
    assert len(atlas.containers) == 1

    with pytest.raises(ValueError):
        atlas.add_container(address, "container")

    atlas.add_container(container, "other_container")
    assert len(atlas.containers) == 2


def test_add_existing_address(points, container, address, tmpdir):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    atlas.add_address(address, "address")
    atlas.add_address(address, "address")
    assert len(atlas.addresses) == 1

    with pytest.raises(ValueError):
        atlas.add_address(container, "address")

    atlas.add_address(container, "other_address")
    assert len(atlas.addresses) == 2


def test_containers_all_method(points, container, tmpdir):
    atlas_a = Atlas("test_a")
    atlas_a.add_sensitive(points)
    atlas_a.add_container(container, "Container_A")

    atlas_b = Atlas("test_b")
    atlas_b.add_sensitive(points)
    atlas_b.add_container(container, "Container_B")

    atlas_c = Atlas("test_c")
    assert len(atlas_c.containers_all) == 2


def test_add_address(points, address):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    atlas.add_address(address, "AddressPoints")
    atlas.add_address(address, "OtherAddressPoints")
    assert isinstance(atlas.read_gdf(atlas.addresses[0].id), GeoDataFrame)
    assert atlas.sensitive.addresses[0].name == "AddressPoints"


def test_add_layers_on_disk(points, address, container, tmpdir):
    # Trim address points as quantity is not needed for this test
    address = address.loc[0:10, :]

    atlas = Atlas("test")
    donut = Donut(points, 50, 500)
    atlas.add_sensitive(points)
    atlas.add_candidate(donut.run(), donut.params)
    atlas.add_container(container, "BoundaryPolygons")
    atlas.add_address(address, "AddressPoints")

    assert isinstance(atlas.read_gdf(atlas.candidates[0].id), GeoDataFrame)
    assert_frame_equal(atlas.sdf, points)
    assert_frame_equal(atlas.read_gdf(atlas.containers[0].id), container)
    assert_frame_equal(atlas.read_gdf(atlas.addresses[0].id), address)


def test_add_layers_in_memory(points, address, container, tmpdir):
    # Trim address points as quantity is not needed for this test
    address = address.loc[0:10, :]

    atlas = Atlas("test", in_memory=True)
    donut = Donut(points, 50, 500)
    atlas.add_sensitive(points)
    atlas.add_candidate(donut.run(), donut.params)
    atlas.add_container(container, "BoundaryPolygons")
    atlas.add_address(address, "AddressPoints")

    assert isinstance(atlas.read_gdf(atlas.candidates[0].id), GeoDataFrame)
    assert_frame_equal(atlas.sdf, points)
    assert_frame_equal(atlas.read_gdf(atlas.containers[0].id), container)
    assert_frame_equal(atlas.read_gdf(atlas.addresses[0].id), address)


def test_drift_calculation(points):
    atlas = Atlas("test", in_memory=True)
    donut = Donut(points, 50, 500)
    atlas.add_sensitive(points)
    candidate = atlas.add_candidate(donut.run(), donut.params)
    atlas.drift(candidate.id)
    assert isinstance(atlas.candidates[0].drift, float)


def test_calculate_k(points, address):
    atlas = Atlas("test", in_memory=True)
    donut = Donut(points, 100, 1000)
    atlas.add_sensitive(points)
    pop = atlas.add_address(address, "address_points")
    candidate = atlas.add_candidate(donut.run(), donut.params)
    atlas.calculate_k(candidate.id, address_name=pop.name)
    assert atlas.candidates[0].k_max is not None
    assert atlas.candidates[0].k_max > 1
    assert atlas.candidates[0].k_max > atlas.candidates[0].k_min
    assert atlas.candidates[0].k_max > atlas.candidates[0].k_mean
    assert atlas.candidates[0].k_max > atlas.candidates[0].k_med


def test_nnd_calculation(points):
    atlas = Atlas("test", in_memory=True)
    donut = Donut(points, 50, 500)
    atlas.add_sensitive(points)
    assert atlas.sensitive.nnd_max > 0
    assert atlas.sensitive.nnd_max > atlas.sensitive.nnd_min
    assert atlas.sensitive.nnd_max > atlas.sensitive.nnd_mean
    atlas.add_candidate(donut.run(), donut.params)

    assert atlas.candidates[0].nnd_max > 0
    assert atlas.candidates[0].nnd_max > atlas.candidates[0].nnd_min
    assert atlas.candidates[0].nnd_max > atlas.candidates[0].nnd_mean


def test_analyze_all(points, address):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    atlas.add_address(address, "Addresses")
    atlas.donut(low=50, high=500)
    atlas.donut(low=100, high=1000)
    assert atlas.candidates[0].k_max is None
    assert atlas.candidates[1].k_max is None
    assert atlas.candidates[0].drift is None

    atlas.analyze_all(address_name="Addresses")
    assert isinstance(atlas.candidates[0].k_max, int)
    assert isinstance(atlas.candidates[1].k_max, int)
    assert isinstance(atlas.candidates[0].drift, float)


def test_rank(points, address):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)
    atlas.add_address(address, "Addresses")
    atlas.donut(low=5, high=50)
    atlas.donut(low=500, high=5000)
    atlas.analyze_all(address_name="Addresses")

    ranked = atlas.rank("drift")
    assert ranked[0].drift < ranked[1].drift

    ranked = atlas.rank("nnd_min")
    assert ranked[0].nnd_min < ranked[1].nnd_min

    k_floor = atlas.candidates[1].k_min
    ranked = atlas.rank("nnd_min", min_k=k_floor)
    assert len(ranked) == 1

    ranked = atlas.rank("drift", desc=True)
    assert ranked[0].drift > ranked[1].drift


def test_nominate(points):
    atlas = Atlas("test", in_memory=True)
    atlas.add_sensitive(points)

    cand_0 = atlas.donut(low=5, high=50)
    atlas.nominate(atlas.candidates[0].id)
    assert atlas.nominee == cand_0

    cand_1 = atlas.donut(low=500, high=5000)
    atlas.nominate(atlas.candidates[1].id)
    assert atlas.nominee == cand_1
