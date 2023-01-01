from math import sqrt
from random import SystemRandom

import geopandas as gpd
from shapely.affinity import translate
from shapely.geometry import LineString, Point, Polygon

from .candidate import Candidate
from .validation import *


def donut(sensitive_gdf, min, max, container=None):
    validate_input(**locals())
    sensitive_gdf["geometry"] = sensitive_gdf.geometry.translate(0.01)
    candidate = Candidate(sensitive_gdf, locals())
    return candidate


from random import SystemRandom
from typing import Optional, Union
from warnings import warn

from geopandas import GeoDataFrame, sjoin
from numpy import random

import maskmypy.tools as tools


class Mask:
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
        self,
        displacement=False,
        estimate_k=False,
        calculate_k=False,
        map_displacement=False,
    ) -> GeoDataFrame:
        """Run the masking procedure to anonymize secret points.

        Parameters
        ----------
        displacement : bool, optional
            If `True`, add a `distance` column containing the displacement distance.
        estimate_k : bool, optional
            If `True`, estimate the k-anonymity of each anonymized point based on surrounding
            population density. Requires a population layer to be loaded into the masking object.
        calculate_k : bool, optional
            If `True`, calculate the k-anonymity of each anonymized point based on nearby address
            points. Requires an address layer to be loaded into the masking class.
        map_displacement : bool, optional
            If `True`, output a file called `displacement_map.png` that visualizes displacement
            distance between secret and masked points.

        Returns
        -------
        GeoDataFrame
            A GeoDataFrame of anonymized points.
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
