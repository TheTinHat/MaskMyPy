import inspect
import json
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from time import time
from timeit import default_timer
from typing import Callable

import matplotlib.pyplot as plt
from geopandas import GeoDataFrame
from pandas import DataFrame, Series, concat

from . import analysis, masks, tools


@dataclass
class Atlas:
    """
    A class for quickly performing and evaluating geographic masks.

    Example
    -------
    ```python
    from maskmypy import Atlas, donut, locationswap

    atlas = Atlas(sensitive=some_points, population=some_addresses)
    atlas.mask(donut, low=50, high=500)
    atlas.mask(locationswap, low=50, high=500, address=some_addresses)
    atlas.as_df()
    ```

    Attributes
    ----------
    sensitive : GeoDataFrame
        A GeoDataFrame containing sensitive points.
    population : GeoDataFrame
        A GeoDataFrame containing population information, such as address points or polygon
        with population counts.
    population_column : str
        If the population layer is based on polygons, the name of the column containing population
        counts.
    candidates : list[]
        A list of existing masked candidates, if any.
    """

    sensitive: GeoDataFrame
    population: GeoDataFrame = None
    population_column: str = "pop"
    candidates: list = field(default_factory=list)

    def __post_init__(self):
        self.layers = {}
        if isinstance(self.population, GeoDataFrame):
            tools._validate_crs(self.sensitive.crs, self.population.crs)

    def __getitem__(self, idx):
        return self.candidates[idx]

    def __setitem__(self, idx, val):
        self.candidates[idx] = val

    def __len__(self):
        return len(self.candidates)

    def add_layers(self, *gdf: GeoDataFrame):
        """
        Add GeoDataFrames to the layer store (`Atlas.layers`).

        When regenerating masked GeoDataFrames using `Atlas.gen_gdf()`, any context layers
        that were used in creating the associated candidate must be present in the layer store.
        If they are, they will be automatically found and used as needed.

        Note that layers are stored according to their checksum value (see
        `maskmypy.tools.checksum()`) to provide both deduplication and integrity
        checking.

        Parameters
        ----------
        gdf : GeoDataFrame
            GeoDataFrames to be added to the layer store.
        """
        for x in gdf:
            tools._validate_crs(self.sensitive.crs, x.crs)
            self.layers[tools.checksum(x)] = x

    def mask(
        self,
        mask_func: Callable,
        keep_gdf: bool = False,
        keep_candidate: bool = True,
        skip_slow_evaluators: bool = True,
        measure_execution_time: bool = True,
        measure_peak_memory: bool = False,
        **kwargs,
    ):
        """
        Execute a given mask, analyze the result, and add it to the Atlas.

        Parameters
        ----------
        mask_func : GeoDataFrame
            A masking function to apply to the sensitive point dataset. If using a custom mask,
            it must take the sensitive GeoDataFrame as its first argument, all other arguments as
            keyword arguments, and must return a GeoDataFrame containing the results.
        keep_gdf : bool
            If `False`, the resulting GeoDataFrame will be analyzed and then dropped to save memory.
            Use `gen_gdf` to regenerate the GeoDataFrame.
        keep_candidate : bool
            If `True`, a dictionary containing mask parameters and analysis results are added to
            the candidate list (`Atlas.candidates`, or `Atlas[index]`).
        skip_slow_evaluators : bool
            If `True`, skips any analyses that are known to be slow during mask result
            evaluation. See maskmypy.analysis.evaluate() for more information.
        measure_execution_time : bool
            If `True`, measures the execution time of the mask function and adds it to the
            candidate statistics. Mutually exclusive with `measure_peak_memory`
        measure_peak_memory : bool
            If `True`, will profile memory usage while the mask function is being applied,
            and will add the value in MB to the candidate statistics. Note that the reported
            value represents *additional* memory used by the mask, and does not include existing
            allocations. Mutually exclusive with `measure_peak_memory`.

            Warning: this can significantly slow down execution time.

        """
        if measure_execution_time and measure_peak_memory:
            raise ValueError(
                "`measure_execution_time` and `measure_peak_memory` cannot both be true."
            )

        candidate = {
            "mask": mask_func.__name__,
            "kwargs": self._hydrate_mask_kwargs(**kwargs),
        }

        if "seed" in inspect.getfullargspec(mask_func).args and "seed" not in candidate["kwargs"]:
            candidate["kwargs"]["seed"] = tools.gen_seed()

        if measure_execution_time:
            time_start = default_timer()
        elif measure_peak_memory:
            tracemalloc.start()

        gdf = mask_func(self.sensitive, **candidate["kwargs"])

        if measure_execution_time:
            execution_time = default_timer() - time_start
        elif measure_peak_memory:
            _, mem_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            mem_peak_mb = mem_peak / 1024 / 1024

        candidate["checksum"] = tools.checksum(gdf)
        candidate["kwargs"] = self._dehydrate_mask_kwargs(**candidate["kwargs"])
        candidate["stats"] = analysis.evaluate(
            sensitive_gdf=self.sensitive,
            candidate_gdf=gdf,
            population_gdf=self.population,
            population_column=self.population_column,
            skip_slow=skip_slow_evaluators,
        )

        if "UNMASKED" in gdf.columns:
            candidate["stats"]["UNMASKED_POINTS"] = gdf["UNMASKED"].sum()

        if measure_execution_time:
            candidate["stats"]["execution_time"] = round(execution_time, 3)
        elif measure_peak_memory:
            candidate["stats"]["memory_peak_mb"] = round(mem_peak_mb, 3)

        if keep_gdf:
            self.layers[candidate["checksum"]] = gdf
        else:
            del gdf

        if keep_candidate:
            self.candidates.append(candidate)

        return candidate

    def gen_gdf(
        self,
        idx: int = None,
        checksum: str = None,
        keep: bool = False,
        custom_mask: Callable = None,
    ):
        """
        Regenerates the GeoDataFrame for a given candidate based on either its position in the
        `Atlas.candidates` list or its checksum.

        Parameters
        ----------
        idx : int
            Index of the candidate in `Atlas.candidates` to regenerate a GeoDataFrame for.
        checksum : str
            Checksum of the candidate in `Atlas.candidates` to regenerate a GeoDataFrame for.
        keep : bool
            If `True`, return the masked GeoDataFrame and store it in `Atlas.layers` for future
            use so it does not need to be regenerated.
        custom_mask : Callable
            If the candidate was generated using a custom masking function from outside MaskMyPy,
            provide the function here.

        """
        if (idx is None and checksum is None) or (idx is not None and checksum is not None):
            raise ValueError(f"Must specify either idx or checksum.")

        checksum_before = checksum if checksum else self.candidates[idx]["checksum"]

        # Check if layer is already in the store.
        if isinstance(self.layers.get(checksum_before, None), GeoDataFrame):
            return self.layers[checksum_before]

        try:
            candidate = next(
                cand for cand in self.candidates if cand["checksum"] == checksum_before
            )
        except:
            raise ValueError(f"Could not locate candidate with checksum '{checksum_before}'")

        mask_func = custom_mask or getattr(masks, candidate["mask"])

        candidate_after = self.mask(
            mask_func, keep_candidate=False, keep_gdf=True, **candidate["kwargs"]
        )

        checksum_after = candidate_after.get("checksum")
        if checksum_before != checksum_after:
            raise ValueError(
                f"Checksum of masked GeoDataFrame ({checksum_after}) does not match that which is on record for this candidate ({checksum_before}). Did any input layers get modified?"
            )

        gdf = self.layers[checksum_after]

        if not keep:
            del self.layers[checksum_after]

        return gdf

    def sort(self, by: str, desc: bool = False):
        """
        Sorts the list of candidates (`Atlas.candidates`) based on a given statistic.

        Example:
        ```
        # Sort candidate list in ascending order based on maximum displacement distance.
        atlas.sort(by="displacement_max")

        # Sort candidate list in descending order based on minimum k-anonymity.
        atlas.sort(by="k_min", desc=True)
        ```

        Parameters
        ----------
        by : str
            Name of the statistic to sort by.
        desc : bool
            If `True`, sort in descending order.

        """
        if by in self.candidates[0]["stats"].keys():
            self.candidates.sort(key=lambda x: x["stats"][by], reverse=desc)
        else:
            raise ValueError(f"Could not find '{by}' in candidate statistics.")

    def prune(self, by: str, min: float, max: float):
        """
        Prune candidates based on a given statistic. If the value for that attribute is less than
        `min` or greater than `max` (both inclusive), drop the candidate.

        Example:
        ```
        # Prune any candidates with a minimum displacement distance below 50 and above 500.
        atlas.prune(by="displacement_min", min=50, max=500)

        # Prune any candidates with minimum k-anonymity values below 10 and above 50.
        atlas.prune(by="k_min", min=10, max=50)
        ```

        Parameters
        ----------
        by : str
            Name of the candidate statistic to prune by.
        min : float
            Minimum value of the statistic. If below `min`, the candidate is pruned from the
            candidates list. If the statistic is equal to or greater than `min` but not
            greater than `max` it is kept in the list.
        max : float
            Maximum value of the statistic. If above `max`, the candidate is pruned from the
            candidates list. If the statistic is equal to or less than `max` but not less
            than `min` it is kept in the list.
        """
        if by in self.candidates[0]["stats"].keys():
            self.candidates = [
                c for c in self.candidates if c["stats"][by] >= min and c["stats"][by] <= max
            ]
        else:
            raise ValueError(f"Could not find '{by}' in candidate statistics.")

    def to_json(self, file: Path):
        """
        Saves candidates to a JSON file. As long as the input GeoDataFrames are
        also preserved by the user*, this JSON file can be used to later reconstruct
        the atlas using `Atlas.from_json()`, including all resulting candidate GeoDataFrames.

        * Warning: if Street masking is used, there is a chance that a candidate will not be able
        to be regenerated if OpenStreetMap data changes. This will be addressed in a future version
        of MaskMyPy.

        Parameters
        ----------
        file : Path
            File path indicating where the JSON file should be saved.
        """
        with open(file, "w") as f:
            json.dump(self.candidates, f)

    @classmethod
    def from_json(
        cls,
        sensitive: GeoDataFrame,
        candidate_json: Path,
        population: GeoDataFrame = None,
        population_column: str = "pop",
        layers: list = None,
    ):
        """
        Recreate an Atlas from a candidate JSON file previously generated using `Atlas.to_json()`
        as well as the original GeoDataFrames. Masked GeoDataFrames can then be regenerated using
        `Atlas.gen_gdf()`.

        * Warning: if Street masking is used, there is a chance that a candidate will not be able
        to be regenerated if OpenStreetMap data changes. This will be addressed in a future version
        of MaskMyPy.

        Parameters
        ----------
        sensitive : GeoDataFrame
            The original sensitive point layer.
        candidate_json : Path
            Path to a candidate JSON file previously generated using `Atlas.to_json()`.
        population : GeoDataFrame
            The original population layer, if one was specified.
        population_column : str
            If a polygon-based population layer was used, the name of the population column.
        layers : List[GeoDataFrame]
            A list of additional GeoDataFrames used in the original Atlas. For instance,
            any containers used during donut masking.
        """
        with open(candidate_json) as f:
            candidates = json.load(f)

        atlas = cls(
            sensitive=sensitive,
            candidates=candidates,
            population=population,
            population_column=population_column,
        )
        if layers:
            atlas.add_layers(*layers)
        return atlas

    def as_df(self):
        """
        Return a pandas DataFrame describing each candidate.
        """
        df = DataFrame(data=self.candidates)
        df = concat([df.drop(["kwargs"], axis=1), df["kwargs"].apply(Series)], axis=1)
        df = concat([df.drop(["stats"], axis=1), df["stats"].apply(Series)], axis=1)
        return df

    def scatter(self, a: str, b: str):
        """
        Return a scatter plot of candidates across two given statistics.

        Parameters
        ----------
        a : string
            Name of the candidate statistic to plot.
        b : string
            Name of the candidate statistic to plot.
        """
        df = self.as_df()
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.scatter(df[a], df[b], c="#1f77b4")
        ax.set_xlabel(a)
        ax.set_ylabel(b)
        for i, label in enumerate(df["checksum"]):
            ax.annotate(label, (df.loc[i, a], df.loc[i, b]))
        return fig

    def _hydrate_mask_kwargs(self, **mask_kwargs: dict) -> dict:
        """
        Find any keyword arguments that contain context layer checksums and
        attempt to restore the layer from `Atlas.layers`.
        """
        for key, value in mask_kwargs.items():
            if isinstance(value, str) and value.startswith("context_"):
                checksum = value.split("_")[1]
                try:
                    mask_kwargs[key] = self.layers[checksum]
                except KeyError as e:
                    raise KeyError(
                        f"Error: cannot find context layer for '{key}, {checksum}', \
                        try loading it first using Atlas.add_layers(). {e}"
                    )
        return mask_kwargs

    def _dehydrate_mask_kwargs(self, **mask_kwargs: dict) -> dict:
        """
        Search mask kwargs for any GeoDataFrames and replace them with their checksums.
        """
        for key, value in mask_kwargs.items():
            if isinstance(value, GeoDataFrame):
                self.add_layers(value)
                mask_kwargs[key] = "_".join(["context", tools.checksum(value)])
        return mask_kwargs
