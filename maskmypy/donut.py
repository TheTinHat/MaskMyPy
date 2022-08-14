from math import sqrt, pi
from random import SystemRandom, random

from geopandas import GeoDataFrame, sjoin
from numpy import random
from shapely.affinity import translate

from .mask import Base


class Donut(Base):
    def __init__(
        self, *args, max_distance=500, ratio=0.2, distribution="uniform", seed="", **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.max_distance = max_distance
        self.distribution = distribution
        self.ratio = ratio

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
            hypotenuse = abs(self.rng.normal(mean, sigma))
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

    def _set_radii(self):
        self.mask.loc[:, "_r_min"] = self.max_distance * self.ratio
        self.mask.loc[:, "_r_max"] = self.max_distance

    def _mask_within_container(self):
        self.mask.loc[:, "CONTAINED"] = 0
        while min(self.mask["CONTAINED"]) == 0:
            uncontained = self.mask.loc[self.mask["CONTAINED"] == 0, :]
            for index, row in uncontained.iterrows():
                x, y = self._random_xy(row["_r_min"], row["_r_max"])
                self.mask.at[index, "geometry"] = translate(
                    self.input.at[index, "geometry"], xoff=x, yoff=y
                )
            self._containment(uncontained)
        return True

    def _displace(self, row):
        x_off, y_off = self._random_xy(row["_r_min"], row["_r_max"])
        return translate(row["geometry"], xoff=x_off, yoff=y_off)

    def run(self):
        self.mask = self.input.copy()
        self._set_radii()
        self.mask["geometry"] = self.mask.apply(
            self._displace,
            axis=1,
        )
        if isinstance(self.container, GeoDataFrame):
            self._mask_within_container()
        self.check()
        self.mask = self.mask.loc[:, ~self.mask.columns.str.startswith("_")]
        return self.mask

    def check(self):
        self.displacement_distance()
        max = self.max_distance if self.distribution != "gaussian" else self.max_distance * 1.5
        min = self.max_distance * self.ratio if self.distribution != "gaussian" else 0
        assert self.mask["_distance"].min() > min
        assert self.mask["_distance"].max() < max
        assert len(self.input) == len(self.mask)


class Donut_MaxK(Donut):
    def __init__(self, *args, max_k_anonymity, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_k = max_k_anonymity

    def _set_radii(self):
        self.population["_pop_area"] = self.population.area
        mask_pop = sjoin(self.mask, self.population, how="left")

        mask_pop["_area_max"] = mask_pop.apply(
            lambda x: self.target_k * x["_pop_area"] / x[self.pop_col], axis=1
        )
        mask_pop["_area_min"] = mask_pop.apply(
            lambda x: (self.target_k * self.ratio) * x["_pop_area"] / x[self.pop_col],
            axis=1,
        )
        mask_pop["_r_max"] = mask_pop.apply(lambda x: sqrt(x["_area_max"] / pi), axis=1)
        mask_pop["_r_min"] = mask_pop.apply(lambda x: sqrt(x["_area_min"] / pi), axis=1)
        self.mask["_r_min"] = mask_pop.apply(lambda x: x["_r_min"], axis=1)
        self.mask["_r_max"] = mask_pop.apply(lambda x: x["_r_max"], axis=1)

    def check(self):
        self.displacement_distance()
        assert self.mask["_distance"].min() > 0
        assert len(self.input) == len(self.mask)


class Donut_Multiply(Donut):
    def __init__(self, *args, population_multiplier, **kwargs):
        super().__init__(*args, **kwargs)
        self.pop_multiplier = population_multiplier - 1

    def _set_radii(self):
        self.population["_pop_area"] = self.population.area
        mask_pop = sjoin(self.mask, self.population, how="left")
        pop_min = min(mask_pop[self.pop_col])
        pop_max = max(mask_pop[self.pop_col])
        pop_range = pop_max - pop_min
        pop_range = pop_range if pop_range > 0 else 1
        mask_pop["_pop_score"] = mask_pop.apply(
            lambda x: (1 - (x[self.pop_col] - pop_min) / pop_range) * self.pop_multiplier,
            axis=1,
        )
        self.mask["_r_max"] = mask_pop.apply(
            lambda x: (x["_pop_score"] * self.max_distance) + self.max_distance, axis=1
        )
        self.mask["_r_min"] = self.mask.apply(lambda x: x["_r_max"] * self.ratio, axis=1)

    def check(self):
        self.displacement_distance()
        assert self.mask["_distance"].min() > 0
        assert len(self.input) == len(self.mask)
