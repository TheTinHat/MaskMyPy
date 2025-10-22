from math import sqrt

import matplotlib.pyplot as plt
from geopandas import GeoDataFrame, sjoin
from matplotlib.axis import Axis
from matplotlib.figure import Figure
from numpy import array, floor, square
from pointpats import PointPattern, k_test
from pointpats.distance_statistics import KtestResult
from shapely.geometry import LineString

from . import tools


def evaluate(
    sensitive_gdf: GeoDataFrame,
    candidate_gdf: GeoDataFrame,
    population_gdf: GeoDataFrame = None,
    population_column: str = "pop",
    skip_slow: bool = True,
) -> dict:
    """
    Evaluate the privacy protection and information loss of a masked dataset (`candidate_gdf`)
    compared to the unmasked sensitive dataset (`sensitive_gdf`). This is a convenience function
    that automatically runs many of the analysis tools that MaskMyPy offers, returning a simple
    dictionary of results. Note that privacy metrics require a `population_gdf` to be provided.

    Parameters
    ----------
    sensitive_gdf : GeoDataFrame
        A GeoDataFrame containing sensitive points prior to masking.
    candidate_gdf : GeoDataFrame
        A GeoDataFrame containing masked points to be evaluated.
    population_gdf : GeoDataFrame
        A GeoDataFrame containing either address points or polygons with a population column
        (see `population_column`). Used to calculate k-anonymity metrics.
    population_column : str
        If a polygon-based `population_gdf` is provided, the name of the column containing
        population counts.
    skip_slow : bool
        If True, skips analyses that are known to be slow. Currently, this only includes the
        root-mean-square error of Ripley's K results between the masked and unmasked data.

    Returns
    -------
    dict
        A dictionary containing evaluation results.
    """
    stats = {}

    # Information Loss
    stats["central_drift"] = central_drift(
        sensitive_gdf=sensitive_gdf, candidate_gdf=candidate_gdf
    )
    stats.update(
        summarize_displacement(
            displacement(
                sensitive_gdf=sensitive_gdf,
                candidate_gdf=candidate_gdf,
            )
        )
    )
    stats.update(nnd_delta(sensitive_gdf=sensitive_gdf, candidate_gdf=candidate_gdf))
    if not skip_slow:
        stats["ripley_rmse"] = ripley_rmse(ripleys_k(sensitive_gdf), ripleys_k(candidate_gdf))

    # Privacy
    if isinstance(population_gdf, GeoDataFrame):
        k_gdf = k_anonymity(
            sensitive_gdf=sensitive_gdf,
            candidate_gdf=candidate_gdf,
            population_gdf=population_gdf,
            population_column=population_column,
        )
        stats.update(summarize_k(k_gdf))
        stats["k_satisfaction_5"] = k_satisfaction(k_gdf, 5)
        stats["k_satisfaction_25"] = k_satisfaction(k_gdf, 25)
        stats["k_satisfaction_50"] = k_satisfaction(k_gdf, 50)
    return stats


def displacement(
    sensitive_gdf: GeoDataFrame, candidate_gdf: GeoDataFrame, col: str = "_distance"
) -> GeoDataFrame:
    """
    Adds a column to the `candidate_gdf` containing the distance between each masked point
    and its original, unmasked location (`sensitive_gdf`).

    Parameters
    ----------
    sensitive_gdf : GeoDataFrame
        A GeoDataFrame containing sensitive points prior to masking.
    candidate_gdf : GeoDataFrame
        A GeoDataFrame containing masked points.
    col : str
        Name of the displacement distance column to add to `candidate_gdf`.

    Returns
    -------
    GeoDataFrame
        The `candidate_gdf` with an additional column describing displacement distance.
    """
    candidate_gdf = candidate_gdf.copy()
    candidate_gdf[col] = candidate_gdf.geometry.distance(sensitive_gdf.geometry)
    return candidate_gdf


