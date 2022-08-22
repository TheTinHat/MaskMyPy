from typing import Optional
from warnings import warn

import contextily as ctx
import matplotlib.pyplot as plt
from geopandas import GeoDataFrame, sjoin
from shapely.geometry import LineString


class Base:
    """Base class for masking methods"""

    def __init__(
        self,
        secret: GeoDataFrame,
        population: Optional[GeoDataFrame] = None,
        pop_col: str = "pop",
        container: Optional[GeoDataFrame] = None,
        address: Optional[GeoDataFrame] = None,
        max_tries: int = 1000,
    ):
        self.secret = secret.copy()
        self.crs = self.secret.crs
        self.max_tries = max_tries
        self._load_population(population, pop_col)
        self._load_container(container)
        self._load_address(address)

    def _load_population(self, population, pop_col="pop"):
        """Loads a geodataframe of population data for donut masking and/or k-anonymity estimation."""
        if isinstance(population, GeoDataFrame):
            assert population.crs == self.crs
            self.pop_col = pop_col
            self.population = self._crop(population.copy(), self.secret).loc[
                :, ["geometry", self.pop_col]
            ]
            return self.population

    def _load_container(self, container):
        """Loads a geodataframe of polygons to contain points while donut masking"""
        if isinstance(container, GeoDataFrame):
            assert container.crs == self.crs
            self.container = self._crop(container.copy(), self.secret).loc[:, ["geometry"]]
            return self.container

    def _load_address(self, address):
        """Loads geodataframe containing address data for k-anonymity calculation"""
        if isinstance(address, GeoDataFrame):
            assert address.crs == self.crs
            self.address = self._crop(address.copy(), self.secret).loc[:, ["geometry"]]
            return self.address

    def _crop(self, target, reference):
        """Uses spatial index to reduce an target geodataframe to
        that which intersects with a reference geodataframe"""
        bb = reference.total_bounds
        if len(set(bb)) == 2:  # If reference is single point, skip crop
            return target
        x = (bb[2] - bb[0]) / 2
        y = (bb[3] - bb[1]) / 2
        bb[0] = bb[0] - x
        bb[1] = bb[1] - y
        bb[2] = bb[2] + x
        bb[3] = bb[3] + y
        return target.cx[bb[0] : bb[2], bb[1] : bb[3]]

    def _sanity_check(self):
        pass

    def _apply_mask(self):
        pass

    def _sanitize(self):
        self.mask = self.mask.loc[:, ~self.mask.columns.str.startswith("_")]
        return True

    def run(self, parallel=False) -> GeoDataFrame:
        self.try_count = 0
        self.mask = self.secret.copy()

        if parallel is True:
            self._apply_mask(parallel=True)
        else:
            self._apply_mask()

        self._sanity_check()
        self._sanitize()
        return self.mask

    def displacement(self) -> GeoDataFrame:
        """Calculate dispalcement distance for each point after masking."""
        self.mask["_distance"] = self.mask.geometry.distance(self.secret.geometry)
        return self.mask

    def map_displacement(self, filename=""):
        lines = self.mask.copy()
        lines = lines.join(self.secret, how="left", rsuffix="_secret")
        lines.geometry = lines.apply(
            lambda x: LineString([x["geometry"], x["geometry_secret"]]), axis=1
        )
        ax = lines.plot(color="black", zorder=1, linewidth=1, figsize=[10, 10])
        ax = self.secret.plot(ax=ax, color="red", zorder=2, markersize=12)
        ax = self.mask.plot(ax=ax, color="blue", zorder=3, markersize=12)
        if hasattr(self, "container"):
            ax = self.container.plot(ax=ax, color="grey", zorder=0, linewidth=1)
        if hasattr(self, "address"):
            ax = self.address.plot(ax=ax, color="grey", markersize=2)
        ctx.add_basemap(ax, crs=self.crs, source=ctx.providers.OpenStreetMap.Mapnik)
        plt.title("Displacement Distances", fontsize=16)
        plt.figtext(
            0.5,
            0.025,
            "Secret points (red), Masked points (blue). \n KEEP CONFIDENTIAL",
            wrap=True,
            horizontalalignment="center",
            fontsize=12,
        )
        if filename:
            plt.savefig(filename)
        else:
            plt.show()
        return True

    def estimate_k(
        self, population: Optional[GeoDataFrame] = None, pop_col: str = "pop"
    ) -> GeoDataFrame:
        """Estimates k-anoynmity based on population data."""
        if population:
            self._load_population(population, pop_col)

        self.population["_pop_area"] = self.population.area

        self.mask["k_est"] = (
            self.displacement()
            .assign(geometry=lambda x: x.geometry.buffer(x["_distance"]), axis=1)
            .pipe(self._disaggregate_population)
            .groupby("_index_2")["_pop_adjusted"]
            .sum()
            .round()
        )
        return self.mask

    def calculate_k(self, address: Optional[GeoDataFrame] = None) -> GeoDataFrame:
        """Calculates k-anonymity based on the number of address points that are closer
        to the masked point than secret point"""
        if address:
            self._load_address(address)

        mask_tmp = self.displacement().assign(geometry=lambda x: x.buffer(x["_distance"]))
        self.mask["k_calc"] = (
            sjoin(self.address, mask_tmp, how="left", rsuffix="mask").groupby("index_mask").size()
        )
        self.mask.fillna({"k_calc": 0}, inplace=True)
        return self.mask

    def _disaggregate_population(self, target):
        """Used for estimating k-anonymity. Disaggregates population within
        buffers based on population polygon data"""
        target = (
            sjoin(target, self.population, how="left", rsuffix="pop")
            .rename_axis("_index_2")
            .reset_index()
        )
        target.geometry = target.apply(
            lambda x: x.geometry.intersection(self.population.at[x["index_pop"], "geometry"]),
            axis=1,
        )
        target["_intersected_area"] = target.geometry.area
        for i, _ in enumerate(target.index):
            polygon_fragments = target.loc[target["_index_2"] == i, :]
            for index, row in polygon_fragments.iterrows():
                area_pct = row["_intersected_area"] / row["_pop_area"]
                target.at[index, "_pop_adjusted"] = row[self.pop_col] * area_pct
        return target

    def _containment(self, target):
        """Checks whether or not mask points are within the same containment
        polygon as their original locations."""
        if "index_cont" not in self.secret.columns:
            self.secret = sjoin(self.secret, self.container, how="left", rsuffix="cont")
        target = sjoin(target, self.container, how="left", rsuffix="cont")
        for index, row in target.iterrows():
            if row["index_cont"] == self.secret.at[index, "index_cont"]:
                self.mask.at[index, "CONTAINED"] = 1
        self.try_count += 1
        if self.try_count > self.max_tries:

            for index, row in target.iterrows():
                self.mask.loc[index, "CONTAINED"] = 0
            warn(
                f"One or more points were masked but could not be contained. Target points are listed as 0 in the 'CONTAINED' field"
            )
        return self.mask
