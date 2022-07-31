from maskmypy import Donut, Street, Donut_MaxK, Donut_Multiply
import geopandas as gpd

# Load base data
points = gpd.read_file("tests/test_data/test_points.shp")
populations = gpd.read_file("tests/test_data/test_population.shp")
addresses = gpd.read_file("tests/test_data/test_addresses.shp")


def basic_assertions(masking_class):
    sensitive_length = len(masking_class.sensitive)
    masked_length = len(masking_class.masked)

    assert (
        sensitive_length == masked_length
    ), "Masked data not same length as sensitive data."

    for i in range(int(masked_length / 10)):
        assert not masking_class.sensitive.at[i, "geometry"].intersects(
            masking_class.masked.at[i, "geometry"]
        ), "Sensitive and masked geometries intersect."

        assert (
            masking_class.masked.at[i, "distance"] > 0
        ), "Displacement distance is zero."

        assert (
            masking_class.masked.at[i, "distance"] < 10000
        ), "Displacement distance is extremely large."


def test_donut_random_xy():
    modes = ["uniform", "areal"]
    i = 1000
    for mode in modes:
        for i in range(i):
            DonutMasker = Donut(sensitive_gdf=points, distribution=mode)
            offset_coords = DonutMasker._random_xy(1, 100)
            assert isinstance(
                offset_coords[0], float
            ), "Random XY offsets are not valid floats."
            assert isinstance(
                offset_coords[1], float
            ), "Random XY offsets are not valid floats."
            assert (
                offset_coords[0] > -100 and offset_coords[1] > -100
            ), "Random XY offsets are outside input range."
            assert (
                offset_coords[0] < 100 and offset_coords[1] < 100
            ), "Random XY offsets are outside input range."


def test_seed_reproducibility():
    i = 1000
    numbers = []
    for i in range(i):
        DonutMasker = Donut(sensitive_gdf=points, seed=123456789)
        offset_coords = DonutMasker._random_xy(1, 100)
        numbers.append(offset_coords)
    assert (
        len(set(numbers)) == 1
    ), "Random numbers are not deterministic given same seed."


def test_seed_randomness():
    i = 1000
    numbers = []
    for n in range(i):
        DonutMasker = Donut(sensitive_gdf=points, seed=n)
        offset_coords = DonutMasker._random_xy(1, 100)
        numbers.append(offset_coords)
    assert len(set(numbers)) == i, "Random numbers are not unique across seeds."


def test_donut_mask_normal():
    DonutMasker = Donut(
        sensitive_gdf=points,
        population_gdf=populations,
        population_column="POP",
        address_points_gdf=addresses,
        seed=1235151512515,
        distribution="gaussian",
    )
    DonutMasker.execute()
    DonutMasker.displacement_distance()
    basic_assertions(DonutMasker)


def test_donut_mask_max_k():
    DonutMasker = Donut_MaxK(
        sensitive_gdf=points,
        population_gdf=populations,
        population_column="POP",
        address_points_gdf=addresses,
        max_k_anonymity=100,
    )
    DonutMasker.execute()
    DonutMasker.displacement_distance()
    basic_assertions(DonutMasker)


def test_donut_mask_pop_multiplier():
    DonutMasker = Donut_Multiply(
        sensitive_gdf=points,
        population_gdf=populations,
        population_column="POP",
        address_points_gdf=addresses,
        population_multiplier=5,
        max_distance=100,
    )
    DonutMasker.execute()
    DonutMasker.displacement_distance()
    basic_assertions(DonutMasker)
    assert (
        max(DonutMasker.masked["radius_max"]) == 500
    ), "Max radius not scaling with population properly."


def test_street_mask():
    StreetMasker = Street(
        sensitive_gdf=points,
        population_gdf=populations,
        population_column="POP",
        address_points_gdf=addresses,
    )
    StreetMasker.execute()
    StreetMasker.displacement_distance()
    basic_assertions(StreetMasker)


def test_street_mask_parallel():
    StreetMasker = Street(
        sensitive_gdf=points,
        population_gdf=populations,
        population_column="POP",
        address_points_gdf=addresses,
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
