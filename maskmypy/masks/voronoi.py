from dataclasses import dataclass

from geopandas import GeoDataFrame, GeoSeries
from osmnx import graph_to_gdfs
from osmnx.distance import nearest_nodes
from osmnx.graph import graph_from_bbox
from osmnx.projection import project_graph
from osmnx.utils_graph import remove_isolated_nodes
from shapely import Point, voronoi_polygons
from shapely.ops import nearest_points

from .. import messages as msg
from .. import tools


@dataclass
class Voronoi:
    gdf: GeoDataFrame
    snap: bool = True

    def __post_init__(self) -> None:
        # Validate and initialize input parameters
        tools.validate_geom_type(self.gdf, "Point")
        self.mdf = self.gdf.copy(deep=True)

    def _generate_voronoi_polygons(self) -> GeoSeries:
        points = self.mdf.dissolve()
        return voronoi_polygons(points.geometry, only_edges=True)

    def _mask_point(self, point: Point) -> Point:
        return nearest_points(point, self.voronoi)[1][0]

    def run(self) -> GeoDataFrame:
        self.voronoi = self._generate_voronoi_polygons()
        self.mdf[self.mdf.geometry.name] = self.mdf[self.mdf.geometry.name].apply(self._mask_point)

        if self.street:
            self.mdf = tools.snap_to_streets(self.mdf)

        return self.mdf

    @property
    def params(self) -> dict:
        return {"mask": "voronoi", "snap": self.snap}
