import geopandas as gpd
from .tools import validate_geom_type
from pointpats import PointPattern, k_test
import numpy as np

# from matplotlib import
import pandas as pd


def displacement(gdf, candidate_gdf, colname="_distance"):
    candidate_gdf[colname] = candidate_gdf.geometry.distance(gdf.geometry)
    return candidate_gdf


def estimate_k(sensitive_gdf, candidate_gdf, population_gdf, pop_col="pop"):
    candidate_columns = candidate_gdf.columns

    if validate_geom_type(population_gdf, "Point"):
        candidate_k = _estimate_k_from_addresses(
            sensitive_gdf, candidate_gdf, population_gdf, pop_col
        )

    elif validate_geom_type(population_gdf, "Polygon", "MultiPolygon"):
        candidate_k = _estimate_k_from_polygons(sensitive_gdf, candidate_gdf, population_gdf)

    candidate_columns += ["k_anonymity"]
    candidate_k = candidate_k[candidate_k.columns.intersection(candidate_columns)]
    return candidate_k


def _estimate_k_from_polygons(sensitive_gdf, candidate_gdf, population_gdf, pop_col="pop"):
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


def _estimate_k_from_addresses(sensitive_gdf, candidate_gdf, address):
    candidate_gdf_tmp = displacement(sensitive_gdf, candidate_gdf).assign(
        geometry=lambda x: x.buffer(x["_distance"])
    )
    candidate_gdf["k_anonymity"] = (
        gpd.sjoin(address, candidate_gdf_tmp, how="left", rsuffix="candidate")
        .groupby("index_candidate")
        .size()
    )
    candidate_gdf.fillna({"k_anonymity": 0}, inplace=True)
    return candidate_gdf


def _disaggregate(gdf_a, gdf_b, gdf_b_col):
    new_col = "_".join([gdf_b_col, "adjusted"])
    gdf_b["_b_area"] = gdf_b.geometry.area
    gdf = gpd.sjoin(gdf_a, gdf_b, how="left", rsuffix="b").rename_axis("_index_2").reset_index()
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


def mean_center_drift(gdf_a, gdf_b):
    centroid_a = gdf_a.dissolve().centroid
    centroid_b = gdf_b.dissolve().centroid
    return float(centroid_a.distance(centroid_b))


def k_satisfaction(gdf, k, k_col="k_anonymity"):
    return gdf.loc[gdf[k_col] > k, k_col].count() / gdf[k_col].count()


def ripleys_k(gdf, dist_min, dist_max, step_count=None, step_width=None, comparison_kdf=None):
    if step_width:
        step_count = int((dist_max - dist_min) / step_width) + 1

    k_results = k_test(
        np.array(list(zip(gdf.geometry.x, gdf.geometry.y))),
        keep_simulations=True,
        support=(dist_min, dist_max, step_count),
    )

    kdf = pd.DataFrame(
        {
            "distance": k_results.support,
            "statistic": k_results.statistic,
            "pvalue": k_results.pvalue,
        }
    )

    if isinstance(comparison_kdf, pd.DataFrame):
        kdf["difference"] = kdf["statistic"] - comparison_kdf["statistic"]

    return kdf


def nearest_neighbor_stats(gdf):
    point_list = list(zip(gdf.geometry.x, gdf.geometry.y))
    pp = PointPattern(point_list)
    return {"min": pp.min_nnd, "max": pp.max_nnd, "mean": pp.mean_nnd}


def compare_candidates(sensitive_gdf, *candidates):
    for candidate in candidates:
        pass
