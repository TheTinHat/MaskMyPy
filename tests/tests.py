import geopandas as gpd
import pytest
from maskmypy import Donut, Donut_MaxK, Donut_Multiply, Street
from numpy import random

# Load base data
points = gpd.read_file("tests/test_data/100_test_points.shp")
populations = gpd.read_file("tests/test_data/test_population.shp")
addresses = gpd.read_file("tests/test_data/1000_test_addresses.shp")

rng = random.default_rng(seed=12345)


def gen_seeds(n):
    return rng.integers(low=10000, high=100000, size=n)


def basic_assertions(masking_class):
    sensitive_length = len(masking_class.sensitive)
    masked_length = len(masking_class.masked)

    assert sensitive_length == masked_length, "Masked data not same length as sensitive data."

    for i in range(masked_length):
        assert not masking_class.sensitive.at[i, "geometry"].intersects(
            masking_class.masked.at[i, "geometry"]
        ), "Sensitive and masked geometries intersect."


@pytest.mark.parametrize("distributions", ["uniform", "gaussian", "areal"])
@pytest.mark.parametrize("seeds", gen_seeds(5))
def test_donut_mask_normal(distributions, seeds):
    DonutMasker = Donut(
        sensitive=points,
        seed=seeds,
        distribution=distributions,
    )
    DonutMasker.execute()
    DonutMasker.displacement_distance()
    basic_assertions(DonutMasker)


@pytest.mark.parametrize("distributions", ["uniform", "gaussian", "areal"])
@pytest.mark.parametrize("seeds", gen_seeds(5))
def test_donut_mask_contained(distributions, seeds):
    DonutMasker = Donut(
        sensitive=points, container=populations, distribution=distributions, seed=seeds
    )
    DonutMasker.execute()
    DonutMasker.displacement_distance()
    basic_assertions(DonutMasker)
    assert DonutMasker.masked["CONTAINED"].min() == 1, "Points were not contained."


@pytest.mark.parametrize("distributions", ["uniform", "gaussian", "areal"])
def test_donut_mask_max_k(distributions):
    DonutMasker = Donut_MaxK(
        sensitive=points,
        population=populations,
        population_column="POP",
        distribution=distributions,
        addresses=addresses,
        max_k_anonymity=20,
        ratio=0.1,
    )
    DonutMasker.execute()
    DonutMasker.displacement_distance()
    DonutMasker.k_anonymity_estimate()
    basic_assertions(DonutMasker)


@pytest.mark.parametrize("distributions", ["uniform", "gaussian", "areal"])
def test_donut_mask_pop_multiplier(distributions):
    DonutMasker = Donut_Multiply(
        sensitive=points,
        population=populations,
        population_column="POP",
        distribution=distributions,
        population_multiplier=5,
        max_distance=100,
    )
    DonutMasker.execute()
    DonutMasker.displacement_distance()
    basic_assertions(DonutMasker)


def test_street_mask():
    StreetMasker = Street(
        sensitive=points,
        population=populations,
        population_column="POP",
        addresses=addresses,
    )
    StreetMasker.execute()
    StreetMasker.displacement_distance()
    StreetMasker.k_anonymity_actual()
    basic_assertions(StreetMasker)


def test_street_mask_parallel():
    StreetMasker = Street(
        sensitive=points,
    )
    StreetMasker.execute(parallel=True)
    StreetMasker.displacement_distance()
    basic_assertions(StreetMasker)


if __name__ == "__main__":
    test_donut_random_xy()
    test_seed_reproducibility()
    test_seed_randomness()
    test_street_mask()
    test_street_mask_parallel()
    test_donut_mask_max_k()
    test_donut_mask_normal()
    test_donut_mask_pop_multiplier()