def k_anonymity(
    sensitive_gdf: GeoDataFrame,
    candidate_gdf: GeoDataFrame,
    population_gdf: GeoDataFrame,
    population_column: str = "pop",
) -> GeoDataFrame:
    """
    Adds a column to the `candidate_gdf` containing the spatial k-anonymity value of each
    masked point.

    Parameters
    ----------
    sensitive_gdf : GeoDataFrame
        A GeoDataFrame containing sensitive points prior to masking.
    candidate_gdf : GeoDataFrame
        A GeoDataFrame containing masked points.
    population_gdf : GeoDataFrame
        A GeoDataFrame containing either address points or polygons with a population column
        (see `population_column`). Used to calculate k-anonymity metrics. Note that
        address points tend to provide more accurate results.
    population_column : str
        If a polygon-based `population_gdf` is provided, the name of the column containing
        population counts.

    Returns
    -------
    GeoDataFrame
        The `candidate_gdf` with an additional column describing k-anonymity.
    """
    if tools._validate_geom_type(population_gdf, "Point"):
        k_gdf = _calculate_k(sensitive_gdf, candidate_gdf, population_gdf)
    elif tools._validate_geom_type(population_gdf, "Polygon", "MultiPolygon"):
        if population_column not in population_gdf:
            raise ValueError(
                f"Cannot find population column {population_column} in population_gdf"
            )
        k_gdf = _estimate_k(sensitive_gdf, candidate_gdf, population_gdf, population_column)
    else:
        raise ValueError("population_gdf must include either Points or Polygons/MultiPolygons.")
    return k_gdf


def k_satisfaction(gdf: GeoDataFrame, min_k: int, col: str = "k_anonymity") -> float:
    """
    For a masked GeoDataFrame containing k-anonymity values, calculate the percentage of
    points that are equal to or greater than (i.e. satisfy) a given k-anonymity threshold (`min_k`).

    Parameters
    ----------
    gdf : GeoDataFrame
        A GeoDataFrame containing k-anonymity values.
    min_k : int
        The minimum k-anonymity that must be satisfied.
    col : str
        Name of the column containing k-anonymity values.

    Returns
    -------
    float
        A percentage of points in the GeoDataFrame that satisfy `min_k`.
    """
    return round(gdf.loc[gdf[col] >= min_k, col].count() / gdf[col].count(), 3)


def summarize_k(gdf: GeoDataFrame, col: str = "k_anonymity") -> dict:
    """
    For a masked GeoDataFrame containing k-anonymity values, calculate the minimum, maximum,
    median, and mean k-anonymity.

    Parameters
    ----------
    gdf : GeoDataFrame
        A GeoDataFrame containing k-anonymity values.
    col : str
        Name of the column containing k-anonymity values.

    Returns
    -------
    dict
        A dictionary containing summary k-anonymity statistics.
    """
    return {
        "k_min": int(gdf.loc[:, col].min()),
        "k_max": int(gdf.loc[:, col].max()),
        "k_med": round(float(gdf.loc[:, col].median()), 2),
        "k_mean": round(float(gdf.loc[:, col].mean()), 2),
    }


def summarize_displacement(gdf: GeoDataFrame, col: str = "_distance") -> dict:
    """
    For a masked GeoDataFrame containing displacement distances, calculate the minimum, maximum,
    median, and mean displacement distance.

    Parameters
    ----------
    gdf : GeoDataFrame
        A GeoDataFrame containing displacement distance values.
    col : str
        Name of the column containing displacement distance values.

    Returns
    -------
    dict
        A dictionary containing summary displacement distance statistics.
    """
    return {
        "displacement_min": round(float(gdf.loc[:, col].min()), 6),
        "displacement_max": round(float(gdf.loc[:, col].max()), 6),
        "displacement_med": round(float(gdf.loc[:, col].median()), 6),
        "displacement_mean": round(float(gdf.loc[:, col].mean()), 6),
    }


def nnd(gdf: GeoDataFrame) -> dict:
    """
    Calculate the minimum, maximum, and mean nearest neighbor distance for a given GeoDataFrame.

    Parameters
    ----------
    gdf : GeoDataFrame
        A GeoDataFrame containing points.

    Returns
    -------
    dict
        A dictionary containing the minimum, maximum, and mean nearest neighbor distance.
    """
    pp = _gdf_to_pointpattern(gdf)
    return {"nnd_min": pp.min_nnd, "nnd_max": pp.max_nnd, "nnd_mean": pp.mean_nnd}


