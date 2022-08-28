from math import pi, sqrt
from typing import Union

from geopandas import GeoDataFrame, sjoin
from shapely.affinity import translate

from .mask import Base
from .tools import displacement


class Donut(Base):
    """Donut masking class. Randomly displaces points between a given
    minimum and maximum distance.

    Parameters
    ----------
    Base : _type_
        _description_
    min_distance : int, float
        The minimum distance that points should be displaced
    max_distance : int, float
        The maximum distance that points should be displaced
    """

    def __init__(
        self,
        *args,
        min_distance: Union[int, float] = 50,
        max_distance: Union[int, float] = 500,
        distribution: str = "uniform",
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.min_distance = min_distance
        self.max_distance = max_distance
        self.distribution = distribution

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
        self.mask.loc[:, "_r_min"] = self.min_distance
        self.mask.loc[:, "_r_max"] = self.max_distance

    def _mask_within_container(self):
        self.mask.loc[:, "CONTAINED"] = -1
        while min(self.mask["CONTAINED"]) == -1:
            uncontained = self.mask.loc[self.mask["CONTAINED"] == -1, :]
            for index, row in uncontained.iterrows():
                self.mask.at[index, "geometry"] = self._displace_point(
                    row, custom_geom=self.secret.at[index, "geometry"]
                )
            self._containment(uncontained)
        return True

    def _displace_point(self, row, custom_geom=""):
        x_off, y_off = self._random_xy(row["_r_min"], row["_r_max"])
        if not custom_geom:
            return translate(row["geometry"], xoff=x_off, yoff=y_off)
        elif custom_geom:
            return translate(custom_geom, xoff=x_off, yoff=y_off)

    def _apply_mask(self) -> GeoDataFrame:
        self._set_radii()
        self.mask.geometry = self.mask.apply(
            self._displace_point,
            axis=1,
        )
        if hasattr(self, "container"):
            self._mask_within_container()
        return True

    def _sanity_check(self):
        mask_tmp = displacement(self.secret, self.mask)
        max = self.max_distance if self.distribution != "gaussian" else self.max_distance * 1.5
        min = self.min_distance if self.distribution != "gaussian" else 0
        assert mask_tmp["_distance"].min() > min
        assert mask_tmp["_distance"].max() < max
        assert len(self.secret) == len(self.mask)


class Donut_K(Donut):
    def __init__(self, *args, min_k_anonymity, max_k_anonymity, **kwargs):
        super().__init__(*args, **kwargs)
        self.min_k: int = min_k_anonymity
        self.max_k: int = max_k_anonymity

    def _set_radii(self):
        self.population["_pop_area"] = self.population.area
        mask_pop = (
            sjoin(self.mask, self.population, how="left")
            .assign(_area_max=lambda x: self.max_k * x["_pop_area"] / x[self.pop_col])
            .assign(_area_min=lambda x: self.min_k * x["_pop_area"] / x[self.pop_col])
        )
        self.mask["_r_min"] = mask_pop.apply(lambda x: sqrt(x["_area_min"] / pi), axis=1)
        self.mask["_r_max"] = mask_pop.apply(lambda x: sqrt(x["_area_max"] / pi), axis=1)

    def _sanity_check(self):
        mask_tmp = displacement(self.secret, self.mask)
        assert mask_tmp["_distance"].min() > 0
        assert len(self.secret) == len(self.mask)


class Donut_Multiply(Donut):
    def __init__(self, *args, population_multiplier, **kwargs):
        super().__init__(*args, **kwargs)
        self.pop_multiplier: int = population_multiplier - 1

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
        self.mask["_r_min"] = mask_pop.apply(
            lambda x: (x["_pop_score"] * self.min_distance) + self.min_distance, axis=1
        )

    def _sanity_check(self):
        mask_tmp = displacement(self.secret, self.mask)
        assert mask_tmp["_distance"].min() > 0
        assert len(self.secret) == len(self.mask)
