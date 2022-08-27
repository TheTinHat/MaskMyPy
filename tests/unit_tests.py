import geopandas as gpd
import pytest
from maskmypy import *
from maskmypy.tools import *
from numpy import random
from scipy.stats import normaltest
from shapely.geometry import Point

"""   INITIALIZATION   """


@pytest.fixture()
def data():
    crs = 26910
    rng = random.default_rng(seed=1234)

    point = gpd.GeoDataFrame(
        {"geometry": [Point(-122.87289, 49.30314)]}, index=[0], crs=4326
    ).to_crs(crs)
    test_point = gpd.GeoDataFrame(
        {"geometry": Point(-122.87290, 49.30260)}, index=[0], crs=4326
    ).to_crs(crs)
    test_circle = gpd.GeoDataFrame({"geometry": point.buffer(20)}, crs=crs)
    population = gpd.GeoDataFrame({"geometry": point.buffer(100), "pop": 100}, crs=crs)
    container = population.copy()
    bbox = population.total_bounds
    seeds = rng.integers(low=100000, high=10000000, size=100)
    assert len(set(seeds)) == 100, "Duplicate seeds found"

    address = gpd.GeoDataFrame(columns=["geometry"], crs=crs)
    for i in range(population.loc[0, "pop"]):
        contained = False
        while contained is False:
            addr = Point(
                rng.uniform(low=bbox[0], high=bbox[2]), rng.uniform(low=bbox[1], high=bbox[3])
            )
            if addr.intersects(population.loc[0, "geometry"]):
                address.loc[i, "geometry"] = addr
                contained = True
    return {
        "point": point,
        "population": population,
        "address": address,
        "container": container,
        "test_point": test_point,
        "test_circle": test_circle,
        "seeds": seeds,
    }


def test_load_population(data):
    test_donut = Donut(data["point"], population=data["population"])
    assert test_donut.secret.crs == test_donut.population.crs
    with pytest.raises(AssertionError):
        assert Donut(data["point"], population=data["population"].to_crs(4326))


def test_load_container(data):
    test_donut = Donut(data["point"], container=data["container"])
    assert test_donut.secret.crs == test_donut.container.crs
    with pytest.raises(AssertionError):
        assert Donut(data["point"], container=data["container"].to_crs(4326))


def test_load_address(data):
    test_donut = Donut(data["point"], address=data["address"])
    assert test_donut.secret.crs == test_donut.address.crs
    with pytest.raises(AssertionError):
        assert Donut(data["point"], address=data["address"].to_crs(4326))


def test_crop(data):
    test_donut = Donut(data["point"])
    dubious_crop = test_donut._crop(data["address"], data["test_circle"])
    assert len(dubious_crop) < len(data["address"])
    assert any(dubious_crop.intersects(data["test_circle"].loc[0, "geometry"]))


def test_crop_single_point(data):
    test_donut = Donut(data["point"])
    dubious_crop = test_donut._crop(data["address"], data["point"])
    assert len(dubious_crop) == len(data["address"])


def test_displacement(data):
    distance = int(data["point"].distance(data["test_point"]))
    assert distance == 60


def test_estimate_k(data):
    test_donut = Donut(
        data["point"],
        population=data["population"],
        min_distance=19.9,
        max_distance=20,
    )
    test_donut.run()
    mask_temp = estimate_k(test_donut.secret, test_donut.mask, population=data["population"])
    assert mask_temp.loc[0, "k_est"] == 4.0

    test_donut.max_distance = 50
    test_donut.min_distance = 49.9
    test_donut.run()
    mask_temp = estimate_k(test_donut.secret, test_donut.mask, population=data["population"])
    assert mask_temp.loc[0, "k_est"] == 25.0


def test_disaggregate_population(data):
    test_donut = Donut(data["point"], population=data["population"])
    test_donut.population["_pop_area"] = test_donut.population.area

    circle = data["point"].copy()
    circle.geometry = circle.geometry.buffer(50)
    dubious_disaggregate = disaggregate(circle, data["population"], "pop")
    assert int(dubious_disaggregate.loc[0, "pop_adjusted"]) == 25

    circle = data["point"].copy()
    circle.geometry = circle.geometry.buffer(75)
    dubious_disaggregate = disaggregate(circle, data["population"], "pop")
    assert int(dubious_disaggregate.loc[0, "pop_adjusted"]) == 56

    circle = data["point"].copy()
    circle.geometry = circle.geometry.buffer(100)
    dubious_disaggregate = disaggregate(circle, data["population"], "pop")
    assert int(dubious_disaggregate.loc[0, "pop_adjusted"]) == 100


def test_calculate_k_no_distance(data):
    test_donut = Donut(
        data["point"],
        address=data["address"],
        max_distance=1,
        min_distance=0.9,
        seed=data["seeds"][0],
    )
    test_donut.run()
    mask_k = calculate_k(data["point"], test_donut.mask, data["address"])
    assert int(mask_k.loc[0, "k_calc"]) == 0


