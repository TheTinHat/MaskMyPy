from dataclasses import dataclass
from math import sqrt

from geopandas import GeoDataFrame
from shapely import Point
from shapely.affinity import translate

from .. import tools


def donut(
    gdf: GeoDataFrame,
    low: float,
    high: float,
    container: GeoDataFrame = None,
    distribution: str = "uniform",
    seed: int = None,
    snap_to_streets: bool = False,
) -> GeoDataFrame:
    """
    Apply donut masking to a GeoDataFrame, randomly displacing points between a minimum and
    maximum distance. Advantages of this mask is speed and simplicity, though it does not
    handle highly varied population densities well.

    Example
    -------
    ```python
    from maskmypy import donut

    masked = donut(
        gdf=sensitive_points,
        min=100,
        max=1000
    )
    ```

    Parameters
    ----------
    gdf : GeoDataFrame
        GeoDataFrame containing sensitive points.
    low : float
        Minimum distance to displace points. Unit must match that of the `gdf` CRS.
    high : float
        Maximum displacement to displace points. Unit must match that of the `gdf` CRS.
    container : GeoDataFrame
        A  GeoDataFrame containing polygons within which intersecting sensitive points should
        remain after masking. This works by masking a point, checking if it intersects
        the same polygon prior to masking, and retrying until it does. Useful for preserving
        statistical relationships, such as census tract, or to ensure that points are not
        displaced into impossible locations, such as the ocean. CRS must match that of `gdf`.
    distribution : str
        The distribution used to determine masking distances. `uniform` provides
        a flat distribution where any value between the minimum and maximum distance is
        equally likely to be selected. `areal` is more likely to select distances that are
        further away. The `gaussian` distribution uses a normal distribution, where values
        towards the middle of the range are most likely to be selected. Note that gaussian
        distribution has a small chance of selecting values beyond the defined minimum and
        maximum.
    seed : int
        Used to seed the random number generator so that masked datasets are reproducible.
        Randomly generated if left undefined.
    snap_to_streets : bool
        If True, points are snapped to the nearest node on the OSM street network after masking.
        This can reduce the chance of false-attribution.

    Returns
    -------
    GeoDataFrame
        A GeoDataFrame containing masked points.
    """
    _gdf = gdf.copy()
    _validate_donut(_gdf, low, high, container)

    seed = tools.gen_seed() if not seed else seed

    args = locals()
    del args["snap_to_streets"]
    del args["gdf"]

    masked_gdf = _Donut(**args).run()

    if snap_to_streets:
        masked_gdf = tools.snap_to_streets(masked_gdf)

    return masked_gdf


def _validate_donut(gdf, low, high, container):
    tools._validate_geom_type(gdf, "Point")

    if low >= high:
        raise ValueError("Minimum displacement distance is greater than or equal to maximum.")

    if container is not None:
        if not isinstance(container, GeoDataFrame):
            raise ValueError("Container is not a valid GeoDataFrame")
        tools._validate_geom_type(container, "Polygon", "MultiPolygon")
        tools._validate_crs(gdf.crs, container.crs)


@dataclass
class _Donut:
    _gdf: GeoDataFrame
    low: float
    high: float
    container: GeoDataFrame = None
    distribution: str = "uniform"
    seed: int = None

    def __post_init__(self) -> None:
        self._rng = tools.gen_rng(seed=self.seed)

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
            self._gdf[self._gdf.geometry.name] = self._gdf[self._gdf.geometry.name].apply(
                self._mask_contained_point
            )
        else:
            self._gdf[self._gdf.geometry.name] = self._gdf[self._gdf.geometry.name].apply(
                self._mask_point
            )

        return self._gdf
