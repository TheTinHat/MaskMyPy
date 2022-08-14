import geopandas as gpd
import pytest
from maskmypy import Donut, Donut_MaxK, Donut_Multiply, Street
from numpy import random

# Load base data
points = gpd.read_file("tests/test_data/100_test_points.shp")
populations = gpd.read_file("tests/test_data/test_population.shp")
address = gpd.read_file("tests/test_data/1000_test_addresses.shp")

i = 10

rng = random.default_rng(seed=12345)


def gen_seeds(n):
    return rng.integers(low=10000, high=100000, size=n)


def basic_assertions(masking_class):
    input_length = len(masking_class.input)
    mask_length = len(masking_class.mask)

    assert input_length == mask_length

    for i in range(mask_length):
        assert not masking_class.input.at[i, "geometry"].intersects(
            masking_class.mask.at[i, "geometry"]
        )


@pytest.mark.parametrize("distributions", ["uniform", "gaussian", "areal"])
@pytest.mark.parametrize("seeds", gen_seeds(i))
def test_donut_mask_normal(distributions, seeds):
    DonutMasker = Donut(
        input=points,
        seed=seeds,
        distribution=distributions,
    )
    DonutMasker.run()
    DonutMasker.displacement_distance()
    basic_assertions(DonutMasker)


@pytest.mark.parametrize("distributions", ["uniform", "gaussian", "areal"])
@pytest.mark.parametrize("seeds", gen_seeds(i))
def test_donut_mask_contained(distributions, seeds):
    DonutMasker = Donut(
        input=points, container=populations, distribution=distributions, seed=seeds
    )
    DonutMasker.run()
    DonutMasker.displacement_distance()
    basic_assertions(DonutMasker)
    assert DonutMasker.mask["CONTAINED"].min() == 1


@pytest.mark.parametrize("distributions", ["uniform", "gaussian", "areal"])
def test_donut_mask_max_k(distributions):
    DonutMasker = Donut_MaxK(
        input=points,
        population=populations,
        pop_col="POP",
        distribution=distributions,
        address=address,
        max_k_anonymity=20,
        ratio=0.1,
    )
    DonutMasker.run()
    DonutMasker.displacement_distance()
    DonutMasker.k_anonymity_estimate()
    basic_assertions(DonutMasker)


@pytest.mark.parametrize("distributions", ["uniform", "gaussian", "areal"])
def test_donut_mask_pop_multiplier(distributions):
    DonutMasker = Donut_Multiply(
        input=points,
        population=populations,
        pop_col="POP",
        distribution=distributions,
        population_multiplier=5,
        max_distance=100,
    )
    DonutMasker.run()
    DonutMasker.displacement_distance()
    basic_assertions(DonutMasker)


def test_street_mask():
    StreetMasker = Street(
        input=points,
        population=populations,
        pop_col="POP",
        address=address,
    )
    StreetMasker.run()
    StreetMasker.displacement_distance()
    StreetMasker.k_anonymity_actual()
    basic_assertions(StreetMasker)


def test_street_mask_parallel():
    StreetMasker = Street(
        input=points,
    )
    StreetMasker.run(parallel=True)
    StreetMasker.displacement_distance()
    basic_assertions(StreetMasker)
