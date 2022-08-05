import geopandas as gpd
from maskmypy import Donut, Donut_MaxK, Donut_Multiply, Street

# Load base data
points = gpd.read_file("tests/test_data/test_points.shp")
populations = gpd.read_file("tests/test_data/test_population.shp")
addresses = gpd.read_file("tests/test_data/test_addresses.shp")


def basic_assertions(masking_class):
    sensitive_length = len(masking_class.sensitive)
    masked_length = len(masking_class.masked)

    assert sensitive_length == masked_length, "Masked data not same length as sensitive data."

    for i in range(masked_length):
        assert not masking_class.sensitive.at[i, "geometry"].intersects(
            masking_class.masked.at[i, "geometry"]
        ), "Sensitive and masked geometries intersect."


def test_donut_random_xy():
    modes = ["uniform", "areal"]
    i = 100
    for mode in modes:
        for i in range(i):
            DonutMasker = Donut(sensitive=points, distribution=mode)
            offset_coords = DonutMasker._random_xy(1, 100)
            assert isinstance(offset_coords[0], float), "Random XY offsets are not valid floats."
            assert isinstance(offset_coords[1], float), "Random XY offsets are not valid floats."
            assert (
                offset_coords[0] > -100 and offset_coords[1] > -100
            ), "Random XY offsets are outside input range."
            assert (
                offset_coords[0] < 100 and offset_coords[1] < 100
            ), "Random XY offsets are outside input range."


def test_seed_reproducibility():
    i = 100
    numbers = []
    for i in range(i):
        DonutMasker = Donut(sensitive=points, seed=123456789)
        offset_coords = DonutMasker._random_xy(1, 100)
        numbers.append(offset_coords)
    assert len(set(numbers)) == 1, "Random numbers are not deterministic given same seed."


def test_seed_randomness():
    i = 100
    numbers = []
    for n in range(i):
        DonutMasker = Donut(sensitive=points, seed=n)
        offset_coords = DonutMasker._random_xy(1, 100)
        numbers.append(offset_coords)
    assert len(set(numbers)) == i, "Random numbers are not unique across seeds."


def test_donut_mask_normal():
    DonutMasker = Donut(
        sensitive=points,
        population=populations,
        population_column="POP",
        addresses=addresses,
        seed=1235151512515,
        distribution="gaussian",
    )
    DonutMasker.execute()
    DonutMasker.displacement_distance()
    basic_assertions(DonutMasker)


def test_donut_mask_max_k():
    DonutMasker = Donut_MaxK(
        sensitive=points,
        population=populations,
        population_column="POP",
        addresses=addresses,
        max_k_anonymity=100,
    )
    DonutMasker.execute()
    DonutMasker.displacement_distance()
    basic_assertions(DonutMasker)


def test_donut_mask_pop_multiplier():
    DonutMasker = Donut_Multiply(
        sensitive=points,
        population=populations,
        population_column="POP",
        addresses=addresses,
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
    basic_assertions(StreetMasker)


def test_street_mask_parallel():
    StreetMasker = Street(
        sensitive=points,
        population=populations,
        population_column="POP",
        addresses=addresses,
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
