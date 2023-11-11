from math import pi, sqrt
from typing import Union

from geopandas import GeoDataFrame, sjoin
from shapely.affinity import translate

import maskmypy.tools as tools

from .mask import Mask


class Donut(Mask):
    def __init__(
        self,
        *args,
        min_distance: Union[int, float] = 50,
        max_distance: Union[int, float] = 500,
        distribution: str = "uniform",
        **kwargs
    ):
        """Constructs a donut masking class that (when run) anonymizes points by randomly
        displacing them between a minimum and maximum distance.

        Parameters
        ----------
        secret : GeoDataFrame
            Secret layer of points that require anonymization.
            All other GeoDataFrame inputs must match the CRS of the secret point layer.
        min_distance : int, float
            The minimum distance that points should be displaced. Default: `50`.
        max_distance : int, float
            The maximum distance that points should be displaced. Default: `500`.
        distribution : str, optional
            The distribution used to determine masking distances. The default `uniform` provides
            a flat distribution where any value between the minimum and maximum distance is
            equally likely to be selected. The `areal` distribution is more likely to select
            distances that are further away. The `gaussian` distribution uses a normal
            distribution, where values towards the middle of the range are most likely to be
            selected. Note that gaussian distribution has a small chance of selecting values
            beyond the defined minimum and maximum. Default: `uniform`.
        padding : int, float, optional
            Context layers (e.g. population, address, container, street network) are
            automatically cropped to the extent of the secret layer, plus some amount of padding
            to reduce edge effects. By default, padding is set to one fifth the *x* or *y*
            extent, whichever is larger. This parameter allows you to instead specify an exact
            amount of padding to be added. Recommended if the extent of the secret layer is either
            very small or very large. Units should match that of the secret layer's CRS.
        max_tries : int, optional
            The maximum number of times that MaskMyPy should re-mask a point until it is
            contained within the corresponding polygon (see `container` parameter). Default: `1000`.
        seed : int, optional
            Used to seed the random number generator so that masks are reproducible.
            In other words, given a certain seed, MaskMyPy will always mask data the exact same way.
            If left unspecified, a seed is randomly selected using `SystemRandom`
        population : GeoDataFrame, optional
            A polygon layer with a column describing population count.
        pop_col : str, optional
            The name of the population count column in the population polygon layer. Default: `pop`.
        container : GeoDataFrame, optional
            A layer containing polygons within which intersecting secret points should remain
            after masking. This works by masking a point, checking if it intersects
            the same polygon prior to masking, and retrying until it does. The number of attempts
            is controlled by the `max_tries` parameter. Useful for preserving statistical values,
            such as from census tracts, or to ensure that points are not displaced into impossible
            locations, such as the ocean.
        address : GeoDataFrame, optional
            A layer containing address points.

        """
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
        mask_tmp = tools.displacement(self.secret, self.mask)
        max = self.max_distance if self.distribution != "gaussian" else self.max_distance * 1.5
        min = self.min_distance if self.distribution != "gaussian" else 0
        assert mask_tmp["_distance"].min() > min
        assert mask_tmp["_distance"].max() < max
        assert len(self.secret) == len(self.mask)


class Donut_K(Donut):
    def __init__(self, *args, min_k: int, max_k: int, **kwargs):
        """Constructs a masking class that (when run) anonymizes points by randomly displacing
        them according to a desired k-anonymity range. Note that the k-anonymity values only
        reflect the population density of the immediate polygon the point falls within,
        and do not take into account any neighboring polygons.

        Requires a population layer.

        Parameters
        ----------
        secret : GeoDataFrame
            Secret layer of points that require anonymization.
            All other GeoDataFrame inputs must match the CRS of the secret point layer.
        min_k : int
            The minimum desired k-anonymity for each point. Please read description above to learn
            the limitations of this calculation.
        max_k : int
            The maximum desired k-anonymity for each point. Please read description above to learn
            the limitations of this calculation.
        padding : int, float, optional
            Context layers (e.g. population, address, container, street network) are
            automatically cropped to the extent of the secret layer, plus some amount of padding
            to reduce edge effects. By default, padding is set to one fifth the *x* or *y*
            extent, whichever is larger. This parameter allows you to instead specify an exact
            amount of padding to be added. Recommended if the extent of the secret layer is either
            very small or very large. Units should match that of the secret layer's CRS.
        max_tries : int, optional
            The maximum number of times that MaskMyPy should re-mask a point until it is
            contained within the corresponding polygon (see `container` parameter). Default: `1000`.
        seed : int, optional
            Used to seed the random number generator so that masks are reproducible.
            In other words, given a certain seed, MaskMyPy will always mask data the exact same way.
            If left unspecified, a seed is randomly selected using `SystemRandom`
        population : GeoDataFrame, optional
            A polygon layer with a column describing population count.
        pop_col : str, optional
            The name of the population count column in the population polygon layer. Default: `pop`.
        container : GeoDataFrame, optional
            A layer containing polygons within which intersecting secret points should remain
            after masking. This works by masking a point, checking if it intersects
            the same polygon prior to masking, and retrying until it does. The number of attempts
            is controlled by the `max_tries` parameter. Useful for preserving statistical values,
            such as from census tracts, or to ensure that points are not displaced into impossible
            locations, such as the ocean.
        address : GeoDataFrame, optional
            A layer containing address points.
        """
        super().__init__(*args, **kwargs)
        self.min_k: int = min_k
        self.max_k: int = max_k

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
        mask_tmp = tools.displacement(self.secret, self.mask)
        assert mask_tmp["_distance"].min() > 0
        assert len(self.secret) == len(self.mask)