def nnd_delta(sensitive_gdf: GeoDataFrame, candidate_gdf: GeoDataFrame) -> dict:
    """
    Calculate the *difference* between minimum, maximum, and mean nearest neighbor distances
    before (`sensitive_gdf`) and after (`candidate_gdf`) masking. Higher values indicate
    greater information loss due to masking.

    Parameters
    ----------
    sensitive_gdf : GeoDataFrame
        A GeoDataFrame containing sensitive points prior to masking.
    candidate_gdf : GeoDataFrame
        A GeoDataFrame containing masked points.

    Returns
    -------
    dict
        A dictionary describing deltas in nearest neighbor distance before and after masking.
    """
    before = nnd(sensitive_gdf)
    after = nnd(candidate_gdf)
    delta = {}
    for key, value in before.items():
        delta.update({f"{key}_delta": round(after[key] - before[key], 6)})
    return delta


def central_drift(sensitive_gdf: GeoDataFrame, candidate_gdf: GeoDataFrame) -> float:
    """
    Calculates how far the centroid of the point pattern has been displaced due to masking.
    Higher central drift indicates more information loss.

    Parameters
    ----------
    sensitive_gdf : GeoDataFrame
        A GeoDataFrame containing sensitive points prior to masking.
    candidate_gdf : GeoDataFrame
        A GeoDataFrame containing masked points.

    Returns
    -------
    float
        The central drift, with units equal to the CRS of the `sensitive_gdf`.
    """
    centroid_a = sensitive_gdf.dissolve().centroid
    centroid_b = candidate_gdf.dissolve().centroid
    return round(float(centroid_a.distance(centroid_b).iloc[0]), 6)


def ripleys_k(
    gdf: GeoDataFrame,
    max_dist: float = None,
    min_dist: float = None,
    steps: int = 10,
    simulations: int = 99,
) -> KtestResult:
    """
    Performs Ripley's K clustering analysis on a GeoDataFrame. This evaluates clustering across a
    range of spatial scales.

    See `maskmypy.analysis.ripley_rmse()`, `maskmypy.analysis.graph_ripleyresult()`, and
    `maskmypy.analysis.graph_ripleyresults()` for functions that process/visualize the results
    of this function.

    Parameters
    ----------
    gdf : GeoDataFrame
        GeoDataFrame to analyse.
    max_dist : float
        The largest distance band used for cluster analysis. If `None`, this defaults to one
        quarter of the smallest side of the bounding box (i.e. Ripleys Rule of Thumb).
    min_dist : float
        The smallest distance band used for cluster analysis. If `None`, this is automatically set
        to  `max_dist / steps`.
    steps : int
        The number of equally spaced intervals between the minimum and maximum distance bands
        to analyze clustering on.
    simulations : int
        The number of simulations to perform.

    Returns
    -------
    KtestResult
        A named tuple that contains `("support", "statistic", "pvalue", "simulations")`.
    """
    if not max_dist:
        max_dist = _gdf_to_pointpattern(gdf).rot

    if not min_dist:
        min_dist = max_dist / steps

    k_results = k_test(
        array(list(zip(gdf.geometry.x, gdf.geometry.y))),
        keep_simulations=True,
        support=(min_dist, max_dist, steps),
        n_simulations=simulations,
    )
    return k_results


def ripley_rmse(sensitive_result: KtestResult, candidate_result: KtestResult) -> float:
    """
    Calculates the root-mean-square error between the Ripley's K-test results of unmasked and
    masked data. As the goal of geographic masking is to reduce information loss, the actual
    amount of clustering in masked data is unimportant; what matters is that the clustering
    or dispersion of the masked data resembles that of the original, sensitive data. By comparing
    the RMSE of k-test results, we can reduce this deviation to a single figure, which is useful
    for quickly comparing how multiple masks perform.

    Lower RMSE values indicate less information loss due to masking, whereas higher values
    indicate greater information loss due to masking.

    Parameters
    ----------
    sensitive_result : KtestResult
        The KtestResult tuple from applying `maskmypy.analysis.ripleys_k()` on a sensitive layer.
    candidate_result : KtestResult
        The KtestResult tuple from applying `maskmypy.analysis.ripleys_k()` on a masked layer.

    Returns
    -------
    float
        The root-mean-square error between the two k-test results.
    """
    step_count = len(candidate_result.statistic)
    residuals = []
    for i in range(step_count):
        residual = candidate_result.statistic[i] - sensitive_result.statistic[i]
        residuals.append(residual)
    return round(sqrt(square(residuals).mean()), 3)


