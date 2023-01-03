from math import sqrt
from random import SystemRandom
from numpy import random
import geopandas as gpd
from shapely.affinity import translate
from shapely.geometry import LineString, Point, Polygon

from .candidate import Candidate
from .validation import *
from .tools import *


def _random_xy(min, max, rng, distribution="uniform"):
    if distribution == "uniform":
        hypotenuse = rng.uniform(min, max)
        x = rng.uniform(0, hypotenuse)
    elif distribution == "gaussian":
        mean = ((max - min) / 2) + min
        sigma = ((max - min) / 2) / 2.5
        hypotenuse = abs(rng.normal(mean, sigma))
        x = rng.uniform(0, hypotenuse)
    elif distribution == "areal":
        hypotenuse = 0
        while hypotenuse == 0:
            r1 = rng.uniform(min, max)
            r2 = rng.uniform(min, max)
            if r1 > r2:
                hypotenuse = r1
        x = rng.uniform(0, hypotenuse)
    else:
        raise Exception("Unknown distribution")

    y = sqrt(hypotenuse**2 - x**2)
    direction = rng.random()
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


def _displace(geometry, min, max, rng, distribution, container=None):
    if container is not None:
        i = 0
        containment = container.contains(geometry)
        idx = containment[containment].index
        start = idx if len(idx) > 0 else -1
        end = None
        while start != end:
            xoff, yoff = _random_xy(min, max, rng, distribution)
            geometry = translate(geometry, xoff=xoff, yoff=yoff)
            containment = container.contains(geometry)
            idx = containment[containment].index
            end = idx if len(idx) > 0 else -1
            i += 1
            if i > 2:
                print(i)
    else:
        xoff, yoff = _random_xy(min, max, rng, distribution)
        geometry = translate(geometry, xoff=xoff, yoff=yoff)

    return geometry


def donut(
    sensitive_gdf,
    min,
    max,
    container=None,
    seed=int(SystemRandom().random() * (10**10)),
    padding=None,
    distribution="uniform",
):
    # Setup
    validate_input(**locals())
    rng = random.default_rng(seed=seed)
    sensitive_gdf = sensitive_gdf.copy(deep=True)

    if container is not None:
        container = container.copy(deep=True)
        # container = crop(container, sensitive_gdf.total_bounds, padding)
        container = container.loc[:, [container.geometry.name]]

    # Masking
    sensitive_gdf[sensitive_gdf.geometry.name] = sensitive_gdf[sensitive_gdf.geometry.name].apply(
        _displace, min=min, max=max, container=container, rng=rng, distribution=distribution
    )

    candidate = Candidate(sensitive_gdf, locals())
    return candidate
