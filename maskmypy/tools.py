from geopandas import GeoDataFrame, sjoin
from shapely.geometry import LineString


def crop(gdf, bbox, padding):
    bbox = pad(bbox, padding)
    return gdf.cx[bbox[0] : bbox[2], bbox[1] : bbox[3]]


def pad(bbox, padding):
    pad_x = (bbox[2] - bbox[0]) * padding
    pad_y = (bbox[3] - bbox[1]) * padding
    bbox[0] = bbox[0] - pad_x
    bbox[1] = bbox[1] - pad_y
    bbox[2] = bbox[2] + pad_x
    bbox[3] = bbox[3] + pad_y
    return bbox


def validate_geom_type(gdf, *type_as_string):
    geom_types = {True if geom_type in type_as_string else False for geom_type in gdf.geom_type}
    if False in geom_types:
        raise ValueError(f"GeoDataFrame contains geometry types other than {type_as_string}.")
    return True


def map_displacement(sensitive_gdf, candidate_gdf, filename=None, address=None):
    import contextily as ctx
    import matplotlib.pyplot as plt

    lines = sensitive_gdf.copy()
    lines = lines.join(candidate_gdf, how="left", rsuffix="_masked")
    lines.geometry = lines.apply(
        lambda x: LineString([x["geometry"], x["geometry_masked"]]), axis=1
    )
    ax = lines.plot(color="black", zorder=2, linewidth=1, figsize=[10, 10])
    ax = sensitive_gdf.plot(ax=ax, color="red", zorder=3, markersize=12)
    ax = candidate_gdf.plot(ax=ax, color="blue", zorder=4, markersize=12)
    if isinstance(address, GeoDataFrame):
        ax = address.plot(ax=ax, color="grey", zorder=1, markersize=6)

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
