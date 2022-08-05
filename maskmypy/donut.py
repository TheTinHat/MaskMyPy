from math import sqrt, pi
from random import SystemRandom, random

from geopandas import GeoDataFrame, sjoin
from numpy import random
from shapely.affinity import translate

from .mask import Base


class Donut(Base):
    def __init__(
        self,
        *args,
        max_distance=250,
        donut_ratio=0.1,
        distribution="uniform",
        seed="",
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.max = max_distance
        self.distribution = distribution
        self.donut_ratio = donut_ratio

        if not seed:
            self.seed = int(SystemRandom().random() * (10**10))
        elif seed:
            self.seed = seed

        self.rng = random.default_rng(seed=self.seed)

    def _random_xy(self, min, max):
        if self.distribution == "uniform":
            hypotenuse = self.rng.uniform(min, max)
            x = self.rng.uniform(0, hypotenuse)

        elif self.distribution == "gaussian":
            mean = ((max - min) / 2) + min
            sigma = ((max - min) / 2) / 2.5
            hypotenuse = self.rng.normal(mean, sigma)
            x = self.rng.uniform(0, hypotenuse)

        elif self.distribution == "areal":
            hypotenuse = 0
            while hypotenuse == 0:
                r1 = self.rng.uniform(min, max)
                r2 = self.rng.uniform(min, max)
                if r1 > r2:
                    hypotenuse = r1
            x = self.rng.uniform(0, hypotenuse)

        else:
            raise Exception("Unknown distribution")

        y = sqrt(hypotenuse**2 - x**2)

        direction = self.rng.random()

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

    def _find_radii(self):
        self.masked.loc[:, "mmp_radius_min"] = self.max * self.donut_ratio
        self.masked.loc[:, "mmp_radius_max"] = self.max

    def _mask_within_container(self):
        self.masked.loc[:, "mmp_contain"] = 0

        while min(self.masked["mmp_contain"]) == 0:
            uncontained = self.masked.loc[self.masked["mmp_contain"] == 0, :]

            for index, row in uncontained.iterrows():
                x, y = self._random_xy(row["mmp_radius_min"], row["mmp_radius_max"])

                self.masked.at[index, "geometry"] = translate(
                    self.sensitive.at[index, "geometry"], xoff=x, yoff=y
                )

            self._containment(uncontained)
        return True

    def execute(self):
        self.masked = self.sensitive.copy()

        self._find_radii()

        self.masked["mmp_offset"] = self.masked.apply(
            lambda x: self._random_xy(x["mmp_radius_min"], x["mmp_radius_max"]), axis=1
        )

        self.masked["geometry"] = self.masked.apply(
            lambda x: translate(
                x["geometry"], xoff=x["mmp_offset"][0], yoff=x["mmp_offset"][1]
            ),
            axis=1,
        )

        if isinstance(self.container, GeoDataFrame):
            self._mask_within_container()

        self.masked = self.masked.drop(["mmp_offset"], axis=1)

        return self.masked


class Donut_MaxK(Donut):
    def __init__(self, *args, max_k_anonymity=0, **kwargs):
        super().__init__(*args, **kwargs)

        self.target_k = max_k_anonymity

    def _find_radii(self):

        self.population["mmp_pop_area"] = self.population.area

        join = sjoin(self.masked, self.population, how="left")

        join["mmp_max_area"] = join.apply(
            lambda x: self.target_k * x["mmp_pop_area"] / x[self.pop_column], axis=1
        )

        join["mmp_min_area"] = join.apply(
            lambda x: (self.target_k * self.donut_ratio)
            * x["mmp_pop_area"]
            / x[self.pop_column],
            axis=1,
        )

        join["mmp_max_radius"] = join.apply(
            lambda x: sqrt(x["mmp_max_area"] / pi), axis=1
        )

        join["mmp_min_radius"] = join.apply(
            lambda x: sqrt(x["mmp_min_area"] / pi), axis=1
        )

        self.masked["mmp_radius_min"] = join.apply(lambda x: x["mmp_min_radius"], axis=1)
        self.masked["mmp_radius_max"] = join.apply(lambda x: x["mmp_max_radius"], axis=1)


class Donut_Multiply(Donut):
    def __init__(self, *args, population_multiplier=0, **kwargs):
        super().__init__(*args, **kwargs)

        self.pop_multiplier = population_multiplier - 1

    def _find_radii(self):
        self.population["mmp_pop_area"] = self.population.area

        join = sjoin(self.masked, self.population, how="left")

        pop_min = min(join[self.pop_column])
        pop_max = max(join[self.pop_column])
        pop_range = pop_max - pop_min

        join["mmp_pop_score"] = join.apply(
            lambda x: (1 - (x[self.pop_column] - pop_min) / pop_range)
            * self.pop_multiplier,
            axis=1,
        )

        self.masked["mmp_radius_max"] = join.apply(
            lambda x: (x["mmp_pop_score"] * self.max) + self.max, axis=1
        )

        self.masked["mmp_radius_min"] = self.masked.apply(
            lambda x: x["mmp_radius_max"] * self.donut_ratio, axis=1
        )
