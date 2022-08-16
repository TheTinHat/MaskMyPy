from geopandas import GeoDataFrame, sjoin


class Base:
    """Base class for masking methods"""

    def __init__(
        self,
        input,
        population="",
        pop_col="pop",
        container="",
        max_tries=1000,
        address="",
    ):
        self.input = input.copy()
        self.crs = self.input.crs
        self.max_tries = max_tries
        self._load_population(population, pop_col)
        self._load_container(container)
        self._load_address(address)

    def _load_population(self, population="", pop_col="pop"):
        """Loads a geodataframe of population data for donut masking and/or k-anonymity estimation."""
        if isinstance(population, GeoDataFrame):
            assert population.crs == self.crs
            self.population = self._crop(population.copy(), self.input)
            self.pop_col = pop_col
            self.population = self.population.loc[:, ["geometry", self.pop_col]]
            return True
        else:
            self.population = ""
            return False

    def _load_container(self, container):
        """Loads a geodataframe of polygons to contain points while donut masking"""
        if isinstance(container, GeoDataFrame):
            assert container.crs == self.crs
            self.container = self._crop(container.copy(), self.input)
            self.container = self.container.loc[:, ["geometry"]]
            return True
        else:
            self.container = ""
            return False

    def _load_address(self, address):
        """Loads geodataframe containing address data for k-anonymity calculation"""
        if isinstance(address, GeoDataFrame):
            assert address.crs == self.crs
            self.address = self._crop(address.copy(), self.input)
            self.address = self.address.loc[:, ["geometry"]]
            return True
        else:
            self.address = ""
            return False

    def _crop(self, target, reference):
        """Uses spatial index to reduce an input (target) geodataframe to only
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
        target = target.cx[bb[0] : bb[2], bb[1] : bb[3]]
        return target

    def displacement_distance(self):
        """Calculate dispalcement distance for each point after masking."""
        assert isinstance(self.mask, GeoDataFrame)
        self.mask["_distance"] = self.mask.geometry.distance(self.input["geometry"])
        return self.mask

    def k_anonymity_estimate(self, population="", pop_col="pop"):
        """Estimates k-anoynmity based on population data."""
        if population:
            self._load_population(population, pop_col)

        self.population["_pop_area"] = self.population.area
        self.displacement_distance()
        mask_tmp = self.mask.copy()
        mask_tmp["geometry"] = mask_tmp.apply(lambda x: x.geometry.buffer(x["_distance"]), axis=1)
        mask_tmp = self._disaggregate_population(mask_tmp)
        for i in range(len(self.mask.index)):
            self.mask.at[i, "k_est"] = int(
                round(mask_tmp.loc[mask_tmp["_index_2"] == i, "_pop_adjusted"].sum())
            )
        return self.mask

    def k_anonymity_actual(self, address=""):
        """Calculates k-anonymity based on the number of address closer
        to the mask point than input point"""
        if address:
            self._load_address(address)

        self.displacement_distance()
        mask_tmp = self.mask.copy()
        mask_tmp["geometry"] = mask_tmp.apply(lambda x: x.geometry.buffer(x["_distance"]), axis=1)
        join = sjoin(self.address, mask_tmp, how="left", rsuffix="mask")
        for i in range(len(self.mask)):
            subset = join.loc[join["index_mask"] == i, :]
            self.mask.at[i, "k_actual"] = len(subset)
        return self.mask

    def _disaggregate_population(self, target):
        """Used for estimating k-anonymity. Disaggregates population within
        buffers based on population polygon data"""
        target = target.copy()
        target = sjoin(target, self.population, how="left", rsuffix="pop")
        target["_index_2"] = target.index
        target.index = range(len(target.index))
        target["geometry"] = target.apply(
            lambda x: x["geometry"].intersection(self.population.at[x["index_pop"], "geometry"]),
            axis=1,
        )
        target["_intersected_area"] = target["geometry"].area
        for i in range(len(target.index)):
            polygon_fragments = target.loc[target["_index_2"] == i, :]
            for index, row in polygon_fragments.iterrows():
                area_pct = row["_intersected_area"] / row["_pop_area"]
                target.at[index, "_pop_adjusted"] = row[self.pop_col] * area_pct
        return target

    def _containment(self, target):
        """Checks whether or not mask points are within the same containment
        polygon as their original locations."""
        if "index_cont" not in self.input.columns:
            self.input = sjoin(self.input, self.container, how="left", rsuffix="cont")
            self.try_count = 0
        target = sjoin(target, self.container, how="left", rsuffix="cont")
        for index, row in target.iterrows():
            if row["index_cont"] == self.input.at[index, "index_cont"]:
                self.mask.at[index, "CONTAINED"] = 1
        self.try_count += 1
        if self.try_count > self.max_tries:
            for index, row in target.iterrows():
                self.mask.loc[index, "CONTAINED"] = 0
            print(
                str(len(target)) + " points were mask but could not be "
                "contained. target points are listed as 0 in the 'CONTAINED' field"
            )
        return True
