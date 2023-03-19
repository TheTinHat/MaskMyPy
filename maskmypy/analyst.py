from collections import namedtuple

from geopandas import GeoDataFrame, sjoin
from numpy import array
from pointpats import PointPattern, k_test
from pointpats.distance_statistics import KtestResult
from shapely.ops import nearest_points
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axis import Axis
from .candidate import Candidate
from .tools import validate_geom_type


def displacement(
    gdf_a: GeoDataFrame, gdf_b: GeoDataFrame, colname: str = "_distance"
) -> GeoDataFrame:
    gdf_b[colname] = gdf_b.geometry.distance(gdf_a.geometry)
    return gdf_b


def estimate_k(
    sensitive_gdf: GeoDataFrame,
    candidate_gdf: GeoDataFrame,
    population_gdf: GeoDataFrame,
    pop_col: str = "pop",
) -> GeoDataFrame:
    candidate_columns = candidate_gdf.columns

    if validate_geom_type(population_gdf, "Point"):
        candidate_k = _estimate_k_from_addresses(sensitive_gdf, candidate_gdf, population_gdf)

    elif validate_geom_type(population_gdf, "Polygon", "MultiPolygon"):
        candidate_k = _estimate_k_from_polygons(
            sensitive_gdf, candidate_gdf, population_gdf, pop_col
        )

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


def k_satisfaction(gdf: GeoDataFrame, min_k: int, k_col: str = "k_anonymity") -> float:
    return gdf.loc[gdf[k_col] >= min_k, k_col].count() / gdf[k_col].count()


def _gdf_to_pointpattern(gdf: GeoDataFrame) -> PointPattern:
    return PointPattern(list(zip(gdf.geometry.x, gdf.geometry.y)))


def nnd(gdf: GeoDataFrame) -> tuple[float, float, float]:
    "Returns nearest neighbor distances in a tuple of (min, mean, max)"
    pp = _gdf_to_pointpattern(gdf)
    return pp.min_nnd, pp.mean_nnd, pp.max_nnd


def central_drift(gdf_a: GeoDataFrame, gdf_b: GeoDataFrame) -> float:
    centroid_a = gdf_a.dissolve().centroid
    centroid_b = gdf_b.dissolve().centroid
    return float(centroid_a.distance(centroid_b))


def ripleys_rot(gdf: GeoDataFrame) -> float:
    return _gdf_to_pointpattern(gdf).rot


def ripleys_k(
    gdf: GeoDataFrame, max_dist: float = None, min_dist: float = None, steps: int = 10
) -> KtestResult:
    if not max_dist:
        max_dist = ripleys_rot(gdf)

    if not min_dist:
        min_dist = max_dist / steps

    k_results = k_test(
        array(list(zip(gdf.geometry.x, gdf.geometry.y))),
        keep_simulations=True,
        support=(min_dist, max_dist, steps),
        n_simulations=999,
    )
    return k_results


def _bounds_from_ripleyresult(result: KtestResult) -> list:
    step_count = len(result.simulations[0])
    lower_bounds = []
    upper_bounds = []
    for i in range(step_count):
        values = [sim[i] for sim in result.simulations]
        lower_bounds.append(min(values))
        upper_bounds.append(max(values))
    return list(zip(lower_bounds, upper_bounds))


def _legend_deduped_labels(ax: Axis) -> None:
    handles, labels = ax.get_legend_handles_labels()
    unique = [(h, l) for i, (h, l) in enumerate(zip(handles, labels)) if l not in labels[:i]]
    ax.legend(*zip(*unique))


def compare_ripleyresults(c_result: KtestResult, s_result: KtestResult) -> list:
    step_count = len(c_result.statistic)
    deltas = []
    for i in range(step_count):
        delta = c_result.statistic[i] - s_result.statistic[i]
        deltas.append(delta)
    return deltas


def graph_ripleyresult(result: KtestResult, subtitle: str = None) -> Figure:
    bounds = _bounds_from_ripleyresult(result)
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(result.support, bounds, color="#303030", label="Upper/Lower Bounds", alpha=0.25)
    ax.plot(result.support, result.statistic, color="#1f77b4", label="Observed K")
    ax.scatter(result.support, result.statistic, c="#1f77b4")
    ax.set_xlabel("Distance")
    ax.set_ylabel("K Function")
    ax.set_title(subtitle)
    _legend_deduped_labels(ax)
    fig.suptitle("K Function Plot")
    return fig


def graph_ripleyresults(
    c_result: KtestResult,
    s_result: KtestResult,
    subtitle: str = None,
) -> Figure:
    bounds = _bounds_from_ripleyresult(s_result)
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(s_result.support, bounds, color="#303030", label="Upper/Lower Bounds", alpha=0.25)
    ax.plot(s_result.support, c_result.statistic, color="#1f77b4", label="Candidate")
    ax.plot(s_result.support, s_result.statistic, color="#ff7f0e", label="Sensitive")
    ax.scatter(c_result.support, c_result.statistic, zorder=5, c="#1f77b4")
    ax.scatter(s_result.support, s_result.statistic, zorder=6, c="#ff7f0e")
    ax.set_title(subtitle)
    ax.set_xlabel("Distance")
    ax.set_ylabel("K Function")
    _legend_deduped_labels(ax)
    fig.suptitle("K Function Result Comparison")
    return fig


def compare_candidates(sensitive_gdf: GeoDataFrame, *candidates: Candidate):
    for candidate in candidates:
        pass
