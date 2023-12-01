from dataclasses import dataclass

from geopandas import GeoDataFrame, GeoSeries
from shapely import Point, voronoi_polygons
from shapely.ops import nearest_points

from .. import tools


def voronoi(gdf: GeoDataFrame, snap_to_streets: bool = False) -> GeoDataFrame:
    gdf = gdf.copy()
    _validate_voronoi(gdf)

    args = locals()
    del args["snap_to_streets"]

    masked_gdf = _Voronoi(**args).run()

    if snap_to_streets:
        masked_gdf = tools.snap_to_streets(masked_gdf)

    return masked_gdf


def _validate_voronoi(gdf):
    tools._validate_geom_type(gdf, "Point")


@dataclass
class _Voronoi:
    gdf: GeoDataFrame

    def _generate_voronoi_polygons(self) -> GeoSeries:
        points = self.gdf.dissolve()
        return voronoi_polygons(points.geometry, only_edges=True)

    def _mask_point(self, point: Point) -> Point:
        return nearest_points(point, self.voronoi)[1][0]

    def run(self) -> GeoDataFrame:
        self.voronoi = self._generate_voronoi_polygons()
        self.gdf[self.gdf.geometry.name] = self.gdf[self.gdf.geometry.name].apply(self._mask_point)

        return self.gdf
