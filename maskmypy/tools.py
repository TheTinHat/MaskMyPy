from geopandas import GeoDataFrame, sjoin
from shapely.geometry import LineString


def crop(gdf, bbox, padding=None):
    if padding is None:
        pad_x = (bbox[2] - bbox[0]) / 5
        pad_y = (bbox[3] - bbox[1]) / 5
        padding = max(pad_x, pad_y)

    bbox[0] = bbox[0] - pad_x
    bbox[1] = bbox[1] - pad_y
    bbox[2] = bbox[2] + pad_x
    bbox[3] = bbox[3] + pad_y
    return gdf.cx[bbox[0] : bbox[2], bbox[1] : bbox[3]]


def validate_geom_type(gdf, *type_as_string):
    geom_types = {True if geom_type in type_as_string else False for geom_type in gdf.geom_type}
    if False in geom_types:
        raise ValueError(f"GeoDataFrame contains geometry types other than {type_as_string}.")
    return True


def displacement(secret: GeoDataFrame, mask: GeoDataFrame, colname="_distance") -> GeoDataFrame:
    """Calculates the displacement distance between secret and masked points.

    Parameters
    ----------
    secret : GeoDataFrame
        Secret points prior to masking.
    mask : GeoDataFrame
        Points after masking
    colname : str, optional
        Name for the output displacement distance column. Default: `_distance`.

    Returns
    -------
    GeoDataFrame
        A GeoDataFrame with a column describing displacement distances
    """
    mask[colname] = mask.geometry.distance(secret.geometry)
    return mask


def estimate_k(
    secret: GeoDataFrame, mask: GeoDataFrame, population: GeoDataFrame, pop_col: str = "pop"
) -> GeoDataFrame:
    """Estimate the k-anonymity of each anonymized point based on surrounding population density.
    Note that unlike in `Donut_K`, neighboring polygons will be disaggregated and included to more
    accurately estimate k-anonymity. Typically less accurate the `calculate_k`.

    Parameters
    ----------
    secret : GeoDataFrame
        Secret points prior to masking.
    mask : GeoDataFrame
        Points after masking
    population : GeoDataFrame
        A polygon layer with a column describing population count.
    pop_col : str, optional
        The name of the population count column in the population polygon layer. Default: `pop`.

    Returns
    -------
    GeoDataFrame
        A GeoDataFrame with a `k_est` column describing k-anonymity.
    """
    pop_col_adjusted = "_".join([pop_col, "adjusted"])
    mask["k_est"] = (
        displacement(secret, mask)
        .assign(geometry=lambda x: x.geometry.buffer(x["_distance"]), axis=1)
        .pipe(disaggregate, gdf_b=population, gdf_b_col=pop_col)
        .groupby("_index_2")[pop_col_adjusted]
        .sum()
        .round()
    )
    return sanitize(mask)


def calculate_k(secret: GeoDataFrame, mask: GeoDataFrame, address: GeoDataFrame) -> GeoDataFrame:
    """Calculate the k-anonymity of each anonymized point based on surrounding address points.
    Typically more accurate the `estimate_k`.

    Parameters
    ----------
    secret : GeoDataFrame
        Secret points prior to masking.
    mask : GeoDataFrame
        Points after masking
    address : GeoDataFrame, optional
            A layer containing address points.

    Returns
    -------
    GeoDataFrame
        A GeoDataFrame with a `k_calc` column describing k-anonymity.
    """
    mask_tmp = displacement(secret, mask).assign(geometry=lambda x: x.buffer(x["_distance"]))
    mask["k_calc"] = (
        sjoin(address, mask_tmp, how="left", rsuffix="mask").groupby("index_mask").size()
    )
    mask.fillna({"k_calc": 0}, inplace=True)
    return sanitize(mask)


def sanitize(gdf):
    gdf = gdf.loc[:, ~gdf.columns.str.startswith("_")]
    return gdf


def disaggregate(gdf_a, gdf_b, gdf_b_col):
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


def map_displacement(secret, mask, filename=None, address=None):
    """Creates a map visualizing the displacement of each point between its
    original and masked location.

    Parameters
    ----------
    secret : GeoDataFrame
        Secret points prior to masking.
    mask : GeoDataFrame
        Points after masking
    filename : str, optional
        If specified, saves the output map to a file.
    address : GeoDataFrame, optional
            A layer containing address points.

    Returns
    -------
    matplotlib.pyplot.plt
        A plot depicting secret and masked points connected by lines.
    """
    import contextily as ctx
    import matplotlib.pyplot as plt

    lines = secret.copy()
    lines = lines.join(mask, how="left", rsuffix="_mask")
    lines.geometry = lines.apply(lambda x: LineString([x["geometry"], x["geometry_mask"]]), axis=1)
    ax = lines.plot(color="black", zorder=2, linewidth=1, figsize=[10, 10])
    ax = secret.plot(ax=ax, color="red", zorder=3, markersize=12)
    ax = mask.plot(ax=ax, color="blue", zorder=4, markersize=12)
    if isinstance(address, GeoDataFrame):
        ax = address.plot(ax=ax, color="grey", zorder=1, markersize=6)

    ctx.add_basemap(ax, crs=secret.crs, source=ctx.providers.OpenStreetMap.Mapnik)
    plt.title("Displacement Distances", fontsize=16)
    plt.figtext(
        0.5,
        0.025,
        "Secret points (red), Masked points (blue). \n KEEP CONFIDENTIAL",
        wrap=True,
        horizontalalignment="center",
        fontsize=12,
    )
    if filename:
        plt.savefig(filename)

    return plt