class Donut_Multiply(Donut):
    def __init__(self, *args, population_multiplier: Union[int, float] = 5, **kwargs):
        """Constructs a masking class that (when run) anonymizes points by randomly displacing
        them according to a minimum and maximum distance, but with an additional multiplier
        to help take population density into account. Points in the most population-dense polygons
        will have their minimum and maximum masking distances multiplied by 1. This multiplier
        will increase linearly as population density decreases, with points in the least
        population-dense polygons having their minimum and maximum masking distances multiplied
        by the full `population_mulitplier` value.

        Requires a population layer.

        Parameters
        ----------
        secret : GeoDataFrame
            Secret layer of points that require anonymization.
            All other GeoDataFrame inputs must match the CRS of the secret point layer.
        min_distance : int, float
            The minimum distance that points should be displaced.
        max_distance : int, float
            The maximum distance that points should be displaced.
        population_multiplier : int, float
            The maximum possible multiplier used to extend masking distances according to
            population density.
        padding : int, float, optional
            Context layers (e.g. population, address, container, street network) are
            automatically cropped to the extent of the secret layer, plus some amount of padding
            to reduce edge effects. By default, padding is set to one fifth the *x* or *y*
            extent, whichever is larger. This parameter allows you to instead specify an exact
            amount of padding to be added. Recommended if the extent of the secret layer is either
            very small or very large. Units should match that of the secret layer's CRS.
        max_tries : int, optional
            The maximum number of times that MaskMyPy should re-mask a point until it is
            contained within the corresponding polygon (see `container` parameter). Default: `1000`.
        seed : int, optional
            Used to seed the random number generator so that masks are reproducible.
            In other words, given a certain seed, MaskMyPy will always mask data the exact same way.
            If left unspecified, a seed is randomly selected using `SystemRandom`
        population : GeoDataFrame, optional
            A polygon layer with a column describing population count.
        pop_col : str, optional
            The name of the population count column in the population polygon layer. Default: `pop`.
        container : GeoDataFrame, optional
            A layer containing polygons within which intersecting secret points should remain
            after masking. This works by masking a point, checking if it intersects
            the same polygon prior to masking, and retrying until it does. The number of attempts
            is controlled by the `max_tries` parameter. Useful for preserving statistical values,
            such as from census tracts, or to ensure that points are not displaced into impossible
            locations, such as the ocean.
        address : GeoDataFrame, optional
            A layer containing address points.

        """
        super().__init__(*args, **kwargs)
        self.pop_multiplier: int = population_multiplier - 1

    def _set_radii(self):
        self.population["_pop_area"] = self.population.area
        mask_pop = sjoin(self.mask, self.population, how="left")
        mask_pop["_pop_density"] = mask_pop[self.pop_col] / mask_pop["_pop_area"]
        pop_density_min = min(mask_pop["_pop_density"])
        pop_density_max = max(mask_pop["_pop_density"])
        pop_range = pop_density_max - pop_density_min
        pop_range = pop_range if pop_range > 0 else 1
        mask_pop["_pop_score"] = mask_pop.apply(
            lambda x: (1 - (x["_pop_density"] - pop_density_min) / pop_range)
            * self.pop_multiplier,
            axis=1,
        )
        self.mask["_r_max"] = mask_pop.apply(
            lambda x: (x["_pop_score"] * self.max_distance) + self.max_distance, axis=1
        )
        self.mask["_r_min"] = mask_pop.apply(
            lambda x: (x["_pop_score"] * self.min_distance) + self.min_distance, axis=1
        )

    def _sanity_check(self):
        mask_tmp = tools.displacement(self.secret, self.mask)
        assert mask_tmp["_distance"].min() > 0
        assert len(self.secret) == len(self.mask)
