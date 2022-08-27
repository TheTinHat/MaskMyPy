from multiprocessing import Pool, cpu_count
from random import SystemRandom
from typing import Union, Optional

from geopandas import GeoDataFrame
from networkx import single_source_dijkstra_path_length
from numpy import array_split, random
from osmnx import graph_from_polygon, graph_to_gdfs
from osmnx.distance import add_edge_lengths, nearest_nodes
from osmnx.utils_graph import remove_isolated_nodes
from pandas import concat

from .mask import Base
from .tools import displacement


class Street(Base):
    def __init__(
        self,
        *args,
        min_depth: int = 18,
        max_depth: int = 20,
        max_length: Union[int, float] = 500,
        seed: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.max_length = max_length
        self.min_depth = min_depth
        self.max_depth = max_depth

        if not seed:
            self.seed = int(SystemRandom().random() * (10**10))
        elif seed:
            self.seed = seed

        self.rng = random.default_rng(seed=self.seed)

    def _get_osm(self):
        polygon = (
            self.secret.copy()
            .assign(geometry=lambda x: x.geometry.buffer(self.padding))
            .to_crs(epsg=4326)
            .geometry.unary_union.convex_hull
        )
        self.graph = add_edge_lengths(
            remove_isolated_nodes(
                graph_from_polygon(
                    polygon=polygon,
                    network_type="drive",
                    simplify=True,
                    truncate_by_edge=True,
                    clean_periphery=True,
                )
            )
        )
        self.graph_gdf = graph_to_gdfs(self.graph)
        return True

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

    def _street_mask_parallel(self):
        cpus = cpu_count() - 1 if cpu_count() > 1 else 1
        pool = Pool(processes=cpus)
        chunks = array_split(self.mask, cpus)
        processes = [pool.apply_async(self._street_mask, args=(chunk,)) for chunk in chunks]
        mask_chunks = [chunk.get() for chunk in processes]
        mask = GeoDataFrame(concat(mask_chunks))
        mask = mask.set_crs(epsg=4326)
        return mask

    def _apply_mask(self, parallel=False):
        self._get_osm()
        self.mask = self.mask.to_crs(epsg=4326)
        if parallel == True:
            self.mask = self._street_mask_parallel()
        else:
            self.mask = self._street_mask(self.mask)
        self.mask = self.mask.to_crs(self.crs)
        return True

    def _sanity_check(self):
        mask_tmp = displacement(self.secret, self.mask)
        assert len(self.secret) == len(self.mask)
        assert mask_tmp["_distance"].min() > 0
        assert mask_tmp["_distance"].max() < self.max_depth * self.max_length
