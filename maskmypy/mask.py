from random import SystemRandom
from typing import Optional, Union
from warnings import warn

from geopandas import GeoDataFrame, sjoin
from numpy import random

from .tools import sanitize


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
                f"One or more points were masked but could not be contained. Uncontained points are listed as 0 in the 'CONTAINED' field"
            )
        return self.mask

    def run(self) -> GeoDataFrame:
        """Initiates the masking procedure.

        Returns
        -------
        GeoDataFrame
            A GeoDataFrame containing masked points.
        """
        self.try_count = 0
        self.mask = self.secret.copy()
        self._apply_mask()
        self._sanity_check()
        return sanitize(self.mask)
