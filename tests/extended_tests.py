import geopandas as gpd
import pytest
from maskmypy import Donut, Donut_MaxK, Donut_Multiply, Street, map_displacement
from numpy import random

# Load base data
points = gpd.read_file("tests/test_data/100_test_points.shp")
populations = gpd.read_file("tests/test_data/test_population.shp")
address = gpd.read_file("tests/test_data/1000_test_addresses.shp")

i = 10

rng = random.default_rng(seed=12345)


def gen_seeds(n):
    return rng.integers(low=10000, high=100000, size=n)


@pytest.mark.parametrize("distributions", ["uniform", "gaussian", "areal"])
@pytest.mark.parametrize("seeds", gen_seeds(i))
def test_donut_mask_normal(distributions, seeds):
    DonutMasker = Donut(
        secret=points,
        seed=seeds,
        distribution=distributions,
    )
    DonutMasker.run()


@pytest.mark.parametrize("distributions", ["uniform", "gaussian", "areal"])
@pytest.mark.parametrize("seeds", gen_seeds(i))
def test_donut_mask_contained(distributions, seeds):
    DonutMasker = Donut(
        secret=points, container=populations, distribution=distributions, seed=seeds
    )
    DonutMasker.run()
    assert DonutMasker.mask["CONTAINED"].min() == 1


@pytest.mark.parametrize("distributions", ["uniform", "gaussian", "areal"])
def test_donut_mask_max_k(distributions):
    DonutMasker = Donut_MaxK(
        secret=points,
        population=populations,
        pop_col="POP",
        distribution=distributions,
        address=address,
        max_k_anonymity=20,
        min_k_anonymity=2,
    )
    DonutMasker.run()


@pytest.mark.parametrize("distributions", ["uniform", "gaussian", "areal"])
def test_donut_mask_pop_multiplier(distributions):
    DonutMasker = Donut_Multiply(
        secret=points,
        population=populations,
        pop_col="POP",
        distribution=distributions,
        population_multiplier=5,
        max_distance=100,
        min_distance=10,
    )
    DonutMasker.run()


def test_map_displacement():
    map_displacement(
        points,
        Donut(points, seed=gen_seeds(1)).run(),
        "tests/results/displacement_map_test_extended.png",
        address,
    )


def test_street_mask():
    StreetMasker = Street(
        secret=points,
        population=populations,
        pop_col="POP",
        address=address,
    )
    StreetMasker.run()


def test_street_mask_parallel():
    StreetMasker = Street(
        secret=points,
    )
    StreetMasker.run(parallel=True)
