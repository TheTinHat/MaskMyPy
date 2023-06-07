from copy import deepcopy
from dataclasses import dataclass
from random import SystemRandom

from geopandas import GeoDataFrame
from networkx import single_source_dijkstra_path_length
from numpy import random
from osmnx import graph_to_gdfs
from osmnx.distance import add_edge_lengths, nearest_nodes
from osmnx.graph import graph_from_bbox
from osmnx.utils_graph import remove_isolated_nodes
from shapely import Point

from .. import messages as msg
from .. import tools
from .abstract_mask import AbstractMask


@dataclass
class Street(AbstractMask):
    gdf: GeoDataFrame
    low: int
    high: int
    max_length: float = 1000
    seed: int = None
    padding: float = 0.2

    def __post_init__(self) -> None:
        # Initialize random number generator
        self.seed = int(SystemRandom().random() * (10**10)) if not self.seed else self.seed
        self._rng = random.default_rng(seed=self.seed)

        # Validate and initialize input parameters
        tools.validate_geom_type(self.gdf, "Point")
        self.crs = self.gdf.crs
        self.mdf = self.gdf.copy(deep=True).to_crs(epsg=4326)

        if self.low >= self.high:
            raise ValueError("Minimum is larger than or equal to maximum.")

        self._get_osm()

    def _get_osm(self) -> None:
        bbox = tools.pad(self.mdf.total_bounds, self.padding)
        self.graph = add_edge_lengths(
            remove_isolated_nodes(
                graph_from_bbox(
                    north=bbox[3],
                    south=bbox[1],
                    west=bbox[0],
                    east=bbox[2],
                    network_type="drive",
                    truncate_by_edge=True,
                )
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
        distance = 1000

        # Search for surrounding nodes until number of nodes found equals or exceeds target_node_count
        while node_count < target_node_count:
            paths = single_source_dijkstra_path_length(
                G=self.graph, source=node_id, cutoff=distance, weight="length"
            )
            node_count = len(paths)

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
        self.mdf[self.mdf.geometry.name] = self.mdf[self.mdf.geometry.name].apply(self._mask_point)
        self.mdf = self.mdf.to_crs(self.crs)
        return self.mdf

    @property
    def params(self) -> dict:
        return {
            "mask": "street",
            "low": self.low,
            "high": self.high,
            "max_length": self.max_length,
            "seed": self.seed,
            "padding": self.padding,
        }
