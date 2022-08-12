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

    addresses = gpd.GeoDataFrame(columns=["geometry"], crs=crs)
    for i in range(population.loc[0, "pop"]):
        contained = False
        while contained is False:
            address = Point(
                rng.uniform(low=bbox[0], high=bbox[2]), rng.uniform(low=bbox[1], high=bbox[3])
            )
            if address.intersects(population.loc[0, "geometry"]):
                addresses.loc[i, "geometry"] = address
                contained = True
    return {
        "point": point,
        "population": population,
        "addresses": addresses,
        "container": container,
        "test_point": test_point,
        "test_circle": test_circle,
        "seeds": seeds,
    }


def test_load_population(data):
    dubious_donut = Donut(data["point"], population=data["population"])
    assert dubious_donut.sensitive.crs == dubious_donut.population.crs
    with pytest.raises(AssertionError):
        assert Donut(data["point"], population=data["population"].to_crs(4326))


def test_load_container(data):
    dubious_donut = Donut(data["point"], container=data["container"])
    assert dubious_donut.sensitive.crs == dubious_donut.container.crs
    with pytest.raises(AssertionError):
        assert Donut(data["point"], container=data["container"].to_crs(4326))


def test_load_addresses(data):
    dubious_donut = Donut(data["point"], addresses=data["addresses"])
    assert dubious_donut.sensitive.crs == dubious_donut.addresses.crs
    with pytest.raises(AssertionError):
        assert Donut(data["point"], addresses=data["addresses"].to_crs(4326))


def test_crop(data):
    dubious_donut = Donut(data["point"])
    dubious_crop = dubious_donut._crop(data["addresses"], data["test_circle"])
    assert len(dubious_crop) < len(data["addresses"])
    assert any(dubious_crop.intersects(data["test_circle"].loc[0, "geometry"]))


def test_crop_single_point(data):
    dubious_donut = Donut(data["point"])
    dubious_crop = dubious_donut._crop(data["addresses"], data["point"])
    assert len(dubious_crop) == len(data["addresses"])


def test_displacement_distance(data):
    distance = int(data["point"].distance(data["test_point"]))
    assert distance == 60


def test_k_anonymity_estimate(data):
    dubious_donut = Donut(
        data["point"], population=data["population"], max_distance=20, ratio=0.99999
    )
    dubious_donut.execute()
    dubious_donut.k_anonymity_estimate()
    assert dubious_donut.masked.loc[0, "k_est"] == 4.0

    dubious_donut.max_distance = 50
    dubious_donut.execute()
    dubious_donut.k_anonymity_estimate()
    assert dubious_donut.masked.loc[0, "k_est"] == 25.0


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


def test_k_anonymity_actual_no_distance(data):
    dubious_donut = Donut(
        data["point"],
        addresses=data["addresses"],
        max_distance=1,
        ratio=0.99999,
        seed=data["seeds"][0],
    )
    dubious_donut.execute()
    dubious_donut.k_anonymity_actual()
    assert int(dubious_donut.masked.loc[0, "k_actual"]) == 0


def test_k_anonymity_actual(data):
    dubious_donut = Donut(
        data["point"],
        addresses=data["addresses"],
        max_distance=100,
        ratio=0.99999,
        seed=data["seeds"][0],
    )
    dubious_donut.execute()
    dubious_donut.k_anonymity_actual()
    assert int(dubious_donut.masked.loc[0, "k_actual"]) == 39


def test_containment_false(data):
    dubious_donut = Donut(data["point"], container=data["test_circle"], max_tries=0)
    dubious_donut.masked = data["test_point"]
    dubious_donut._containment(data["test_point"])
    assert dubious_donut.masked.loc[0, "CONTAINED"] == 0


def test_containment_true(data):
    dubious_donut = Donut(data["point"], container=data["test_circle"])
    dubious_donut.masked = data["point"]
    dubious_donut._containment(data["point"])
    assert dubious_donut.masked.loc[0, "CONTAINED"] == 1


def test_seed_reproducibility(data):
    numbers = []
    for i in range(100):
        dubious_donut = Donut(data["point"], seed=data["seeds"][0])
        offset_coords = dubious_donut._random_xy(1, 100)
        numbers.append(offset_coords)
    assert len(set(numbers)) == 1, "Random numbers are not deterministic given same seed."


def test_seed_randomness(data):
    numbers = []
    for seed in data["seeds"]:
        dubious_donut = Donut(data["point"], seed=seed)
        offset_coords = dubious_donut._random_xy(1, 100)
        numbers.append(offset_coords)
    assert len(set(numbers)) == len(data["seeds"]), "Random numbers are not unique across seeds."


@pytest.mark.parametrize("distribution", ["uniform", "areal"])
def test_random_xy(data, distribution):
    for i in range(100):
        dubious_donut = Donut(data["point"], distribution=distribution)
        offset_coords = dubious_donut._random_xy(1, 100)
        assert isinstance(offset_coords[0], float), "Random XY offsets are not valid floats."
        assert isinstance(offset_coords[1], float), "Random XY offsets are not valid floats."
        assert (
            offset_coords[0] > -100 and offset_coords[1] > -100
        ), "Random XY offsets are outside input range."
        assert (
            offset_coords[0] < 100 and offset_coords[1] < 100
        ), "Random XY offsets are outside input range."


def test_random_xy_gaussian(data):
    distance_list = []
    for seed in data["seeds"]:
        dubious_donut = Donut(
            data["point"], distribution="gaussian", max_distance=100, ratio=0, seed=seed
        )
        dubious_donut.execute()
        dubious_donut.displacement_distance()
        distance_list.append(dubious_donut.masked.loc[0, "_displace_dist"])
    assert normaltest(distance_list)[1] > 0.05


def test_donut_find_radii(data):
    dubious_donut = Donut(data["point"], max_distance=100, ratio=0.1)
    dubious_donut.masked = data["point"]
    dubious_donut._find_radii()
    assert dubious_donut.masked.loc[0, "_radius_min"] == 10
    assert dubious_donut.masked.loc[0, "_radius_max"] == 100


def test_donut_container(data):
    dubious_donut = Donut(
        data["point"],
        max_distance=900,
        ratio=0.01,
        container=data["population"],
        seed=data["seeds"][0],
    )
    dubious_donut.execute()
    assert dubious_donut.try_count > 1
    assert dubious_donut.masked.loc[0, "CONTAINED"] == 1


def test_donut_maxk_find_radii(data):
    dubious_donut = Donut_MaxK(
        data["point"], population=data["population"], max_k_anonymity=100, ratio=0.1
    )
    dubious_donut.masked = dubious_donut.sensitive
    dubious_donut._find_radii()
    assert round(dubious_donut.masked.loc[0, "_radius_max"]) == 100
    assert round(dubious_donut.masked.loc[0, "_radius_min"]) == 32


def test_donut_multiply_find_radii(data):
    dubious_donut = Donut_Multiply(
        data["point"],
        population=data["population"],
        population_multiplier=5,
        max_distance=100,
        ratio=0.1,
    )
    dubious_donut.masked = dubious_donut.sensitive.copy()
    dubious_donut._find_radii()
    assert dubious_donut.masked.loc[0, "_radius_max"] == 500
    assert dubious_donut.masked.loc[0, "_radius_min"] == 50


# STREET
# _get_osm
# _nearest_node
# _find_neighbors
# _street_mask
# _apply_street_mask
# execute
# execute_parallel
