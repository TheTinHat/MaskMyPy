from dataclasses import dataclass

import geopandas as gpd
from osmnx import graph_to_gdfs
from osmnx.distance import nearest_nodes
from osmnx.graph import graph_from_bbox
from osmnx.projection import project_graph
from osmnx.utils_graph import remove_isolated_nodes
from shapely import voronoi_polygons
from shapely.ops import nearest_points

from .. import tools
from .. import messages


@dataclass
class Voronoi:
    gdf: gpd.GeoDataFrame
    street: bool = True

    def __post_init__(self):
        # Validate and initialize input parameters
        tools.validate_geom_type(self.gdf, "Point")
        self.mdf = self.gdf.copy(deep=True)

    def _generate_random_offset(self):
        pass

    def _generate_voronoi_polygons(self):
        points = self.mdf.dissolve()
        self.voronoi = voronoi_polygons(points.geometry, only_edges=True)

    def _mask_geometry(self, geometry):
        new_geometry = nearest_points(geometry, self.voronoi)[1][0]

        if self.street:
            node = nearest_nodes(self.graph, new_geometry.x, new_geometry.y)
            new_geometry = self.node_gdf.at[node, self.node_gdf.geometry.name]

        return new_geometry

    def _get_osm(self):
        bbox = self.mdf.to_crs(epsg=4326).total_bounds
        self.graph = remove_isolated_nodes(
            graph_from_bbox(
                north=bbox[3],
                south=bbox[1],
                west=bbox[0],
                east=bbox[2],
                network_type="drive",
                truncate_by_edge=True,
            )
        )

        self.graph = project_graph(self.graph, to_crs=self.gdf.crs)
        self.node_gdf = graph_to_gdfs(self.graph)[0]

    def run(self):
        self._generate_voronoi_polygons()
        if self.street:
            self._get_osm()

        self.mdf[self.mdf.geometry.name] = self.mdf[self.mdf.geometry.name].apply(
            self._mask_geometry
        )
        return self.mdf

    @property
    def params(self):
        return {"mask": "voronoi", "street": self.street}
