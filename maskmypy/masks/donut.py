from dataclasses import dataclass
from math import sqrt
from random import SystemRandom

import geopandas as gpd
from numpy import random
from shapely.affinity import translate
from .. import tools
from .. import messages as msg


@dataclass
class Donut:
    gdf: gpd.GeoDataFrame
    low: float
    high: float
    container: gpd.GeoDataFrame = None
    distribution: str = "uniform"
    seed: int = None
    padding: float = 0.2

    def __post_init__(self):
        # Initialize random number generator
        self.seed = int(SystemRandom().random() * (10**10)) if not self.seed else self.seed
        self._rng = random.default_rng(seed=self.seed)

        # Validate and initialize input parameters
        tools.validate_geom_type(self.gdf, "Point")
        self.mdf = self.gdf.copy(deep=True)

        if self.low >= self.high:
            raise ValueError("Minimum displacement distance is larger than or equal to maximum.")

        if self.container is not None:
            tools.validate_geom_type(self.container, "Polygon", "MultiPolygon")
            if self.container.crs != self.mdf.crs:
                raise ValueError("Container CRS does not match that of sensitive GeoDataFrame.")

    def _generate_random_offset(self):
        if self.distribution == "uniform":
            hypotenuse = self._rng.uniform(self.low, self.high)
            x = self._rng.uniform(0, hypotenuse)
        elif self.distribution == "gaussian":
            mean = ((self.high - self.low) / 2) + self.low
            sigma = ((self.high - self.low) / 2) / 2.5
            hypotenuse = abs(self._rng.normal(mean, sigma))
            x = self._rng.uniform(0, hypotenuse)
        elif self.distribution == "areal":
            hypotenuse = 0
            while hypotenuse == 0:
                r1 = self._rng.uniform(self.low, self.high)
                r2 = self._rng.uniform(self.low, self.high)
                if r1 > r2:
                    hypotenuse = r1
            x = self._rng.uniform(0, hypotenuse)
        else:
            raise ValueError("Unknown distribution")

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

    def _mask_geometry(self, geometry):
        xoff, yoff = self._generate_random_offset()
        new_geometry = translate(geometry, xoff=xoff, yoff=yoff)
        return new_geometry

    def _mask_contained_geometry(self, geometry):
        intersection = self.container.intersects(geometry)
        intersected_polygons = set(
            intersection[intersection].index
        )  # Filter for rows where intersection == True, convert to set for later comparison
        start = intersected_polygons if len(intersected_polygons) > 0 else -1
        if len(start) > 1:
            raise ValueError(
                f"Point at {geometry} intersects {len(start)} polygons in the container. Container polygons must not overlap."
            )
        end = None
        while start != end:
            new_geometry = self._mask_geometry(geometry)
            intersection = self.container.intersects(new_geometry)
            intersected_polygons = set(intersection[intersection].index)
            end = intersected_polygons if len(intersected_polygons) > 0 else -1
        return new_geometry

    def run(self):
        if isinstance(self.container, gpd.GeoDataFrame):
            self.mdf[self.mdf.geometry.name] = self.mdf[self.mdf.geometry.name].apply(
                self._mask_contained_geometry
            )
        else:
            self.mdf[self.mdf.geometry.name] = self.mdf[self.mdf.geometry.name].apply(
                self._mask_geometry
            )

        return self.mdf

    @property
    def params(self):
        return {
            "mask": "donut",
            "low": self.low,
            "high": self.high,
            "container": True if isinstance(self.container, gpd.GeoDataFrame) else False,
            "distribution": self.distribution,
            "seed": self.seed,
            "padding": self.padding,
        }
