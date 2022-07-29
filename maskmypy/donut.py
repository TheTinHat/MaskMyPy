from geopandas import GeoDataFrame, sjoin
from random import random, gauss, uniform
from .mask import Base
from shapely.affinity import translate
from math import sqrt


class Donut(Base):
    def __init__(
        self,
        sensitive_gdf,
        population_gdf="",
        population_column="pop",
        max_distance=250,
        donut_ratio=0.1,
        distribution="uniform",
        container_gdf="",
        address_points_gdf="",
        max_tries=1000,
    ):

        super().__init__(
            sensitive_gdf=sensitive_gdf,
            population_gdf=population_gdf,
            population_column=population_column,
            container_gdf=container_gdf,
            max_tries=max_tries,
            address_points_gdf=address_points_gdf,
        )

        self.max = max_distance
        self.distribution = distribution
        self.donut_ratio = donut_ratio

    def _random_xy(self, min, max):
        if self.distribution == "uniform":
            hypotenuse = uniform(min, max)
            x = uniform(0, hypotenuse)

        elif self.distribution == "gaussian":
            mean = ((max - min) / 2) + min
            sigma = ((max - min) / 2) / 2.5
            hypotenuse = gauss(mean, sigma)
            x = uniform(0, hypotenuse)

        elif self.distribution == "areal":
            hypotenuse = 0
            while hypotenuse == 0:
                r1 = uniform(min, max)
                r2 = uniform(min, max)
                if r1 > r2:
                    hypotenuse = r1
            x = uniform(0, hypotenuse)

        else:
            raise Exception("Unknown distribution")

        y = sqrt(hypotenuse**2 - x**2)

        direction = random()

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
        self.masked.loc[:, "radius_min"] = self.max * self.donut_ratio
        self.masked.loc[:, "radius_max"] = self.max

    def _mask_within_container(self):
        self.masked.loc[:, "contain"] = 0

        while min(self.masked["contain"]) == 0:
            uncontained = self.masked.loc[self.masked["contain"] == 0, :]

            for index, row in uncontained.iterrows():
                x, y = self._random_xy(row["radius_min"], row["radius_max"])

                self.masked.at[index, "geometry"] = translate(
                    self.sensitive.at[index, "geometry"], xoff=x, yoff=y
                )

            self._containment(uncontained)
        return True

    def execute(self):
        self.masked = self.sensitive.copy()

        self._find_radii()

        self.masked["offset"] = self.masked.apply(
            lambda x: self._random_xy(x["radius_min"], x["radius_max"]), axis=1
        )

        self.masked["geometry"] = self.masked.apply(
            lambda x: translate(
                x["geometry"], xoff=x["offset"][0], yoff=x["offset"][1]
            ),
            axis=1,
        )

        if isinstance(self.container, GeoDataFrame):
            self._mask_within_container()

        self.masked = self.masked.drop(["offset"], axis=1)

        return self.masked


class Donut_MaxK(Donut):
    def __init__(
        self,
        sensitive_gdf,
        population_gdf="",
        population_column="pop",
        max_k_anonymity=0,
        donut_ratio=0.1,
        distribution="uniform",
        container_gdf="",
        address_points_gdf="",
        max_tries=1000,
    ):

        super().__init__(
            sensitive_gdf=sensitive_gdf,
            population_gdf=population_gdf,
            population_column=population_column,
            container_gdf=container_gdf,
            max_tries=max_tries,
            address_points_gdf=address_points_gdf,
            donut_ratio=donut_ratio,
            distribution=distribution,
        )

        self.target_k = max_k_anonymity

    def _find_radii(self):

        self.population["pop_area"] = self.population.area

        join = sjoin(self.masked, self.population, how="left")

        join["max_area"] = join.apply(
            lambda x: self.target_k * x["pop_area"] / x[self.pop_column], axis=1
        )

        join["min_area"] = join.apply(
            lambda x: (self.target_k * self.donut_ratio)
            * x["pop_area"]
            / x[self.pop_column],
            axis=1,
        )

        join["max_radius"] = join.apply(
            lambda x: sqrt(x["max_area"] / 3.141592654), axis=1
        )

        join["min_radius"] = join.apply(
            lambda x: sqrt(x["min_area"] / 3.141592654), axis=1
        )

        self.masked["radius_min"] = join.apply(lambda x: x["min_radius"], axis=1)
        self.masked["radius_max"] = join.apply(lambda x: x["max_radius"], axis=1)


class Donut_Multiply(Donut):
    def __init__(
        self,
        sensitive_gdf,
        max_distance=250,
        population_gdf="",
        population_column="pop",
        population_multiplier=0,
        donut_ratio=0.1,
        distribution="uniform",
        container_gdf="",
        address_points_gdf="",
        max_tries=1000,
    ):

        super().__init__(
            sensitive_gdf=sensitive_gdf,
            max_distance=max_distance,
            population_gdf=population_gdf,
            population_column=population_column,
            container_gdf=container_gdf,
            max_tries=max_tries,
            address_points_gdf=address_points_gdf,
            donut_ratio=donut_ratio,
            distribution=distribution,
        )

        self.pop_multiplier = population_multiplier - 1

    def _find_radii(self):
        self.population["pop_area"] = self.population.area

        join = sjoin(self.masked, self.population, how="left")

        pop_min = min(join[self.pop_column])
        pop_max = max(join[self.pop_column])
        pop_range = pop_max - pop_min

        join["pop_score"] = join.apply(
            lambda x: (1 - (x[self.pop_column] - pop_min) / pop_range)
            * self.pop_multiplier,
            axis=1,
        )

        self.masked["radius_max"] = join.apply(
            lambda x: (x["pop_score"] * self.max) + self.max, axis=1
        )

        self.masked["radius_min"] = self.masked.apply(
            lambda x: x["radius_max"] * self.donut_ratio, axis=1
        )
