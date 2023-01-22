from networkx import single_source_dijkstra_path_length
from osmnx import graph_from_polygon, graph_to_gdfs
from osmnx.distance import add_edge_lengths, nearest_nodes
from osmnx.utils_graph import remove_isolated_nodes
from osmnx.graph import graph_from_bbox
import geopandas as gpd
from . import tools
from math import sqrt
from random import SystemRandom
from numpy import random
import geopandas as gpd
from shapely.affinity import translate
from shapely.geometry import LineString, Point, Polygon
from dataclasses import dataclass, field

from .candidate import Candidate
from . import validation
from . import tools
from .messages import *


@dataclass
class Street:
    gdf: gpd.GeoDataFrame
    min: float
    max: float
    max_length: float
    seed: int = None
    padding: float = 0.2

    def __post_init__(self):
        # Initialize random number generator
        self.seed = int(SystemRandom().random() * (10**10)) if not self.seed else self.seed
        self._rng = random.default_rng(seed=self.seed)

        # Validate and initialize input parameters
        tools.validate_geom_type(self.gdf, "Point")
        self.crs = self.gdf.crs
        self.gdf = self.gdf.copy(deep=True).to_crs(epsg=4326)

        if self.min >= self.max:
            raise ValueError("Minimum is larger than or equal to maximum.")

        self._get_osm()

    def _get_osm(self):
        bbox = tools.pad(self.gdf.total_bounds)
        self.graph = add_edge_lengths(
            remove_isolated_nodes(
                graph_from_bbox(
                    north=bbox[0],
                    south=bbox[2],
                    west=bbox[1],
                    east=bbox[3],
                    network="drive",
                    truncate_by_edge=True,
                )
            )
        )
        self.graph_gdf = graph_to_gdfs(self.graph)
        return True

    def run(self):
        self.gdf[self.gdf.geometry.name] = self.gdf[self.gdf.geometry.name].apply(
            self._mask_geometry
        )
        self.gdf = self.gdf.to_crs(self.crs)

        parameters = {
            "min": self.min,
            "max": self.max,
            "max_length": self.max_length,
            "seed": self.seed,
            "padding": self.padding,
        }

        self.candidate = Candidate(self.gdf, parameters)
        return self.candidate


""" 




"""


class Street(Mask):
    def __init__(
        self,
        *args,
        min_depth: int = 18,
        max_depth: int = 20,
        max_length: float = 500,
        **kwargs,
    ):

        super().__init__(*args, **kwargs)
        self.max_length = max_length
        self.min_depth = min_depth
        self.max_depth = max_depth

    def _nearest_node(self, graph_tmp, geometry):
        neighbor_count = 0
        while neighbor_count < 1:
            node = nearest_nodes(graph_tmp, geometry.centroid.x, geometry.centroid.y)
            neighbor_count = len(self._find_neighbors(node))
            if neighbor_count == 0:
                graph_tmp.remove_node(node)
        return node

    def _find_neighbors(self, node):
        neighbors = list(self.graph.neighbors(node))
        for neighbor in neighbors:
            length = self.graph.get_edge_data(node, neighbor)[0]["length"]
            if length > self.max_length:
                neighbors = [n for n in neighbors if n != neighbor]
        return neighbors

    def _find_node(self, node):
        node_count = 0
        distance = 500
        threshold = self.rng.integers(self.min_depth, self.max_depth, endpoint=False)
        while node_count < threshold:
            paths = single_source_dijkstra_path_length(self.graph, node, distance, "length")
            node_count = len(paths)
            distance += 500

        nodes = []
        distances = []
        total_distance = 0
        i = 0

        for key, value in paths.items():
            nodes.append(key)
            distances.append(value)
            total_distance += value
            i += 1
            if i == threshold:
                break

        candidate_distance = total_distance / threshold
        idx = distances.index(min(distances, key=lambda x: abs(x - candidate_distance)))
        node = nodes[idx]
        return node

    def _street_mask(self, mask):
        mask["_node"] = mask.apply(
            lambda x: self._nearest_node(self.graph.copy(), x["geometry"]), axis=1
        )
        mask["_node_new"] = mask.apply(lambda x: self._find_node(x["_node"]), axis=1)
        mask.geometry = mask.apply(
            lambda x: self.graph_gdf[0].at[x["_node_new"], "geometry"], axis=1
        )
        mask = mask.drop(["_node", "_node_new"], axis=1)
        return mask

    def _apply_mask(self):
        self._get_osm()
        self.mask = self.mask.to_crs(epsg=4326)
        self.mask = self._street_mask(self.mask)
        self.mask = self.mask.to_crs(self.crs)
        return True
