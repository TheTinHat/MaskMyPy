import geopandas as gpd
import pytest
from maskmypy import Donut, Donut_MaxK, Donut_Multiply, Street
from numpy import random
from shapely.geometry import Point

"""   INITIALIZATION   """


@pytest.fixture()
def data():
    rng = random.default_rng(seed=0)
    crs = 26910
    point = gpd.GeoDataFrame(
        {"geometry": [Point(-122.87289, 49.30314)]}, index=[0], crs=4326
    ).to_crs(crs)
    test_point = gpd.GeoDataFrame(
        {"geometry": Point(-122.87290, 49.30260)}, index=[0], crs=4326
    ).to_crs(crs)
    population = gpd.GeoDataFrame({"geometry": point.buffer(100), "pop": 100}, crs=crs)
    test_circle = gpd.GeoDataFrame({"geometry": point.buffer(20)}, crs=crs)
    container = population.copy()
    bbox = population.total_bounds
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
        data["point"], population=data["population"], max_distance=20, ratio=0.99999999
    )
    dubious_donut.execute()
    dubious_donut.k_anonymity_estimate()
    print(dubious_donut.masked)


# def k_anonymity_estimate(self, population="", population_column="pop"):
#     """Estimates k-anoynmity based on population data."""
#     if not isinstance(self.population, GeoDataFrame):
#         self._load_population(population, population_column)
#     assert isinstance(self.sensitive, GeoDataFrame), "Sensitive points geodataframe is missing"
#     assert isinstance(self.masked, GeoDataFrame), "Data has not yet been masked"
#     assert isinstance(self.population, GeoDataFrame), "Population geodataframe is missing"
#     self.population["_pop_area"] = self.population.area
#     if "_displace_dist" not in self.masked.columns:
#         self.displacement_distance()
#     masked_temp = self.masked.copy()
#     masked_temp["geometry"] = masked_temp.apply(
#         lambda x: x.geometry.buffer(x["_displace_dist"]), axis=1
#     )
#     masked_temp = self._disaggregate_population(masked_temp)
#     for i in range(len(self.masked.index)):
#         self.masked.at[i, "k_est"] = int(
#             masked_temp.loc[masked_temp["_index_2"] == i, "_pop_adjusted"].sum() - 1
#         )
#     return self.masked


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


# def _disaggregate_population(self, target):
#     """Used for estimating k-anonymity. Disaggregates population within
#     buffers based on population polygon data"""
#     target = target.copy()
#     target = sjoin(target, self.population, how="left", rsuffix="right")
#     target["_index_2"] = target.index
#     target.index = range(len(target.index))
#     target["geometry"] = target.apply(
#         lambda x: x["geometry"].intersection(self.population.at[x["index_right"], "geometry"]),
#         axis=1,
#     )
#     target["_intersected_area"] = target["geometry"].area
#     for i in range(len(target.index)):
#         polygon_fragments = target.loc[target["_index_2"] == i, :]
#         for index, row in polygon_fragments.iterrows():
#             area_pct = row["_intersected_area"] / row["_pop_area"]
#             target.at[index, "_pop_adjusted"] = row[self.pop_column] * area_pct
#     return target

# k_anonymity_estimate
# k_anonymity_actual
# _disaggregate_population
# _containment


# DONUT
# _random_xy
# _find_radii
# _mask_within_container
# execute


# DONUT_MAXK
# _find_radii


# DONU
# T_MULTIPLY
# _find_radii


# STREET
# _get_osm
# _nearest_node
# _find_neighbors
# _street_mask
# _apply_street_mask
# execute
# execute_parallel