def graph_ripleyresult(result: KtestResult, subtitle: str = None) -> Figure:
    """
    Generate a graph depicting a given KtestResult, such as would be generated from using
    `maskmypy.analysis.ripleys_k()`.

    Parameters
    ----------
    result : KtestResult
        The KtestResult tuple from applying `maskmypy.analysis.ripleys_k()` on a given layer.
    subtitle : str
        A subtitle to add to the graph.

    Returns
    -------
    Figure
        A matplotlib.figure.Figure object.
    """
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
    sensitive_result: KtestResult,
    candidate_result: KtestResult,
    subtitle: str = None,
) -> Figure:
    """
    Generate a graph depicting two KtestResults, such as would be generated from using
    `maskmypy.analysis.ripleys_k()`.

    Similar to `maskmypy.analysis.graph_ripleyresult()` except this function graphs both
    the sensitive and candidate results, allowing for visual comparison of clustering and dispersion
    between the two.

    Parameters
    ----------
    sensitive_result : KtestResult
        The KtestResult tuple from applying `maskmypy.analysis.ripleys_k()` on the sensitive layer.
    candidate_result : KtestResult
        The KtestResult tuple from applying `maskmypy.analysis.ripleys_k()` on a masked layer.
    subtitle : str
        A subtitle to add to the graph.

    Returns
    -------
    Figure
        A matplotlib.figure.Figure object.
    """
    bounds = _bounds_from_ripleyresult(sensitive_result)
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.plot(
        sensitive_result.support,
        bounds,
        color="#ff7f0e",
        label="Sensitive Upper/Lower Bounds",
        alpha=0.35,
    )
    ax.plot(
        candidate_result.support,
        bounds,
        color="#1f77b4",
        label="Candidate Upper/Lower Bounds",
        alpha=0.35,
    )
    ax.plot(
        sensitive_result.support,
        sensitive_result.statistic,
        color="#ff7f0e",
        label="Sensitive Statistic",
    )
    ax.plot(
        candidate_result.support,
        candidate_result.statistic,
        color="#1f77b4",
        label="Candidate Statistic",
    )
    ax.scatter(sensitive_result.support, sensitive_result.statistic, zorder=6, c="#ff7f0e")
    ax.scatter(candidate_result.support, candidate_result.statistic, zorder=5, c="#1f77b4")
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
    """
    Generate a map showing the displacement of each masked point from its original location.
    Requires the `contextily` package.

    Parameters
    ----------
    sensitive_gdf : GeoDataFrame
        A GeoDataFrame containing sensitive points prior to masking.
    candidate_gdf : GeoDataFrame
        A GeoDataFrame containing masked points.
    filename : str
        If specified, saves the map to the filesystem.
    context_gdf : GeoDataFrame
        A GeoDataFrame containing contextual data to be added to the map, such as address points,
        administrative boundaries, etc.

    Returns
    -------
    matplotlib.pyplot
        A pyplot object containing the mapped data.
    """
    import contextily as ctx

    lines = sensitive_gdf.copy()
    lines = lines.join(candidate_gdf, how="left", rsuffix="_masked")
    lines.geometry = lines.apply(
        lambda x: LineString([x["geometry"], x["geometry_masked"]]), axis=1
    )
    ax = lines.plot(color="black", zorder=2, linewidth=1, figsize=[8, 8])
    ax = sensitive_gdf.plot(ax=ax, color="red", zorder=3, markersize=6)
    ax = candidate_gdf.plot(ax=ax, color="blue", zorder=4, markersize=6)
    if isinstance(context_gdf, GeoDataFrame):
        ax = context_gdf.plot(ax=ax, color="grey", zorder=1, markersize=3)

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


def _estimate_k(
    sensitive_gdf: GeoDataFrame,
    candidate_gdf: GeoDataFrame,
    population_gdf: GeoDataFrame,
    population_column: str = "pop",
) -> GeoDataFrame:
    candidate_gdf = candidate_gdf.copy()
    pop_col_adjusted = "_".join([population_column, "adjusted"])
    candidate_gdf["k_anonymity"] = (
        displacement(sensitive_gdf, candidate_gdf)
        .assign(geometry=lambda x: x.geometry.buffer(x["_distance"]), axis=1)
        .pipe(_disaggregate, gdf_b=population_gdf, gdf_b_col=population_column)
        .groupby("_index_2")[pop_col_adjusted]
        .sum()
        .apply(floor)
    )
    return candidate_gdf


def _calculate_k(
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
        + 1
    )
    candidate_gdf.fillna({"k_anonymity": 1}, inplace=True)
    return candidate_gdf
