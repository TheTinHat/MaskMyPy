from dataclasses import dataclass

from geopandas import GeoDataFrame, GeoSeries
from shapely import Point, voronoi_polygons
from shapely.ops import nearest_points

from .. import tools
from .abstract_mask import AbstractMask


@dataclass
class Voronoi(AbstractMask):
    gdf: GeoDataFrame
    snap: bool = True

    def __post_init__(self) -> None:
        # Validate and initialize input parameters
        tools.validate_geom_type(self.gdf, "Point")
        self.mdf = self.gdf.copy()

    def _generate_voronoi_polygons(self) -> GeoSeries:
        points = self.mdf.dissolve()
        return voronoi_polygons(points.geometry, only_edges=True)

    def _mask_point(self, point: Point) -> Point:
        return nearest_points(point, self.voronoi)[1][0]

    def run(self) -> GeoDataFrame:
        self.voronoi = self._generate_voronoi_polygons()
        self.mdf[self.mdf.geometry.name] = self.mdf[self.mdf.geometry.name].apply(self._mask_point)

        if self.snap:
            self.mdf = tools.snap_to_streets(self.mdf)

        return self.mdf

    @property
    def params(self) -> dict:
        return {"mask": "voronoi", "snap": self.snap}
