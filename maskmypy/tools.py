from geopandas import GeoDataFrame, sjoin
from shapely.geometry import LineString


def displacement(secret: GeoDataFrame, mask: GeoDataFrame, colname="_distance") -> GeoDataFrame:
    mask[colname] = mask.geometry.distance(secret.geometry)
    return mask


def estimate_k(
    secret: GeoDataFrame, mask: GeoDataFrame, population: GeoDataFrame, pop_col: str = "pop"
) -> GeoDataFrame:

    pop_col_adjusted = "_".join([pop_col, "adjusted"])
    mask["k_est"] = (
        displacement(secret, mask)
        .assign(geometry=lambda x: x.geometry.buffer(x["_distance"]), axis=1)
        .pipe(disaggregate, gdf_b=population, gdf_b_col=pop_col)
        .groupby("_index_2")[pop_col_adjusted]
        .sum()
        .round()
    )
    return mask


def calculate_k(secret: GeoDataFrame, mask: GeoDataFrame, address: GeoDataFrame) -> GeoDataFrame:
    mask_tmp = displacement(secret, mask).assign(geometry=lambda x: x.buffer(x["_distance"]))
    mask["k_calc"] = (
        sjoin(address, mask_tmp, how="left", rsuffix="mask").groupby("index_mask").size()
    )
    mask.fillna({"k_calc": 0}, inplace=True)
    return mask


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


def map_displacement(secret, mask, filename="", address=""):
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
    else:
        plt.show()
        return plt
