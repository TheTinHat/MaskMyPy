from maskmypy import Donut, Street, Donut_MaxK, Donut_Multiply
import geopandas as gpd


points = gpd.read_file("tests/test_data/test_points.shp")
populations = gpd.read_file("tests/test_data/test_population.shp")
addresses = gpd.read_file("tests/test_data/test_addresses.shp")


def basic_assertions(masking_class):
    sensitive_length = len(masking_class.sensitive)
    masked_length = len(masking_class.masked)

    assert (
        sensitive_length == masked_length
    ), "Masked data not same length as sensitive data"

    for i in range(int(masked_length / 10)):
        assert not masking_class.sensitive.at[i, "geometry"].intersects(
            masking_class.masked.at[i, "geometry"]
        ), "Sensitive and masked geometries intersect"

        assert (
            masking_class.masked.at[i, "distance"] > 0
        ), "Displacement distance is zero"


def test_donut_mask_normal():
    DonutMasker = Donut(
        sensitive_gdf=points,
        population_gdf=populations,
        population_column="POP",
        address_points_gdf=addresses,
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
    ), "Max radius not scaling with population properly"


# def test_donut_mask_contained():
#     DonutMasker = Donut(
#         sensitive_gdf=points, container_gdf=populations, max_distance=1000, max_tries=1000
#     )
#     DonutMasker.execute()
#     DonutMasker.displacement_distance()
#     basic_assertions(DonutMasker)

#     masked_join = gpd.sjoin(DonutMasker.masked, populations, how="left")
#     for index, row in DonutMasker.sensitive.iterrows():
#         print(row)
#         assert (
#             row["index_right"]
#             == masked_join.at[index, "index_right"]
#         ), "Containment error. Sensitive and masked containment areas do not match."


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
    StreetMasker.masked.to_file("street_output.shp")


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
    test_street_mask()
    test_street_mask_parallel()
    test_donut_mask_max_k()
    test_donut_mask_normal()
    test_donut_mask_pop_multiplier()
