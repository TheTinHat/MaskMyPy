from dataclasses import dataclass
from math import sqrt
from random import SystemRandom

import geopandas as gpd
from numpy import random
from shapely.affinity import translate
from shapely import voronoi_polygons
from shapely.ops import nearest_points
from .. import tools
from ..messages import *


@dataclass
class Voronoi:
    gdf: gpd.GeoDataFrame

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
        return new_geometry

    def run(self):
        self._generate_voronoi_polygons()
        self.mdf[self.mdf.geometry.name] = self.mdf[self.mdf.geometry.name].apply(
            self._mask_geometry
        )

        parameters = {
            "mask": "voronoi",
        }

        return self.mdf, parameters
