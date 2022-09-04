from random import SystemRandom
from typing import Optional, Union
from warnings import warn

from geopandas import GeoDataFrame, sjoin
from numpy import random

import maskmypy.tools as tools


class Base:
    def __init__(
        self,
        secret: GeoDataFrame,
        population: Optional[GeoDataFrame] = None,
        pop_col: str = "pop",
        container: Optional[GeoDataFrame] = None,
        address: Optional[GeoDataFrame] = None,
        padding: Union[int, float, None] = None,
        max_tries: int = 1000,
        seed: Optional[int] = None,
    ):
        """Constructs a base masking class to be inherited by other masking classes.

        Parameters
        ----------
        secret : GeoDataFrame
            Secret layer of points that require anonymization.
            All other GeoDataFrame inputs must match the CRS of the secret point layer. Required.
        population : GeoDataFrame, optional
            A polygon layer with a column describing population count.
        pop_col : str, optional
            The name of the population count column in the population polygon layer. Default: `pop`
        container : GeoDataFrame, optional
            A layer containing polygons within which intersecting secret points should remain
            after masking is complete. This works by masking a point, checking if it intersects
            the same polygon prior to masking, and retrying until it does. The number of attempts
            is controlled by the `max_tries` parameter. Useful for preserving statistical values,
            such as from census tracts, or to ensure that points are not displaced into impossible
            locations, such as the ocean.
        address : GeoDataFrame, optional
            A layer containing address points.
        padding : int, float, optional
            Supplementary layers (e.g. population, address, container, street network) are
            automatically cropped to the extent of the secret layer, plus some amount of padding
            to reduce edge effects. By default, padding is set to one fifth the *x* or *y*
            extent, whichever is larger. This parameter allows you to instead specify an exact
            amount of padding to be added. Recommended if the extent of the secret layer is either
            very small or very large. Units should match that of the secret layer's CRS.
        max_tries : int, optional
            The maximum number of times that MaskMyPy should re-mask a point until it is
            contained within the corresponding polygon (see `container` parameter). Default: `1000`
        seed : int, optional
            Used to seed the random number generator so that masks are reproducible.
            In other words, given a certain seed, MaskMyPy will always mask data the exact same way.
            Default: randomly selected using `SystemRandom`
        """
        self.secret = secret.copy()
        self.crs = self.secret.crs
        self.max_tries = max_tries
        self.padding = self._calculate_padding(padding)
        self._load_population(population, pop_col)
        self._load_container(container)
        self._load_address(address)

        if not seed:
            self.seed = int(SystemRandom().random() * (10**10))
        elif seed:
            self.seed = seed

        self.rng = random.default_rng(seed=self.seed)

    def _load_population(self, population, pop_col="pop"):
        if isinstance(population, GeoDataFrame):
            assert population.crs == self.crs
            self.pop_col = pop_col
            self.population = self._crop(population.copy(), self.secret).loc[
                :, ["geometry", self.pop_col]
            ]
            return self.population

    def _load_container(self, container):
        if isinstance(container, GeoDataFrame):
            assert container.crs == self.crs
            self.container = self._crop(container.copy(), self.secret).loc[:, ["geometry"]]
            return self.container

    def _load_address(self, address):
        if isinstance(address, GeoDataFrame):
            assert address.crs == self.crs
            self.address = self._crop(address.copy(), self.secret).loc[:, ["geometry"]]
            return self.address

    def _calculate_padding(self, padding):
        if padding is None:
            bb = self.secret.total_bounds
            pad_x = (bb[2] - bb[0]) / 5
            pad_y = (bb[3] - bb[1]) / 5
            padding = max(pad_x, pad_y)
        return padding

    def _crop(self, target, reference):
        bb = reference.total_bounds
        if len(set(bb)) == 2:  # If reference is single point, skip crop
            return target

        bb[0] = bb[0] - self.padding
        bb[1] = bb[1] - self.padding
        bb[2] = bb[2] + self.padding
        bb[3] = bb[3] + self.padding
        return target.cx[bb[0] : bb[2], bb[1] : bb[3]]

    def _sanity_check(self):
        pass

    def _apply_mask(self):
        pass

    def _containment(self, gdf):
        if "index_cont" not in self.secret.columns:
            self.secret = sjoin(self.secret, self.container, how="left", rsuffix="cont")
        gdf = sjoin(gdf, self.container, how="left", rsuffix="cont")
        for index, row in gdf.iterrows():
            if row["index_cont"] == self.secret.at[index, "index_cont"]:
                self.mask.at[index, "CONTAINED"] = 1
        self.try_count += 1
        if self.try_count > self.max_tries:

            for index, row in gdf.iterrows():
                self.mask.loc[index, "CONTAINED"] = 0
            warn(
                "One or more points were masked but could not be contained. "
                "Uncontained points are listed as 0 in the 'CONTAINED' field"
            )
        return self.mask

    def run(
        self, displacement=False, estimate_k=False, calculate_k=False, map_displacement=False
    ) -> GeoDataFrame:
        """_summary_

        Parameters
        ----------
        displacement : bool, optional
            _description_, by default False
        estimate_k : bool, optional
            _description_, by default False
        calculate_k : bool, optional
            _description_, by default False
        map_displacement : bool, optional
            _description_, by default False

        Returns
        -------
        GeoDataFrame
            _description_
        """
        self.try_count = 0
        self.mask = self.secret.copy()
        self._apply_mask()
        self._sanity_check()
        self.mask = tools.sanitize(self.mask)

        if displacement:
            self.mask = tools.displacement(self.secret, self.mask, "distance")
        if estimate_k:
            self.mask = tools.estimate_k(self.secret, self.mask, self.population, self.pop_col)
        if calculate_k:
            self.mask = tools.calculate_k(self.secret, self.mask, self.address)
        if map_displacement:
            tools.map_displacement(self.secret, self.mask, "displacement_map.png")
        return self.mask
