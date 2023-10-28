from collections import namedtuple
from math import sqrt

import matplotlib.pyplot as plt
from geopandas import GeoDataFrame, sjoin
from matplotlib.axis import Axis
from matplotlib.figure import Figure
from numpy import array, square
from pointpats import PointPattern, k_test
from pointpats.distance_statistics import KtestResult
from shapely.geometry import LineString


def displacement(
    sensitive_gdf: GeoDataFrame, candidate_gdf: GeoDataFrame, col: str = "_distance"
) -> GeoDataFrame:
    candidate_gdf = candidate_gdf.copy()
    candidate_gdf[col] = candidate_gdf.geometry.distance(sensitive_gdf.geometry)
    return candidate_gdf


def estimate_k(
    sensitive_gdf: GeoDataFrame,
    candidate_gdf: GeoDataFrame,
    population_gdf: GeoDataFrame,
    pop_col: str = "pop",
) -> GeoDataFrame:
    candidate_gdf = candidate_gdf.copy()
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


def calculate_k(
    sensitive_gdf: GeoDataFrame, candidate_gdf: GeoDataFrame, address_gdf: GeoDataFrame
) -> GeoDataFrame:
    candidate_gdf = candidate_gdf.copy()
    candidate_gdf_tmp = displacement(sensitive_gdf, candidate_gdf).assign(
        geometry=lambda x: x.buffer(x["_distance"])
    )
    candidate_gdf["k_anonymity"] = (
        sjoin(address_gdf, candidate_gdf_tmp, how="left", rsuffix="candidate")
        .groupby("index_candidate")
        .size()
    )
    candidate_gdf.fillna({"k_anonymity": 0}, inplace=True)
    return candidate_gdf


def k_satisfaction(gdf: GeoDataFrame, min_k: int, col: str = "k_anonymity") -> float:
    return gdf.loc[gdf[col] >= min_k, col].count() / gdf[col].count()


def summarize_displacement(gdf: GeoDataFrame, col="_distance") -> dict:
    return
    {
        "displacement_min": float(gdf.loc[:, col].min()),
        "displacement_max": float(gdf.loc[:, col].max()),
        "displacement_med": float(gdf.loc[:, col].median()),
        "displacement_mean": float(gdf.loc[:, col].mean()),
    }


def summarize_k(gdf: GeoDataFrame, col="k_anonymity") -> dict:
    return {
        "k_min": int(gdf.loc[:, col].min()),
        "k_max": int(gdf.loc[:, col].max()),
        "k_med": float(gdf.loc[:, col].median()),
        "k_mean": float(gdf.loc[:, col].mean()),
    }


def nnd(gdf: GeoDataFrame) -> dict:
    pp = _gdf_to_pointpattern(gdf)
    return {"nnd_min": pp.min_nnd, "nnd_max": pp.max_nnd, "nnd_mean": pp.mean_nnd}


def drift(gdf_a: GeoDataFrame, gdf_b: GeoDataFrame) -> float:
    centroid_a = gdf_a.dissolve().centroid
    centroid_b = gdf_b.dissolve().centroid
    return float(centroid_a.distance(centroid_b).iloc[0])


def ripleys_k(
    gdf: GeoDataFrame, max_dist: float = None, min_dist: float = None, steps: int = 10
) -> KtestResult:
    if not max_dist:
        max_dist = _ripleys_rot(gdf)

    if not min_dist:
        min_dist = max_dist / steps

    k_results = k_test(
        array(list(zip(gdf.geometry.x, gdf.geometry.y))),
        keep_simulations=True,
        support=(min_dist, max_dist, steps),
        n_simulations=999,
    )
    return k_results


def ripley_rmse(c_result: KtestResult, s_result: KtestResult) -> float:
    step_count = len(c_result.statistic)
    residuals = []
    for i in range(step_count):
        residual = c_result.statistic[i] - s_result.statistic[i]
        residuals.append(residual)
    return sqrt(square(residuals).mean())


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


def map_displacement(
    sensitive_gdf: GeoDataFrame,
    candidate_gdf: GeoDataFrame,
    filename: str = None,
    context_gdf: GeoDataFrame = None,
) -> plt:
    import contextily as ctx

    lines = sensitive_gdf.copy()
    lines = lines.join(candidate_gdf, how="left", rsuffix="_masked")
    lines.geometry = lines.apply(
        lambda x: LineString([x["geometry"], x["geometry_masked"]]), axis=1
    )
    ax = lines.plot(color="black", zorder=2, linewidth=1, figsize=[10, 10])
    ax = sensitive_gdf.plot(ax=ax, color="red", zorder=3, markersize=12)
    ax = candidate_gdf.plot(ax=ax, color="blue", zorder=4, markersize=12)
    if isinstance(context_gdf, GeoDataFrame):
        ax = context_gdf.plot(ax=ax, color="grey", zorder=1, markersize=6)

    ctx.add_basemap(ax, crs=sensitive_gdf.crs, source=ctx.providers.OpenStreetMap.Mapnik)
    plt.title("Displacement Distances", fontsize=16)
    plt.figtext(
        0.5,
        0.025,
        "Sensitive points (red), Masked points (blue). \n KEEP CONFIDENTIAL",
        wrap=True,
        horizontalalignment="center",
        fontsize=12,
    )
    if filename:
        plt.savefig(filename)

    return plt


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


def _gdf_to_pointpattern(gdf: GeoDataFrame) -> PointPattern:
    return PointPattern(list(zip(gdf.geometry.x, gdf.geometry.y)))


def _ripleys_rot(gdf: GeoDataFrame) -> float:
    return _gdf_to_pointpattern(gdf).rot


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
