import geopandas as gpd
import pytest
from maskmypy import Donut, Donut_MaxK, Donut_Multiply, Street
from numpy import random
from shapely.geometry import Point
from scipy.stats import normaltest

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
    dubious_donut = Donut(data["point"], population=data["population"])
    assert dubious_donut.secret.crs == dubious_donut.population.crs
    with pytest.raises(AssertionError):
        assert Donut(data["point"], population=data["population"].to_crs(4326))


def test_load_container(data):
    dubious_donut = Donut(data["point"], container=data["container"])
    assert dubious_donut.secret.crs == dubious_donut.container.crs
    with pytest.raises(AssertionError):
        assert Donut(data["point"], container=data["container"].to_crs(4326))


def test_load_address(data):
    dubious_donut = Donut(data["point"], address=data["address"])
    assert dubious_donut.secret.crs == dubious_donut.address.crs
    with pytest.raises(AssertionError):
        assert Donut(data["point"], address=data["address"].to_crs(4326))


def test_crop(data):
    dubious_donut = Donut(data["point"])
    dubious_crop = dubious_donut._crop(data["address"], data["test_circle"])
    assert len(dubious_crop) < len(data["address"])
    assert any(dubious_crop.intersects(data["test_circle"].loc[0, "geometry"]))


def test_crop_single_point(data):
    dubious_donut = Donut(data["point"])
    dubious_crop = dubious_donut._crop(data["address"], data["point"])
    assert len(dubious_crop) == len(data["address"])


def test_displacement(data):
    distance = int(data["point"].distance(data["test_point"]))
    assert distance == 60


def test_estimate_k(data):
    dubious_donut = Donut(
        data["point"], population=data["population"], max_distance=20, ratio=0.99999
    )
    dubious_donut.run()
    dubious_donut.estimate_k()
    assert dubious_donut.mask.loc[0, "k_est"] == 4.0

    dubious_donut.max_distance = 50
    dubious_donut.run()
    dubious_donut.estimate_k()
    assert dubious_donut.mask.loc[0, "k_est"] == 25.0


def test_disaggregate_population(data):
    dubious_donut = Donut(data["point"], population=data["population"])
    dubious_donut.population["_pop_area"] = dubious_donut.population.area

    circle = data["point"].copy()
    circle.geometry = circle.geometry.buffer(50)
    dubious_disaggregate = dubious_donut._disaggregate_population(circle)
    assert int(dubious_disaggregate.loc[0, "_pop_adjusted"]) == 25

    circle = data["point"].copy()
    circle.geometry = circle.geometry.buffer(75)
    dubious_disaggregate = dubious_donut._disaggregate_population(circle)
    assert int(dubious_disaggregate.loc[0, "_pop_adjusted"]) == 56

    circle = data["point"].copy()
    circle.geometry = circle.geometry.buffer(100)
    dubious_disaggregate = dubious_donut._disaggregate_population(circle)
    assert int(dubious_disaggregate.loc[0, "_pop_adjusted"]) == 100


def test_calculate_k_no_distance(data):
    dubious_donut = Donut(
        data["point"],
        address=data["address"],
        max_distance=1,
        ratio=0.99999,
        seed=data["seeds"][0],
    )
    dubious_donut.run()
    dubious_donut.calculate_k()
    assert int(dubious_donut.mask.loc[0, "k_calc"]) == 0


def test_calculate_k(data):
    dubious_donut = Donut(
        data["point"],
        address=data["address"],
        max_distance=100,
        ratio=0.99999,
        seed=data["seeds"][0],
    )
    dubious_donut.run()
    dubious_donut.calculate_k()
    assert int(dubious_donut.mask.loc[0, "k_calc"]) == 39


def test_containment_false(data):
    dubious_donut = Donut(data["point"], container=data["test_circle"], max_tries=0)
    dubious_donut.try_count = 0
    dubious_donut.mask = data["test_point"]
    dubious_donut._containment(data["test_point"])
    assert dubious_donut.mask.loc[0, "CONTAINED"] == 0


