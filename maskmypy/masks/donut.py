from dataclasses import dataclass
from math import sqrt
from random import SystemRandom

from geopandas import GeoDataFrame
from numpy import random
from shapely import Point
from shapely.affinity import translate

from .. import tools
from .abstract_mask import AbstractMask


@dataclass
class Donut(AbstractMask):
    gdf: GeoDataFrame
    low: float
    high: float
    container: GeoDataFrame = None
    distribution: str = "uniform"
    seed: int = None

    def __post_init__(self) -> None:
        # Initialize random number generator
        self.seed = int(SystemRandom().random() * (10**10)) if not self.seed else self.seed
        self._rng = random.default_rng(seed=self.seed)

        # Validate and initialize input parameters
        tools.validate_geom_type(self.gdf, "Point")
        self.mdf = self.gdf.copy()

        if self.low >= self.high:
            raise ValueError("Minimum displacement distance is larger than or equal to maximum.")

        if self.container is not None:
            tools.validate_geom_type(self.container, "Polygon", "MultiPolygon")
            tools.validate_crs(self.gdf.crs, self.container.crs)

    def _generate_random_offset(self) -> tuple[float, float]:
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

    def _mask_point(self, point: Point) -> Point:
        xoff, yoff = self._generate_random_offset()
        new_point = translate(point, xoff=xoff, yoff=yoff)
        return new_point

    def _mask_contained_point(self, point: Point) -> Point:
        intersection = self.container.intersects(point)
        intersected_polygons = set(
            intersection[intersection].index
        )  # Filter for rows where intersection == True, convert to set for later comparison
        start = intersected_polygons if len(intersected_polygons) > 0 else -1
        if len(start) > 1:
            raise ValueError(
                f"Point at {point} intersects {len(start)} polygons in the container. Container polygons must not overlap."
            )
        end = None
        while start != end:
            new_point = self._mask_point(point)
            intersection = self.container.intersects(new_point)
            intersected_polygons = set(intersection[intersection].index)
            end = intersected_polygons if len(intersected_polygons) > 0 else -1
        return new_point

    def run(self) -> GeoDataFrame:
        if isinstance(self.container, GeoDataFrame):
            self.mdf[self.mdf.geometry.name] = self.mdf[self.mdf.geometry.name].apply(
                self._mask_contained_point
            )
        else:
            self.mdf[self.mdf.geometry.name] = self.mdf[self.mdf.geometry.name].apply(
                self._mask_point
            )

        return self.mdf

    @property
    def params(self) -> dict:
        return {
            "mask": "donut",
            "low": self.low,
            "high": self.high,
            "container": True if isinstance(self.container, GeoDataFrame) else False,
            "distribution": self.distribution,
            "seed": self.seed,
        }
