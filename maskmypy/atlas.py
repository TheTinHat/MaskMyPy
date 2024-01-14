import json
from dataclasses import dataclass, field
from pathlib import Path
from time import time
from typing import Callable

from geopandas import GeoDataFrame
from pandas import DataFrame, Series, concat

from . import analysis, masks, tools


@dataclass
class Atlas:
    sensitive: GeoDataFrame
    candidates: list = field(default_factory=list)
    population: GeoDataFrame = None
    population_column: str = "pop"

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
        [TODO:summary]
        Add GeoDataFrames to the layer store.

        [TODO:description]


        Parameters
        ----------
        gdf
            [TODO:description]
        """
        for x in gdf:
            self.layers[tools.checksum(x)] = x

    def mask(
        self,
        mask_func: Callable,
        keep_gdf: bool = False,
        keep_candidate: bool = True,
        skip_slow_evaluators: bool = True,
        **kwargs,
    ):
        """
        Execute a given mask, analyze the result, and add it to the Atlas.

        NEED MORE DESCRIPTION HERE.

        Parameters
        ----------
        mask_func : GeoDataFrame
            A masking function to apply to the sensitive point dataset. If using a custom mask,
            it must take the sensitive GeoDataFrame as its first argument, all other arguments as
            keyword arguments, and must return a GeoDataFrame containing the results.
        keep_gdf : bool
            If `False`, the resulting GeoDataFrame will be analyzed and then dropped to save memory.
            Use `gen_gdf` to regenerate the GeoDataFrame. Default: `False`.
        keep_candidate : bool
            If `True`, a dictionary containing mask parameters and analysis results are added to
            the candidate list (`Atlas.candidates`, or `Atlas[index]`). Default: `True`.
        skip_slow_evaluators : bool
            If `True`, skips any analyses that are known to be slow during mask result
            evaluation. See maskmypy.analysis.evaluate() for more information. Default: `True`.
        """
        candidate = {
            "mask": mask_func.__name__,
            "kwargs": self._hydrate_mask_kwargs(**kwargs),
            "timestamp": time(),
        }
        candidate["kwargs"]["seed"] = candidate["kwargs"].get("seed") or tools.gen_seed()

        gdf = mask_func(self.sensitive, **candidate["kwargs"])

        candidate["checksum"] = tools.checksum(gdf)
        candidate["kwargs"] = self._dehydrate_mask_kwargs(**candidate["kwargs"])
        candidate["stats"] = analysis.evaluate(
            sensitive_gdf=self.sensitive,
            candidate_gdf=gdf,
            population_gdf=self.population,
            population_column=self.population_column,
            skip_slow=skip_slow_evaluators,
        )

        if keep_gdf:
            self.layers[candidate["checksum"]] = gdf
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
            Index of the candidate in `Atlas.candidates` to regenerate a GeoDataFrame for. Default: `None`.
        checksum : str
            Checksum of the candidate in `Atlas.candidates` to regenerate a GeoDataFrame for. Default: `None`.
        keep : bool
            If `True`, return the masked GeoDataFrame and cache it in `Atlas.layers` for future
            use so it does not need to be regenerated. Default: `False`.
        custom_mask : Callable
            If the candidate was generated using a custom masking function from outside MaskMyPy,
            provide the function here. Default: `None`.

        """
        if (idx is None and checksum is None) or (idx is not None and checksum is not None):
            raise ValueError(f"Must specify either idx or checksum.")

        checksum_before = checksum if checksum else self.candidates[idx]["checksum"]

        # Check if layer is already in the cache.
        if isinstance(self.layers.get(checksum_before, None), GeoDataFrame):
            return self.layers[checksum_before]

        try:
            candidate = next(cand for cand in self.candidates if cand["checksum"] == checksum_before)
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

    def sort(self, by: str):
        """
        [TODO:summary]

        [TODO:description]

        Parameters
        ----------
        by
            [TODO:description]

        Raises
        ------
        ValueError:
            [TODO:description]
        """
        if by in self.candidates[0].keys():
            self.candidates.sort(key=lambda x: x[by])
        elif by in self.candidates[0]["stats"].keys():
            self.candidates.sort(key=lambda x: x["stats"][by])
        elif by in self.candidates[0]["kwargs"].keys():
            self.candidates.sort(key=lambda x: x["kwargs"][by])
        else:
            raise ValueError(f"Could not find {by} in candidate.")

    def prune(self, by: str, min: float, max: float):
        """
        [TODO:summary]

        Prune candidates based on a given attribute (e.g. `k_min`).
        If the value for that attribute is less than `min` or greater than `max`,
        drop the candidate.

        [TODO:description]

        Parameters
        ----------
        by
            [TODO:description]
        min
            [TODO:description]
        max
            [TODO:description]

        Raises
        ------
        ValueError:
            [TODO:description]
        """
        if by in self.candidates[0].keys():
            self.candidates = [c for c in self.candidates if c[by] >= min and c[by] <= max]
        elif by in self.candidates[0]["stats"].keys():
            self.candidates = [
                c for c in self.candidates if c["stats"][by] >= min and c["stats"][by] <= max
            ]
        elif by in self.candidates[0]["kwargs"].keys():
            self.candidates = [
                c for c in self.candidates if c["kwargs"][by] >= min and c["kwargs"][by] <= max
            ]
        else:
            raise ValueError(f"Could not find {by}.")

    def to_json(self, file: Path):
        """
        [TODO:summary]

        Saves candidates to a JSON file. As long as the input GeoDataFrames are
        also preserved by the user, this JSON file can be used to later reconstruct
        the atlas, including all resulting candidate GeoDataFrames.

        [TODO:description]

        Parameters
        ----------
        file
            [TODO:description]
        """
        with open(file, "w") as f:
            json.dump(self.candidates, f)

    @classmethod
    def from_json(
        cls, sensitive, candidate_json, population: GeoDataFrame = None, layers: list = None
    ):
        """
        [TODO:summary]

        [TODO:description]

        Parameters
        ----------
        cls : [TODO:type]
            [TODO:description]
        sensitive : [TODO:type]
            [TODO:description]
        candidate_json : [TODO:type]
            [TODO:description]
        population
            [TODO:description]
        layers
            [TODO:description]
        """
        with open("/tmp/tmp_test.json") as f:
            candidates = json.load(f)

        atlas = cls(sensitive, candidates, population)
        if layers:
            atlas.add_layers(*layers)
        return atlas

    def as_df(self):
        """
        [TODO:summary]

        [TODO:description]
        """
        df = DataFrame(data=self.candidates)
        df = concat([df.drop(["kwargs"], axis=1), df["kwargs"].apply(Series)], axis=1)
        df = concat([df.drop(["stats"], axis=1), df["stats"].apply(Series)], axis=1)
        return df

    def _hydrate_mask_kwargs(self, **mask_kwargs: dict) -> dict:
        """
        Find any keyword arguments that contain context layer checksums and
        attempt to restore the layer from Atlas..
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
        for key, value in mask_kwargs.items():
            if isinstance(value, GeoDataFrame):
                mask_kwargs[key] = "_".join(["context", tools.checksum(value)])
        return mask_kwargs
