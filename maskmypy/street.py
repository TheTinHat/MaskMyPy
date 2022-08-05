from multiprocessing import Pool, cpu_count

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
        depth=20,
        extent_expansion_distance=2000,
        max_street_length=500,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.buffer_dist = extent_expansion_distance
        self.max_street_length = max_street_length
        self.depth = depth

    def _get_osm(self):
        selection = self.masked.buffer(self.buffer_dist)
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

    def _nearest_node(self, graph_temporary, geometry):
        neighbor_count = 0
        while neighbor_count < 1:
            node = nearest_nodes(
                graph_temporary, geometry.centroid.x, geometry.centroid.y
            )

            neighbor_count = len(self._find_neighbors(node))

            if neighbor_count == 0:
                graph_temporary.remove_node(node)

        return node

    def _find_neighbors(self, node):
        neighbors = list(self.graph.neighbors(node))
        for neighbor in neighbors:
            length = self.graph.get_edge_data(node, neighbor)[0]["length"]

            if length > self.max_street_length:
                neighbors = [n for n in neighbors if n != neighbor]

        return neighbors

    def _street_mask(self, node):
        node_count = 0
        distance = 250
        threshold = self.depth

        while node_count < threshold:
            paths = single_source_dijkstra_path_length(
                self.graph, node, distance, "length"
            )
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

    def _apply_street_mask(self, masked):

        graph_temporary = self.graph.copy()

        masked["node"] = masked.apply(
            lambda x: self._nearest_node(graph_temporary, x["geometry"]), axis=1
        )

        masked["node_new"] = masked.apply(
            lambda x: self._street_mask(x["node"]), axis=1
        )

        masked["geometry"] = masked.apply(
            lambda x: self.graph_gdf[0].at[x["node_new"], "geometry"], axis=1
        )

        masked = masked.drop(["node", "node_new"], axis=1)

        return masked

    def execute(self, parallel=False):
        self.masked = self.sensitive.copy()

        self._get_osm()

        self.masked = self.masked.to_crs(epsg=4326)

        if parallel == True:
            self.masked = self.execute_parallel()
        else:
            self.masked = self._apply_street_mask(self.masked)

        self.masked = self.masked.to_crs(self.crs)
        return self.masked

    def execute_parallel(self):
        cpus = cpu_count() - 1
        pool = Pool(processes=cpus)
        chunks = array_split(self.masked, cpus)

        processes = [
            pool.apply_async(self._apply_street_mask, args=(chunk,)) for chunk in chunks
        ]

        masked_chunks = [chunk.get() for chunk in processes]
        gdf = GeoDataFrame(concat(masked_chunks))
        gdf = gdf.set_crs(epsg=4326)
        return gdf
