from dataclasses import dataclass
from random import SystemRandom

from geopandas import GeoDataFrame
from numpy import random
from shapely import Point
from .. import tools


@dataclass
class LocationSwap:
    gdf: GeoDataFrame
    low: float
    high: float
    addresses: GeoDataFrame
    seed: int = None
    padding: float = 0.2

    def __post_init__(self) -> None:
        # Initialize random number generator
        self.seed = int(SystemRandom().random() * (10**10)) if not self.seed else self.seed
        self._rng = random.default_rng(seed=self.seed)

        # Validate and initialize input parameters
        tools.validate_geom_type(self.gdf, "Point")
        self.mdf = self.gdf.copy(deep=True)

        if self.low >= self.high:
            raise ValueError("Minimum displacement distance is larger than or equal to maximum.")

        tools.validate_geom_type(self.addresses, "Point")
        tools.validate_crs(self.gdf.crs, self.addresses.crs)

    def _mask_point(self, point: Point) -> Point:
        min_buffer = point.buffer(self.low)
        max_buffer = point.buffer(self.high)

        excluded_locations = self.addresses.intersects(min_buffer)
        excluded_locations = set(excluded_locations[excluded_locations].index)

        included_locations = self.addresses.intersects(max_buffer)
        included_locations = set(included_locations[included_locations].index)

        included_locations = list(included_locations.difference(excluded_locations))
        if len(included_locations) > 0:
            return self.addresses.iloc[self._rng.choice(included_locations)].geometry
        else:
            return Point(0, 0)

    def run(self) -> GeoDataFrame:
        self.mdf[self.mdf.geometry.name] = self.mdf[self.mdf.geometry.name].apply(self._mask_point)
        return self.mdf

    @property
    def params(self) -> dict:
        return {
            "mask": "location_swapping",
            "low": self.low,
            "high": self.high,
            "seed": self.seed,
            "padding": self.padding,
        }
