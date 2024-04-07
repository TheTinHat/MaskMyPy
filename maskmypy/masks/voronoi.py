from dataclasses import dataclass

from geopandas import GeoDataFrame, GeoSeries
from shapely import Point, voronoi_polygons
from shapely.ops import nearest_points

from .. import tools


def voronoi(gdf: GeoDataFrame, snap_to_streets: bool = False) -> GeoDataFrame:
    """
    Apply voronoi masking to a GeoDataFrame, displacing points to the nearest edges of a vornoi
    diagram. Note: because voronoi masking lacks any level of randomization, snapping to streets
    is recommended for this mask to provide another level of obfuscation.

    Example
    -------
    ```python
    from maskmypy import voronoi

    masked = voronoi(
        gdf=sensitive_points,
        snap_to_streets=True
    )
    ```

    Parameters
    ----------
    gdf : GeoDataFrame
        GeoDataFrame containing sensitive points.
    snap_to_streets : bool
        If True, points are snapped to the nearest node on the OSM street network after masking.
        This can reduce the chance of false-attribution.

    Returns
    -------
    GeoDataFrame
        A GeoDataFrame containing masked points.
    """
    _gdf = gdf.copy()
    _validate_voronoi(gdf)

    args = locals()
    del args["snap_to_streets"]
    del args["gdf"]

    masked_gdf = _Voronoi(**args).run()

    if snap_to_streets:
        masked_gdf = tools.snap_to_streets(masked_gdf)

    return masked_gdf


def _validate_voronoi(gdf):
    tools._validate_geom_type(gdf, "Point")


@dataclass
class _Voronoi:
    _gdf: GeoDataFrame

    def _generate_voronoi_polygons(self) -> GeoSeries:
        points = self._gdf.dissolve()
        return voronoi_polygons(points.geometry, only_edges=True)

    def _mask_point(self, point: Point) -> Point:
        return nearest_points(point, self.voronoi)[1][0]

    def run(self) -> GeoDataFrame:
        self.voronoi = self._generate_voronoi_polygons()
        self._gdf[self._gdf.geometry.name] = self._gdf[self._gdf.geometry.name].apply(
            self._mask_point
        )

        return self._gdf