def test_containment_true(data):
    dubious_donut = Donut(data["point"], container=data["test_circle"])
    dubious_donut.try_count = 0
    dubious_donut.mask = data["point"]
    dubious_donut._containment(data["point"])
    assert dubious_donut.mask.loc[0, "CONTAINED"] == 1


def test_seed_reproducibility(data):
    numbers = []
    for i in range(100):
        dubious_donut = Donut(data["point"], seed=data["seeds"][0])
        offset_coords = dubious_donut._random_xy(1, 100)
        numbers.append(offset_coords)
    assert len(set(numbers)) == 1


def test_seed_randomness(data):
    numbers = []
    for seed in data["seeds"]:
        dubious_donut = Donut(data["point"], seed=seed)
        offset_coords = dubious_donut._random_xy(1, 100)
        numbers.append(offset_coords)
    assert len(set(numbers)) == len(data["seeds"])


@pytest.mark.parametrize("distribution", ["uniform", "areal"])
def test_random_xy(data, distribution):
    for i in range(100):
        dubious_donut = Donut(data["point"], distribution=distribution)
        offset_coords = dubious_donut._random_xy(1, 100)
        assert isinstance(offset_coords[0], float)
        assert isinstance(offset_coords[1], float)
        assert offset_coords[0] > -100 and offset_coords[1] > -100
        assert offset_coords[0] < 100 and offset_coords[1] < 100


def test_random_xy_gaussian(data):
    distance_list = []
    for seed in data["seeds"]:
        dubious_donut = Donut(
            data["point"], distribution="gaussian", max_distance=100, ratio=0, seed=seed
        )
        dubious_donut.run()
        dubious_donut.displacement()
        distance_list.append(dubious_donut.mask.loc[0, "_distance"])
    assert normaltest(distance_list)[1] > 0.1


def test_donut_set_radii(data):
    dubious_donut = Donut(data["point"], max_distance=100, ratio=0.1)
    dubious_donut.mask = data["point"]
    dubious_donut._set_radii()
    assert dubious_donut.mask.loc[0, "_r_min"] == 10
    assert dubious_donut.mask.loc[0, "_r_max"] == 100


def test_donut_container(data):
    dubious_donut = Donut(
        data["point"],
        max_distance=900,
        ratio=0.01,
        container=data["population"],
        seed=data["seeds"][0],
    )
    dubious_donut.run()
    assert dubious_donut.try_count > 1
    assert dubious_donut.mask.loc[0, "CONTAINED"] == 1


def test_donut_maxk_set_radii(data):
    dubious_donut = Donut_MaxK(
        data["point"], population=data["population"], max_k_anonymity=100, ratio=0.1
    )
    dubious_donut.mask = dubious_donut.secret
    dubious_donut._set_radii()
    assert round(dubious_donut.mask.loc[0, "_r_max"]) == 100
    assert round(dubious_donut.mask.loc[0, "_r_min"]) == 32


def test_donut_multiply_set_radii(data):
    dubious_donut = Donut_Multiply(
        data["point"],
        population=data["population"],
        population_multiplier=5,
        max_distance=100,
        ratio=0.1,
    )
    dubious_donut.mask = dubious_donut.secret.copy()
    dubious_donut._set_radii()
    assert dubious_donut.mask.loc[0, "_r_max"] == 500
    assert dubious_donut.mask.loc[0, "_r_min"] == 50


def test_displacement_map(data):
    dubius_donut = Donut(data["point"], seed=data["seeds"][0])
    dubius_donut.run()
    dubius_donut.map_displacement("tests/results/displacement_map_test_image.png")


def test_get_osm(data):
    dubious_street = Street(data["point"])


# STREET
# _get_osm
# _nearest_node
# _find_neighbors
# _street_mask
# _apply_street_mask
# run
# run_parallel
