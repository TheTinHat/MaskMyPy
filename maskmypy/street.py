from typing import Union
from warnings import warn

from networkx import single_source_dijkstra_path_length
from osmnx import graph_from_polygon, graph_to_gdfs
from osmnx.distance import add_edge_lengths, nearest_nodes
from osmnx.utils_graph import remove_isolated_nodes

from .mask import Mask
import maskmypy.tools as tools


class Street(Mask):
    def __init__(
        self,
        *args,
        min_depth: int = 18,
        max_depth: int = 20,
        max_length: Union[int, float] = 500,
        **kwargs,
    ):
        """Constructs a street masking class that (when run) anonymizes points by randomly
        displacing them based on the surrounding street network using OpenStreetMap.

        Does not support containment.

        Parameters
        ----------
        secret : GeoDataFrame
            Secret layer of points that require anonymization.
            All other GeoDataFrame inputs must match the CRS of the secret point layer.
        min_depth : int, optional
            The minimum number of nodes to traverse along the street network. Default: `18`
        max_depth : int, optional
            The maximum number of nodes to traverse along the street network. Default: `20`
        max_length : int, float, optional
            When initially locating each point on the street network, MaskMyPy verifies
            that the nearest node is actually connected to the network and has neighbors
            that are no more than `max_length` away (in meters). If not, the next closest point
            is selected and checked the same way. This acts as a sanity check to prevent
            extremely large masking distances, such as might be caused by highways. Default: `500`.
        padding : int, float, optional
            Context layers (e.g. population, address, container, street network) are
            automatically cropped to the extent of the secret layer, plus some amount of padding
            to reduce edge effects. By default, padding is set to one fifth the *x* or *y*
            extent, whichever is larger. This parameter allows you to instead specify an exact
            amount of padding to be added. Recommended if the extent of the secret layer is either
            very small or very large. Units should match that of the secret layer's CRS.
        seed : int, optional
            Used to seed the random number generator so that masks are reproducible.
            In other words, given a certain seed, MaskMyPy will always mask data the exact same way.
            If left unspecified, a seed is randomly selected using `SystemRandom`
        population : GeoDataFrame, optional
            A polygon layer with a column describing population count.
        pop_col : str, optional
            The name of the population count column in the population polygon layer. Default: `pop`.
        address : GeoDataFrame, optional
            A layer containing address points.

        """
        super().__init__(*args, **kwargs)
        self.max_length = max_length
        self.min_depth = min_depth
        self.max_depth = max_depth

    def _load_container(self, container):
        if container is not None:
            warn("Street masking does not support containment.")

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

    def _apply_mask(self):
        self._get_osm()
        self.mask = self.mask.to_crs(epsg=4326)
        self.mask = self._street_mask(self.mask)
        self.mask = self.mask.to_crs(self.crs)
        return True

    def _sanity_check(self):
        mask_tmp = tools.displacement(self.secret, self.mask)
        assert len(self.secret) == len(self.mask)
        assert mask_tmp["_distance"].min() > 0
        assert mask_tmp["_distance"].max() < self.max_depth * self.max_length
