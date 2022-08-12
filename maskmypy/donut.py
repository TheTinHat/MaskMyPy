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

    def _find_radii(self):
        self.masked.loc[:, "_radius_min"] = self.max_distance * self.ratio
        self.masked.loc[:, "_radius_max"] = self.max_distance

    def _mask_within_container(self):
        self.masked.loc[:, "CONTAINED"] = 0
        while min(self.masked["CONTAINED"]) == 0:
            uncontained = self.masked.loc[self.masked["CONTAINED"] == 0, :]
            for index, row in uncontained.iterrows():
                x, y = self._random_xy(row["_radius_min"], row["_radius_max"])
                self.masked.at[index, "geometry"] = translate(
                    self.sensitive.at[index, "geometry"], xoff=x, yoff=y
                )
            self._containment(uncontained)
        return True

    def execute(self):
        self.masked = self.sensitive.copy()
        self._find_radii()
        self.masked["_offset"] = self.masked.apply(
            lambda x: self._random_xy(x["_radius_min"], x["_radius_max"]), axis=1
        )
        self.masked["geometry"] = self.masked.apply(
            lambda x: translate(x["geometry"], xoff=x["_offset"][0], yoff=x["_offset"][1]),
            axis=1,
        )
        if isinstance(self.container, GeoDataFrame):
            self._mask_within_container()
        self.check()
        self.masked = self.masked.loc[:, ~self.masked.columns.str.startswith("_")]
        return self.masked

    def check(self):
        self.displacement_distance()
        max = self.max_distance if self.distribution != "gaussian" else self.max_distance * 1.5
        min = self.max_distance * self.ratio if self.distribution != "gaussian" else 0
        assert (
            self.masked["_displace_dist"].min() > min
        ), "Displacement distance is less than minimum."
        assert (
            self.masked["_displace_dist"].max() < max
        ), "Displacement distance is greater than maximum."
        assert len(self.sensitive) == len(
            self.masked
        ), "Masked data not same length as sensitive data."


class Donut_MaxK(Donut):
    def __init__(self, *args, max_k_anonymity, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_k = max_k_anonymity

    def _find_radii(self):
        self.population["_pop_area"] = self.population.area
        masked_pop = sjoin(self.masked, self.population, how="left")

        masked_pop["_max_area"] = masked_pop.apply(
            lambda x: self.target_k * x["_pop_area"] / x[self.pop_column], axis=1
        )
        masked_pop["_min_area"] = masked_pop.apply(
            lambda x: (self.target_k * self.ratio) * x["_pop_area"] / x[self.pop_column],
            axis=1,
        )
        masked_pop["_max_radius"] = masked_pop.apply(lambda x: sqrt(x["_max_area"] / pi), axis=1)
        masked_pop["_min_radius"] = masked_pop.apply(lambda x: sqrt(x["_min_area"] / pi), axis=1)
        self.masked["_radius_min"] = masked_pop.apply(lambda x: x["_min_radius"], axis=1)
        self.masked["_radius_max"] = masked_pop.apply(lambda x: x["_max_radius"], axis=1)

    def check(self):
        self.displacement_distance()
        assert self.masked["_displace_dist"].min() > 0, "Displacement distance is zero."
        assert len(self.sensitive) == len(
            self.masked
        ), "Masked data not same length as sensitive data."


class Donut_Multiply(Donut):
    def __init__(self, *args, population_multiplier, **kwargs):
        super().__init__(*args, **kwargs)
        self.pop_multiplier = population_multiplier - 1

    def _find_radii(self):
        self.population["_pop_area"] = self.population.area
        join = sjoin(self.masked, self.population, how="left")
        pop_min = min(join[self.pop_column])
        pop_max = max(join[self.pop_column])
        pop_range = pop_max - pop_min
        pop_range = pop_range if pop_range > 0 else 1
        join["_pop_score"] = join.apply(
            lambda x: (1 - (x[self.pop_column] - pop_min) / pop_range) * self.pop_multiplier,
            axis=1,
        )
        self.masked["_radius_max"] = join.apply(
            lambda x: (x["_pop_score"] * self.max_distance) + self.max_distance, axis=1
        )
        self.masked["_radius_min"] = self.masked.apply(
            lambda x: x["_radius_max"] * self.ratio, axis=1
        )

    def check(self):
        self.displacement_distance()
        assert self.masked["_displace_dist"].min() > 0, "Displacement distance is zero."
        assert len(self.sensitive) == len(
            self.masked
        ), "Masked data not same length as sensitive data."
