from math import sqrt
from random import SystemRandom
from numpy import random
import geopandas as gpd
from shapely.affinity import translate
from shapely.geometry import LineString, Point, Polygon
from dataclasses import dataclass, field

from .candidate import Candidate
from . import validation
from . import tools
from .messages import *


@dataclass
class Donut:
    gdf: gpd.GeoDataFrame
    min: float
    max: float
    container: gpd.GeoDataFrame = None
    distribution: str = "uniform"
    seed: int = None
    padding: float = None

    def __post_init__(self):
        self._rng = random.default_rng(seed=self.seed)
        self.gdf = self.gdf.copy(deep=True)
        tools.assert_geom_type(self.gdf, "Point")
        self.crs = self.gdf.crs
        assert self.max > self.min

        if self.seed is None:
            self.seed = int(SystemRandom().random() * (10**10))

        if self.container is not None:
            assert self.container.crs == self.crs
            tools.assert_geom_type(self.container, "Polygon", "MultiPolygon")
            self.container = self.container.copy(deep=True)
            self.container = tools.crop(self.container, self.gdf.total_bounds, self.padding)
            self.container = self.container.loc[:, [self.container.geometry.name]]

    def _validate_input(self):
        self.cr

    def _random_xy(self):
        if self.distribution == "uniform":
            hypotenuse = self._rng.uniform(self.min, self.max)
            x = self._rng.uniform(0, hypotenuse)
        elif self.distribution == "gaussian":
            mean = ((max - min) / 2) + min
            sigma = ((max - min) / 2) / 2.5
            hypotenuse = abs(self._rng.normal(mean, sigma))
            x = self._rng.uniform(0, hypotenuse)
        elif self.distribution == "areal":
            hypotenuse = 0
            while hypotenuse == 0:
                r1 = self._rng.uniform(self.min, self.max)
                r2 = self._rng.uniform(self.min, self.max)
                if r1 > r2:
                    hypotenuse = r1
            x = self._rng.uniform(0, hypotenuse)
        else:
            raise Exception("Unknown distribution")

        y = sqrt(hypotenuse**2 - x**2)
        direction = self._rng.random()
        if direction < 0.25:
            x = x * -1
        elif direction < 0.5:
            y = y * -1
        elif direction < 0.75:
            x = x * -1
            y = y * -1
        elif direction < 1:
            pass

        return (x, y)

    def _displace(self, geometry):
        if self.container is not None:
            intersection = self.container.intersects(geometry)
            # Get index of container polygons where intersection == True
            intersection = set(intersection[intersection].index)
            start = intersection if len(intersection) > 0 else -1
            assert len(start) < 2, multiple_container_intersection_msg
            end = None
            while start != end:
                xoff, yoff = self._random_xy()
                new_geometry = translate(geometry, xoff=xoff, yoff=yoff)
                intersection = self.container.intersects(new_geometry)
                # Get index of container polygons where intersection == True
                intersection = set(intersection[intersection].index)
                end = intersection if len(intersection) > 0 else -1
        else:
            xoff, yoff = self._random_xy()
            new_geometry = translate(geometry, xoff=xoff, yoff=yoff)

        return new_geometry

    def run(self):
        self.gdf[self.gdf.geometry.name] = self.gdf[self.gdf.geometry.name].apply(self._displace)

        parameters = {
            "min": self.min,
            "max": self.max,
            "container": True if isinstance(self.container, gpd.GeoDataFrame) else False,
            "distribution": self.distribution,
            "seed": self.seed,
            "padding": self.padding,
        }

        self.candidate = Candidate(self.gdf, parameters)
        return self.candidate
