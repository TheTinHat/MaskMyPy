from geopandas import GeoDataFrame, sjoin


class Base:
    """Base class for masking methods"""

    def __init__(
        self,
        sensitive_gdf,
        population_gdf="",
        population_column="pop",
        container_gdf="",
        max_tries=1000,
        address_points_gdf="",
    ):
        self.sensitive = sensitive_gdf.copy()
        self.crs = self.sensitive.crs
        self._load_population(population_gdf, population_column)
        self._load_container(container_gdf)
        self._load_addresses(address_points_gdf)
        self.max_tries = max_tries

    def _load_population(self, population_gdf="", population_column="pop"):
        """Loads a geodataframe of population data for donut masking and/or k-anonymity estimation."""
        if isinstance(population_gdf, GeoDataFrame):
            assert (
                population_gdf.crs == self.crs
            ), "Population CRS does not match points CRS"
            self.population = self._crop_gdf(population_gdf, self.sensitive)
            self.pop_column = population_column
            self.population = self.population.loc[:, ["geometry", self.pop_column]]
            return True
        else:
            self.population = ""
            return False

    def _load_container(self, container_gdf):
        """Loads a geodataframe of polygons to contain points while donut masking"""
        if isinstance(container_gdf, GeoDataFrame):
            assert (
                container_gdf.crs == self.crs
            ), "Container CRS does not match points CRS"
            self.container = self._crop_gdf(container_gdf, self.sensitive)
            self.container = self.container.loc[:, ["geometry"]]
            return True
        else:
            self.container = ""
            return False

    def _load_addresses(self, address_points_gdf):
        """Loads geodataframe containing address data for k-anonymity calculation"""
        if isinstance(address_points_gdf, GeoDataFrame):
            assert (
                address_points_gdf.crs == self.crs
            ), "Address points CRS does not match points CRS"
            self.addresses = self._crop_gdf(address_points_gdf, self.sensitive)
            self.addresses = self.addresses.loc[:, ["geometry"]]
            return True
        else:
            self.addresses = ""
            return False

    def _crop_gdf(self, target_gdf, reference_gdf):
        """Uses spatial index to reduce an input (target) geodataframe to only
        that which intersects with a reference geodataframe"""
        bb = reference_gdf.total_bounds
        x = (bb[2] - bb[0]) / 5
        y = (bb[3] - bb[1]) / 5
        bb[0] = bb[0] - x
        bb[1] = bb[1] - y
        bb[2] = bb[2] + x
        bb[3] = bb[3] + y
        target_gdf = target_gdf.cx[bb[0] : bb[2], bb[1] : bb[3]]
        return target_gdf

    def displacement_distance(self):
        """Calculate dispalcement distance for each point after masking."""
        assert isinstance(self.masked, GeoDataFrame), "Data has not yet been masked"
        self.masked["distance"] = self.masked.geometry.distance(
            self.sensitive["geometry"]
        )
        return self.masked

    def k_anonymity_estimate(self, population_gdf="", population_column="pop"):
        """Estimates k-anoynmity based on population data."""
        if not isinstance(self.population, GeoDataFrame):
            self._load_population(population_gdf, population_column)

        assert isinstance(
            self.sensitive, GeoDataFrame
        ), "Sensitive points geodataframe is missing"
        assert isinstance(self.masked, GeoDataFrame), "Data has not yet been masked"
        assert isinstance(
            self.population, GeoDataFrame
        ), "Population geodataframe is missing"

        self.population["pop_area"] = self.population.area

        if "distance" not in self.masked.columns:
            self.displacement_distance()

        masked_temp = self.masked.copy()

        masked_temp["geometry"] = masked_temp.apply(
            lambda x: x.geometry.buffer(x["distance"]), axis=1
        )

        masked_temp = self._disaggregate_population(masked_temp)

        for i in range(len(self.masked.index)):
            self.masked.at[i, "k_est"] = int(
                masked_temp.loc[masked_temp["index_2"] == i, "pop_adjusted"].sum() - 1
            )

        return self.masked

    def k_anonymity_actual(self, address_points_gdf=""):
        """Calculates k-anonymity based on the number of addresses closer
        to the masked point than sensitive point"""
        if not isinstance(self.addresses, GeoDataFrame):
            self._load_addresses(address_points_gdf)

        assert isinstance(
            self.sensitive, GeoDataFrame
        ), "Sensitive points geodataframe is missing"
        assert isinstance(self.masked, GeoDataFrame), "Data has not yet been masked"
        assert isinstance(
            self.addresses, GeoDataFrame
        ), "Address points geodataframe is missing"

        if isinstance(self.addresses, GeoDataFrame) is False:
            raise Exception("Error: missing address point geodataframe.")

        if "distance" not in self.masked.columns:
            self.displacement_distance()

        masked_temp = self.masked.copy()

        masked_temp["geometry"] = masked_temp.apply(
            lambda x: x.geometry.buffer(x["distance"]), axis=1
        )

        join = sjoin(self.addresses, masked_temp, how="left")

        for i in range(len(self.masked)):
            subset = join.loc[join["index_right"] == i, :]
            self.masked.at[i, "k_actual"] = len(subset)

        return self.masked

    def _disaggregate_population(self, target_gdf):
        """Used for estimating k-anonymity. Disaggregates population within
        buffers based on population polygon data"""
        target = target_gdf.copy()
        target = sjoin(target, self.population, how="left")

        target["index_2"] = target.index

        target.index = range(len(target.index))

        target["geometry"] = target.apply(
            lambda x: x["geometry"].intersection(
                self.population.at[x["index_right"], "geometry"]
            ),
            axis=1,
        )

        target["intersected_area"] = target["geometry"].area

        for i in range(len(target_gdf.index)):

            polygon_fragments = target.loc[target["index_2"] == i, :]

            for index, row in polygon_fragments.iterrows():
                area_pct = row["intersected_area"] / row["pop_area"]
                target.at[index, "pop_adjusted"] = row[self.pop_column] * area_pct

        return target

    def _containment(self, uncontained):
        """If a container geodataframe is loaded, checks whether or not masked
        points are within the same containment polygon as their original locations."""

        if "index_right" not in self.sensitive.columns:
            self.sensitive = sjoin(self.sensitive, self.container, how="left")
            self.tries = 0

        uncontained = sjoin(uncontained, self.container, how="left")

        for index, row in uncontained.iterrows():
            if row["index_right"] == self.sensitive.at[index, "index_right"]:
                self.masked.at[index, "contain"] = 1

        self.tries += 1

        if self.tries > self.max_tries:

            for index, row in uncontained.iterrows():
                self.masked.loc[index, "contain"] = 999

            print(
                str(len(uncontained)) + " points were masked but could not be"
                "contained. Uncontained points are listed as 999 in the 'contain' field"
            )

        return True
