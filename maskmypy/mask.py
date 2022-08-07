from geopandas import GeoDataFrame, sjoin


class Base:
    """Base class for masking methods"""

    def __init__(
        self,
        sensitive,
        population="",
        population_column="pop",
        container="",
        max_tries=1000,
        addresses="",
    ):
        self.sensitive = sensitive.copy()
        self.crs = self.sensitive.crs
        self._load_population(population, population_column)
        self._load_container(container)
        self._load_addresses(addresses)
        self.max_tries = max_tries

    def _load_population(self, population="", population_column="pop"):
        """Loads a geodataframe of population data for donut masking and/or k-anonymity estimation."""
        if isinstance(population, GeoDataFrame):
            assert population.crs == self.crs, "Population CRS does not match points CRS"
            self.population = self._crop(population, self.sensitive)
            self.pop_column = population_column
            self.population = self.population.loc[:, ["geometry", self.pop_column]]
            return True
        else:
            self.population = ""
            return False

    def _load_container(self, container):
        """Loads a geodataframe of polygons to contain points while donut masking"""
        if isinstance(container, GeoDataFrame):
            assert container.crs == self.crs, "Container CRS does not match points CRS"
            self.container = self._crop(container, self.sensitive)
            self.container = self.container.loc[:, ["geometry"]]
            return True
        else:
            self.container = ""
            return False

    def _load_addresses(self, addresses):
        """Loads geodataframe containing address data for k-anonymity calculation"""
        if isinstance(addresses, GeoDataFrame):
            assert addresses.crs == self.crs, "Address points CRS does not match points CRS"
            self.addresses = self._crop(addresses, self.sensitive)
            self.addresses = self.addresses.loc[:, ["geometry"]]
            return True
        else:
            self.addresses = ""
            return False

    def _crop(self, target, reference):
        """Uses spatial index to reduce an input (target) geodataframe to only
        that which intersects with a reference geodataframe"""
        bb = reference.total_bounds
        if len(set(bb)) == 2:  # If reference is single point, skip crop
            return target
        x = (bb[2] - bb[0]) / 5
        y = (bb[3] - bb[1]) / 5
        bb[0] = bb[0] - x
        bb[1] = bb[1] - y
        bb[2] = bb[2] + x
        bb[3] = bb[3] + y
        target = target.cx[bb[0] : bb[2], bb[1] : bb[3]]
        return target

    def displacement_distance(self):
        """Calculate dispalcement distance for each point after masking."""
        assert isinstance(self.masked, GeoDataFrame), "Data has not yet been masked"
        self.masked["_displace_dist"] = self.masked.geometry.distance(self.sensitive["geometry"])
        return self.masked

    def k_anonymity_estimate(self, population="", population_column="pop"):
        """Estimates k-anoynmity based on population data."""
        if not isinstance(self.population, GeoDataFrame):
            self._load_population(population, population_column)
        assert isinstance(self.sensitive, GeoDataFrame), "Sensitive points geodataframe is missing"
        assert isinstance(self.masked, GeoDataFrame), "Data has not yet been masked"
        assert isinstance(self.population, GeoDataFrame), "Population geodataframe is missing"
        self.population["_pop_area"] = self.population.area
        if "_displace_dist" not in self.masked.columns:
            self.displacement_distance()
        masked_temp = self.masked.copy()
        masked_temp["geometry"] = masked_temp.apply(
            lambda x: x.geometry.buffer(x["_displace_dist"]), axis=1
        )
        masked_temp = self._disaggregate_population(masked_temp)
        for i in range(len(self.masked.index)):
            self.masked.at[i, "k_est"] = int(
                round(masked_temp.loc[masked_temp["_index_2"] == i, "_pop_adjusted"].sum())
            )
        return self.masked

    def k_anonymity_actual(self, addresses=""):
        """Calculates k-anonymity based on the number of addresses closer
        to the masked point than sensitive point"""
        if not isinstance(self.addresses, GeoDataFrame):
            self._load_addresses(addresses)
        assert isinstance(self.sensitive, GeoDataFrame), "Sensitive points geodataframe is missing"
        assert isinstance(self.masked, GeoDataFrame), "Data has not yet been masked"
        assert isinstance(self.addresses, GeoDataFrame), "Address points geodataframe is missing"
        if isinstance(self.addresses, GeoDataFrame) is False:
            raise Exception("Error: missing address point geodataframe.")
        if "_displace_dist" not in self.masked.columns:
            self.displacement_distance()
        masked_temp = self.masked.copy()
        masked_temp["geometry"] = masked_temp.apply(
            lambda x: x.geometry.buffer(x["_displace_dist"]), axis=1
        )
        join = sjoin(self.addresses, masked_temp, how="left", rsuffix="right")
        for i in range(len(self.masked)):
            subset = join.loc[join["index_right"] == i, :]
            self.masked.at[i, "k_actual"] = len(subset)
        return self.masked

    def _disaggregate_population(self, target):
        """Used for estimating k-anonymity. Disaggregates population within
        buffers based on population polygon data"""
        target = target.copy()
        target = sjoin(target, self.population, how="left", rsuffix="right")
        target["_index_2"] = target.index
        target.index = range(len(target.index))
        target["geometry"] = target.apply(
            lambda x: x["geometry"].intersection(self.population.at[x["index_right"], "geometry"]),
            axis=1,
        )
        target["_intersected_area"] = target["geometry"].area
        for i in range(len(target.index)):
            polygon_fragments = target.loc[target["_index_2"] == i, :]
            for index, row in polygon_fragments.iterrows():
                area_pct = row["_intersected_area"] / row["_pop_area"]
                target.at[index, "_pop_adjusted"] = row[self.pop_column] * area_pct
        return target

    def _containment(self, uncontained):
        """If a container geodataframe is loaded, checks whether or not masked
        points are within the same containment polygon as their original locations."""
        if "index_right" not in self.sensitive.columns:
            self.sensitive = sjoin(self.sensitive, self.container, how="left", rsuffix="right")
            self.tries = 0
        uncontained = sjoin(uncontained, self.container, how="left")
        for index, row in uncontained.iterrows():
            if row["index_right"] == self.sensitive.at[index, "index_right"]:
                self.masked.at[index, "CONTAINED"] = 1
        self.tries += 1
        if self.tries > self.max_tries:
            for index, row in uncontained.iterrows():
                self.masked.loc[index, "CONTAINED"] = 0
            print(
                str(len(uncontained)) + " points were masked but could not be"
                "contained. Uncontained points are listed as 0 in the 'CONTAINED' field"
            )
        return True
