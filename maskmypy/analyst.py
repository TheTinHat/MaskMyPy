from collections import namedtuple
from geopandas import GeoDataFrame, sjoin
from shapely.ops import nearest_points

from .candidate import Candidate
from .tools import validate_geom_type


def displacement(
    gdf_a: GeoDataFrame, gdf_b: GeoDataFrame, colname: str = "_distance"
) -> GeoDataFrame:
    gdf_b[colname] = gdf_b.geometry.distance(gdf_a.geometry)
    return gdf_b


def estimate_k(
    sensitive: GeoDataFrame,
    candidate_gdf: GeoDataFrame,
    population_gdf: GeoDataFrame,
    pop_col: str = "pop",
) -> GeoDataFrame:
    candidate_columns = candidate_gdf.columns

    if validate_geom_type(population_gdf, "Point"):
        candidate_k = _estimate_k_from_addresses(sensitive, candidate_gdf, population_gdf)

    elif validate_geom_type(population_gdf, "Polygon", "MultiPolygon"):
        candidate_k = _estimate_k_from_polygons(sensitive, candidate_gdf, population_gdf, pop_col)

    candidate_columns += ["k_anonymity"]
    candidate_k = candidate_k[candidate_k.columns.intersection(candidate_columns)]
    return candidate_k


def _estimate_k_from_polygons(
    sensitive_gdf: GeoDataFrame,
    candidate_gdf: GeoDataFrame,
    population_gdf: GeoDataFrame,
    pop_col: str = "pop",
) -> GeoDataFrame:
    pop_col_adjusted = "_".join([pop_col, "adjusted"])
    candidate_gdf["k_anonymity"] = (
        displacement(sensitive_gdf, candidate_gdf)
        .assign(geometry=lambda x: x.geometry.buffer(x["_distance"]), axis=1)
        .pipe(_disaggregate, gdf_b=population_gdf, gdf_b_col=pop_col)
        .groupby("_index_2")[pop_col_adjusted]
        .sum()
        .round()
    )
    return candidate_gdf


def _estimate_k_from_addresses(
    sensitive_gdf: GeoDataFrame, candidate_gdf: GeoDataFrame, address: GeoDataFrame
) -> GeoDataFrame:
    candidate_gdf_tmp = displacement(sensitive_gdf, candidate_gdf).assign(
        geometry=lambda x: x.buffer(x["_distance"])
    )
    candidate_gdf["k_anonymity"] = (
        sjoin(address, candidate_gdf_tmp, how="left", rsuffix="candidate")
        .groupby("index_candidate")
        .size()
    )
    candidate_gdf.fillna({"k_anonymity": 0}, inplace=True)
    return candidate_gdf


def _disaggregate(gdf_a: GeoDataFrame, gdf_b: GeoDataFrame, gdf_b_col: str) -> GeoDataFrame:
    new_col = "_".join([gdf_b_col, "adjusted"])
    gdf_b["_b_area"] = gdf_b.geometry.area
    gdf = sjoin(gdf_a, gdf_b, how="left", rsuffix="b").rename_axis("_index_2").reset_index()
    gdf.geometry = gdf.apply(
        lambda x: x.geometry.intersection(gdf_b.at[x["index_b"], "geometry"]),
        axis=1,
    )
    gdf["_intersected_area"] = gdf.geometry.area

    for i, _ in enumerate(gdf.index):
        fragments = gdf.loc[gdf["_index_2"] == i, :]
        for index, row in fragments.iterrows():
            area_pct = row["_intersected_area"] / row["_b_area"]
            gdf.at[index, new_col] = row[gdf_b_col] * area_pct
    return gdf


def central_drift(gdf_a: GeoDataFrame, gdf_b: GeoDataFrame) -> float:
    centroid_a = gdf_a.dissolve().centroid
    centroid_b = gdf_b.dissolve().centroid
    return float(centroid_a.distance(centroid_b))


def k_satisfaction(gdf: GeoDataFrame, min_k: int, k_col: str = "k_anonymity") -> float:
    return gdf.loc[gdf[k_col] >= min_k, k_col].count() / gdf[k_col].count()


def nearest_neighbor(gdf: GeoDataFrame, summary: bool = True) -> namedtuple:
    gdf_tmp = gdf.copy(deep=True)
    gdf_tmp["nn_geom"] = gdf_tmp.apply(
        lambda x: nearest_points(
            x.geometry, gdf_tmp.loc[gdf_tmp.geometry != x.geometry].dissolve().iloc[0].geometry
        )[1],
        axis=1,
    )

    gdf_tmp["nn_distance"] = gdf_tmp.geometry.distance(gdf_tmp["nn_geom"].set_crs(gdf.crs))

    if not summary:
        return gdf_tmp
    else:
        NeighborSummary = namedtuple("NearestNeighborStats", ["mean", "min", "max"])
        return NeighborSummary(
            gdf_tmp["nn_distance"].mean(),
            gdf_tmp["nn_distance"].min(),
            gdf_tmp["nn_distance"].max(),
        )


def compare_candidates(sensitive_gdf: GeoDataFrame, *candidates: Candidate):
    for candidate in candidates:
        pass
