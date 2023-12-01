from dataclasses import dataclass

from geopandas import GeoDataFrame
from numpy import random
from shapely import Point

from .. import tools


def locationswap(
    gdf: GeoDataFrame,
    low: float,
    high: float,
    address: GeoDataFrame,
    seed: int = None,
    snap_to_streets: bool = False,
):
    gdf = gdf.copy()
    _validate_locationswap(gdf, low, high, address)

    seed = tools.gen_seed() if not seed else seed

    args = locals()
    del args["snap_to_streets"]

    masked_gdf = _LocationSwap(**args).run()

    if snap_to_streets:
        masked_gdf = tools.snap_to_streets(masked_gdf)

    return masked_gdf


def _validate_locationswap(gdf, low, high, address):
    tools._validate_geom_type(gdf, "Point")
    tools._validate_geom_type(address, "Point")
    tools._validate_crs(gdf.crs, address.crs)

    if low >= high:
        raise ValueError("Minimum displacement distance is larger than or equal to maximum.")


@dataclass
class _LocationSwap:
    gdf: GeoDataFrame
    low: float
    high: float
    address: GeoDataFrame
    seed: int = None

    def __post_init__(self) -> None:
        # Initialize random number generator
        self._rng = random.default_rng(seed=self.seed)

    def _mask_point(self, point: Point) -> Point:
        min_buffer = point.buffer(self.low)
        max_buffer = point.buffer(self.high)

        excluded_locations = self.address.intersects(min_buffer)
        excluded_locations = set(excluded_locations[excluded_locations].index)

        included_locations = self.address.intersects(max_buffer)
        included_locations = set(included_locations[included_locations].index)

        included_locations = list(included_locations.difference(excluded_locations))
        if len(included_locations) > 0:
            return self.address.iloc[self._rng.choice(included_locations)].geometry
        else:
            return Point(0, 0)

    def run(self) -> GeoDataFrame:
        self.gdf[self.gdf.geometry.name] = self.gdf[self.gdf.geometry.name].apply(self._mask_point)
        return self.gdf
