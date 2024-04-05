from copy import deepcopy
from dataclasses import dataclass

from geopandas import GeoDataFrame
from networkx import single_source_dijkstra_path_length
from numpy import random
from osmnx import graph_to_gdfs
from osmnx.distance import add_edge_lengths, nearest_nodes
from osmnx.graph import graph_from_bbox
from osmnx.utils_graph import remove_isolated_nodes
from shapely import Point

from .. import tools


def street(
    gdf: GeoDataFrame,
    low: int,
    high: int,
    max_length: float = 1000,
    seed: int = None,
    padding: float = 0.2,
) -> GeoDataFrame:
    """
    Apply street masking to a GeoDataFrame, displacing points along the OpenStreetMap street
    network. This helps account for variations in population density, and reduces the likelihood
    of false attribution as points are always displaced to the street network. Each point is
    snapped to the nearest node on the network, then displaced along the surround network between
    `low` and `high` nodes away.

    Example
    -------
    ```python
    from maskmypy import street

    masked = street(
        gdf=sensitive_points,
        min=20,
        max=30
    )
    ```

    Parameters
    ----------
    gdf : GeoDataFrame
        GeoDataFrame containing sensitive points.
    low : int
        Minimum number of nodes along the OSM street network to traverse.
    high : int
        Maximum number of nodes along the OSM street network to traverse.
    max_length : float
        When locating the closest node to each point on the street network, MaskMyPy verifies
        that its immediate neighbours are no more than `max_length` away, in meters. This prevents
        extremely large masking distances, such as those caused by long highways.
    seed : int
        Used to seed the random number generator so that masked datasets are reproducible.
        Randomly generated if left undefined.
    padding : float
        OSM network data is retrieved based on the bounding box of the sensitive GeoDataFrame.
        Padding is used to expand this bounding box slightly to reduce unwanted edge-effects.
        A value of `0.2` would add 20% of the x and y extent to *each side* of the bounding box.

    Returns
    -------
    GeoDataFrame
        A GeoDataFrame containing masked points.
    """
    gdf = gdf.copy()
    _validate_street(gdf, low, high)

    seed = tools.gen_seed() if not seed else seed

    args = locals()

    masked_gdf = _Street(**args).run()

    return masked_gdf


def _validate_street(gdf, low, high):
    tools._validate_geom_type(gdf, "Point")

    if low >= high:
        raise ValueError("Low value must be less than high value.")


@dataclass
class _Street:
    gdf: GeoDataFrame
    low: int
    high: int
    max_length: float
    seed: int
    padding: float

    def __post_init__(self) -> None:
        self._rng = random.default_rng(seed=self.seed)
        self.crs = self.gdf.crs
        self.gdf = self.gdf.to_crs(epsg=4326)
        self._get_osm()

    def _get_osm(self) -> None:
        bbox = tools._pad(self.gdf.total_bounds, self.padding)
        self.graph = add_edge_lengths(
            remove_isolated_nodes(
                graph_from_bbox(
                    north=bbox[3],
                    south=bbox[1],
                    west=bbox[0],
                    east=bbox[2],
                    network_type="drive",
                    truncate_by_edge=True,
                ),
                warn=False,
            )
        )
        self.graph_gdf = graph_to_gdfs(self.graph)
        self.graph_tmp = deepcopy(self.graph)

    def _mask_point(self, point: Point) -> Point:
        nearest_node_id = self._nearest_node_with_neighbors(point)
        return self._mask_point_from_node_id(nearest_node_id)

    def _nearest_node_with_neighbors(self, point: Point) -> int:
        neighbor_count = 0
        while neighbor_count < 1:
            node_id = nearest_nodes(self.graph_tmp, point.x, point.y)
            neighbors = list(self.graph_tmp.neighbors(node_id))
            for neighbor in neighbors:
                length = self.graph_tmp.get_edge_data(node_id, neighbor)[0]["length"]
                if length > self.max_length:
                    neighbors = [n for n in neighbors if n != neighbor]
            neighbor_count = len(neighbors)

            if neighbor_count == 0:
                self.graph_tmp.remove_node(node_id)
        return node_id

    def _mask_point_from_node_id(self, node_id: int) -> Point:
        node_count = 0
        target_node_count = self._rng.integers(self.low, self.high, endpoint=False)
        _max_length = self.max_length

        # Search for surrounding nodes until number of nodes found equals or exceeds target_node_count
        while node_count < target_node_count:
            paths = single_source_dijkstra_path_length(
                G=self.graph, source=node_id, cutoff=_max_length, weight="length"
            )
            node_count = len(paths)
            _max_length = _max_length * 2

        # Calculate the total distance to the closest nodes within the target_node_count
        i = 0
        distances = []
        nodes = []
        total_distance = 0
        for key, value in paths.items():
            nodes.append(key)
            distances.append(value)
            total_distance += value
            i += 1
            if i == target_node_count:
                break

        # Target distance is the average distance to nodes within the target_node_count
        target_distance = total_distance / target_node_count

        # Find the node closest to the candidate distance
        target_node = nodes[
            distances.index(min(distances, key=lambda x: abs(x - target_distance)))
        ]

        # Return the geometry of the target node
        return self.graph_gdf[0].at[target_node, self.graph_gdf[0].geometry.name]

    def run(self) -> GeoDataFrame:
        self.gdf[self.gdf.geometry.name] = self.gdf[self.gdf.geometry.name].apply(self._mask_point)
        self.gdf = self.gdf.to_crs(self.crs)
        return self.gdf
