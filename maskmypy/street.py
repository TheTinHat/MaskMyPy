from multiprocessing import Pool, cpu_count
from typing import Union

from geopandas import GeoDataFrame
from networkx import single_source_dijkstra_path_length
from numpy import array_split
from osmnx import graph_from_bbox, graph_to_gdfs
from osmnx.distance import add_edge_lengths, nearest_nodes
from osmnx.utils_graph import remove_isolated_nodes
from pandas import concat

from .mask import Base


class Street(Base):
    def __init__(
        self,
        *args,
        depth: int = 20,
        padding: Union[int, float] = 2000,
        max_length: Union[int, float] = 500,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.padding = padding
        self.max_length = max_length
        self.depth = depth

    def _get_osm(self):
        selection = self.mask.buffer(self.padding)
        selection = selection.to_crs(epsg=4326)
        bb = selection.total_bounds
        self.graph = graph_from_bbox(
            north=bb[3],
            south=bb[1],
            east=bb[2],
            west=bb[0],
            network_type="drive",
            simplify=True,
            truncate_by_edge=True,
        )
        self.graph = remove_isolated_nodes(self.graph)
        self.graph = add_edge_lengths(self.graph)
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
        distance = 250
        threshold = self.depth

        while node_count < threshold:
            paths = single_source_dijkstra_path_length(self.graph, node, distance, "length")
            node_count = len(paths)
            distance += 250

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
        graph_tmp = self.graph.copy()
        mask["_node"] = mask.apply(lambda x: self._nearest_node(graph_tmp, x["geometry"]), axis=1)
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
        self.displacement()
        assert len(self.secret) == len(self.mask)
        assert self.mask["_distance"].min() > 0
        assert self.mask["_distance"].max() < self.depth * self.max_length