def test_calculate_k(data):
    test_donut = Donut(
        data["point"],
        address=data["address"],
        max_distance=100,
        min_distance=99,
        seed=data["seeds"][0],
    )
    test_donut.run()
    mask_k = calculate_k(data["point"], test_donut.mask, data["address"])
    assert int(mask_k.loc[0, "k_calc"]) == 39


def test_containment_false(data):
    test_donut = Donut(data["point"], container=data["test_circle"], max_tries=0)
    test_donut.try_count = 0
    test_donut.mask = data["test_point"]
    test_donut._containment(data["test_point"])
    assert test_donut.mask.loc[0, "CONTAINED"] == 0


def test_containment_true(data):
    test_donut = Donut(data["point"], container=data["test_circle"])
    test_donut.try_count = 0
    test_donut.mask = data["point"]
    test_donut._containment(data["point"])
    assert test_donut.mask.loc[0, "CONTAINED"] == 1


def test_seed_reproducibility(data):
    numbers = []
    for i in range(100):
        test_donut = Donut(data["point"], seed=data["seeds"][0])
        offset_coords = test_donut._random_xy(1, 100)
        numbers.append(offset_coords)
    assert len(set(numbers)) == 1


def test_seed_randomness(data):
    numbers = []
    for seed in data["seeds"]:
        test_donut = Donut(data["point"], seed=seed)
        offset_coords = test_donut._random_xy(1, 100)
        numbers.append(offset_coords)
    assert len(set(numbers)) == len(data["seeds"])


@pytest.mark.parametrize("distribution", ["uniform", "areal"])
def test_random_xy(data, distribution):
    for i in range(100):
        test_donut = Donut(data["point"], distribution=distribution)
        offset_coords = test_donut._random_xy(1, 100)
        assert isinstance(offset_coords[0], float)
        assert isinstance(offset_coords[1], float)
        assert offset_coords[0] > -100 and offset_coords[1] > -100
        assert offset_coords[0] < 100 and offset_coords[1] < 100


def test_random_xy_gaussian(data):
    distance_list = []
    for seed in data["seeds"]:
        test_donut = Donut(
            data["point"], distribution="gaussian", max_distance=100, min_distance=0, seed=seed
        )
        test_donut.run()
        test_donut.mask = displacement(test_donut.secret, test_donut.mask)
        distance_list.append(test_donut.mask.loc[0, "_distance"])
    assert normaltest(distance_list)[1] > 0.1


def test_donut_set_radii(data):
    test_donut = Donut(data["point"], max_distance=100, min_distance=10)
    test_donut.mask = data["point"]
    test_donut._set_radii()
    assert test_donut.mask.loc[0, "_r_min"] == 10
    assert test_donut.mask.loc[0, "_r_max"] == 100


def test_donut_container(data):
    test_donut = Donut(
        data["point"],
        max_distance=900,
        min_distance=1,
        container=data["population"],
        seed=data["seeds"][0],
    )
    test_donut.run()
    assert test_donut.try_count > 1
    assert test_donut.mask.loc[0, "CONTAINED"] == 1


def test_donut_k_set_radii(data):
    test_donut = Donut_K(
        data["point"], population=data["population"], max_k_anonymity=100, min_k_anonymity=10
    )
    test_donut.mask = test_donut.secret
    test_donut._set_radii()
    assert round(test_donut.mask.loc[0, "_r_max"]) == 100
    assert round(test_donut.mask.loc[0, "_r_min"]) == 32


def test_donut_multiply_set_radii(data):
    test_donut = Donut_Multiply(
        data["point"],
        population=data["population"],
        population_multiplier=5,
        max_distance=100,
        min_distance=15,
    )
    test_donut.mask = test_donut.secret.copy()
    test_donut._set_radii()
    assert test_donut.mask.loc[0, "_r_max"] == 500
    assert test_donut.mask.loc[0, "_r_min"] == 75


def test_displacement_map(data):
    dubius_donut = Donut(data["point"], seed=data["seeds"][0])
    mask = dubius_donut.run()
    map_displacement(
        data["point"],
        mask,
        "tests/results/donut_map.png",
    )


def test_street(data):
    street = Street(data["point"], min_depth=4, max_depth=5, padding=500, seed=data["seeds"][0])
    street.run()

    assert isinstance(street.graph_gdf[0], GeoDataFrame)
    assert round(displacement(data["point"], street.mask).loc[0, "_distance"]) == 127

    graph_nodes_geom = street.graph_gdf[0].loc[:, "geometry"]
    masked_point = street.mask.to_crs(epsg=4326).loc[0, "geometry"]
    assert round(masked_point.x, 7) in list(graph_nodes_geom.x)
    assert round(masked_point.y, 7) in list(graph_nodes_geom.y)


# STREET
# _nearest_node
# _find_neighbors
# _street_mask
# _apply_street_mask
# run
# run_parallel
