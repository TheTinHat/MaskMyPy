import warnings
from hashlib import sha256
from random import SystemRandom

from geopandas import GeoDataFrame
from numpy import random
from osmnx import graph_to_gdfs
from osmnx.distance import nearest_nodes
from osmnx.graph import graph_from_bbox
from osmnx.projection import project_graph
from osmnx.utils_graph import remove_isolated_nodes
from pandas.util import hash_pandas_object
from pyproj.crs.crs import CRS


def suppress(gdf, min_k, col: str = "k_anonymity", label: bool = True):
    """
    Suppresses points that do not meet a minimum k-anonymity value by displacing them
    to the mean center of the overall masked point pattern and (optionally) labelling them.

    Parameters
    ----------
    gdf : GeoDataFrame
        A GeoDataFrame containing point data and a column with k-anonymity values.
    min_k : int
        Minimum k-anonymity. Points with a k-anonymity below this value will be suppressed.
    col : str
        Name of the column containing k-anonymity values.
    label : bool
        If True, adds a "SUPPRESSED" column and labels suppressed points.

    Returns
    -------
    gdf
        A GeoDataFrame containing the result of the suppression.
    """
    sgdf = gdf.copy()
    centroid = sgdf.dissolve().centroid[0]
    sgdf.loc[sgdf[col] < min_k, sgdf.geometry.name] = centroid
    if label:
        sgdf.loc[sgdf[col] < min_k, "SUPPRESSED"] = "TRUE"
        sgdf.loc[sgdf[col] >= min_k, "SUPPRESSED"] = "FALSE"
    return sgdf


def checksum(gdf: GeoDataFrame) -> str:
    """
    Calculate SHA256 checksum of a GeoDataFrame and return the first 8 characters.
    Two completely identical GeoDataFrames will always return the exact same value,
    whereas two similar, but not completely identical GeoDataFrames will return
    entirely different values.

    Parameters
    ----------
    gdf : GeoDataFrame
        Any valid GeoDataFrame.

    Returns
    -------
    str
        The first 8 characters of the SHA256 checksum of the input GeoDataFrame.
    """
    return sha256(bytearray(hash_pandas_object(gdf).values)).hexdigest()[0:8]


def gen_rng(seed: int = None) -> object:
    """
    Create a seeded numpy default_rng() object.

    Parameters
    ----------
    seed : int
        An integer used to seed the random number generator. A seed is randomly
        generated using gen_seed() if one is not provided.
    Returns
    -------
    object
        numpy.default_rng()
    """
    if not seed:
        seed = gen_seed()
    return random.default_rng(seed=seed)


def gen_seed() -> int:
    """
    Generate a 16-digit random integer to seed random number generators.

    Returns
    -------
    int
        A 16 digit random integer.
    """

    return int(SystemRandom().random() * (10**16))


def snap_to_streets(gdf: GeoDataFrame) -> GeoDataFrame:
    """
    Relocates each point of a GeoDataFrame to the nearest node on the OpenStreetMap driving
    network. Performing this on masked datasets may reduce the chances of false attribution,
    and may provide an additional layer of obfuscation.

    This is *not* an alternative to masking.

    Parameters
    ----------
    gdf : GeoDataFrame
        A GeoDataFrame containing point data.

    Returns
    -------
    GeoDataFrame
        A GeoDataFrame containing points that have been snapped to street nodes.
    """
    snapped_gdf = gdf.copy()
    bbox = gdf.to_crs(epsg=4326).total_bounds
    graph = remove_isolated_nodes(
        graph_from_bbox(
            bbox=(bbox[3], bbox[1], bbox[2], bbox[0]),
            network_type="drive",
            truncate_by_edge=True,
        ),
        warn=False,
    )
    graph = project_graph(graph, to_crs=gdf.crs)
    node_gdf = graph_to_gdfs(graph)[0]

    snapped_gdf[snapped_gdf.geometry.name] = snapped_gdf[snapped_gdf.geometry.name].apply(
        lambda geom: node_gdf.at[nearest_nodes(graph, geom.x, geom.y), node_gdf.geometry.name]
    )

    return snapped_gdf


def _mark_unmasked_points(sensitive: GeoDataFrame, masked: GeoDataFrame):
    geom_col_idx = sensitive.columns.get_loc(sensitive.geometry.name)
    masked["UNMASKED"] = masked.apply(
        lambda x: (1 if x[masked.geometry.name] == sensitive.iat[x.name, geom_col_idx] else 0),
        axis=1,
    )
    unmasked_count = masked["UNMASKED"].sum()
    if unmasked_count > 0:
        warnings.warn(
            f"{unmasked_count} points could not be masked. Adding 'UNMASKED' column to mark unmasked points."
        )
    return masked


def _crop(gdf: GeoDataFrame, bbox: list[float], padding: float) -> GeoDataFrame:
    bbox = _pad(bbox, padding)
    return gdf.cx[bbox[0] : bbox[2], bbox[1] : bbox[3]]


def _pad(bbox: list[float], padding: float) -> list:
    pad_x = (bbox[2] - bbox[0]) * padding
    pad_y = (bbox[3] - bbox[1]) * padding
    bbox[0] = bbox[0] - pad_x
    bbox[1] = bbox[1] - pad_y
    bbox[2] = bbox[2] + pad_x
    bbox[3] = bbox[3] + pad_y
    return bbox


def _validate_geom_type(gdf: GeoDataFrame, *type_as_string: str) -> bool:
    geom_types = {True if geom_type in type_as_string else False for geom_type in gdf.geom_type}
    if False in geom_types:
        raise ValueError(f"GeoDataFrame contains geometry types other than {type_as_string}.")
    return True


def _validate_crs(*crs: CRS, custom_message: str = None) -> bool:
    default_message = (
        "CRS mismatch. Ensure the coordinate reference systems of all input layers match."
    )
    message = default_message if not custom_message else custom_message
    if len(set(crs)) != 1:
        raise ValueError(message)
    else:
        return True
