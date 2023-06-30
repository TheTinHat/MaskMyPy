from hashlib import sha256

from geopandas import GeoDataFrame
from osmnx import graph_to_gdfs
from osmnx.distance import nearest_nodes
from osmnx.graph import graph_from_bbox
from osmnx.projection import project_graph
from osmnx.utils_graph import remove_isolated_nodes
from pandas.util import hash_pandas_object
from pyproj.crs.crs import CRS


def _crop(gdf: GeoDataFrame, bbox: list[float], padding: float) -> GeoDataFrame:
    bbox = _pad(bbox, padding)
    return gdf.cx[bbox[0] : bbox[2], bbox[1] : bbox[3]]


def _checksum(gdf: GeoDataFrame) -> str:
    return sha256(bytearray(hash_pandas_object(gdf).values)).hexdigest()[0:12]


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


def _validate_crs(a: CRS, b: CRS, custom_message: str = None) -> bool:
    default_message = "CRS do not match. Ensure all CRS match that of sensitive GeoDataFrame."
    message = default_message if not custom_message else custom_message
    if a != b:
        raise ValueError(message)
    else:
        return True


def snap_to_streets(gdf: GeoDataFrame) -> GeoDataFrame:
    snapped_gdf = gdf.copy()
    bbox = gdf.to_crs(epsg=4326).total_bounds
    graph = remove_isolated_nodes(
        graph_from_bbox(
            north=bbox[3],
            south=bbox[1],
            west=bbox[0],
            east=bbox[2],
            network_type="drive",
            truncate_by_edge=True,
        )
    )
    graph = project_graph(graph, to_crs=gdf.crs)
    node_gdf = graph_to_gdfs(graph)[0]

    snapped_gdf[snapped_gdf.geometry.name] = snapped_gdf[snapped_gdf.geometry.name].apply(
        lambda geom: node_gdf.at[nearest_nodes(graph, geom.x, geom.y), node_gdf.geometry.name]
    )

    return snapped_gdf
