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

    def __getitem__(self, idx):
        return self.candidates[idx]

    def __setitem__(self, idx, val):
        self.candidates[idx] = val

    def __len__(self):
        return len(self.candidates)

    def add_layers(self, *gdf: GeoDataFrame):
        """
        Add GeoDataFrames to the layer store.
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

    def gen_gdf(self, idx, keep=False, custom_mask: Callable = None):
        """
        Regenerates the GeoDataFrame for a given candidate.
        If the candidate was originally generated using a custom masking function,
        specify it using the `custom_mask` parameter.
        """
        checksum_before = self.candidates[idx]["checksum"]
        if self.layers.get(checksum_before):
            return self.layers[checksum_before]

        mask_func = custom_mask or getattr(masks, self.candidates[idx]["mask"])

        candidate = self.mask(
            mask_func, keep_candidate=False, keep_gdf=True, **self.candidates[idx]["kwargs"]
        )
        checksum_after = candidate.get("checksum")

        if checksum_before != checksum_after:
            raise ValueError(
                f"Checksum of masked GeoDataFrame ({checksum_after}) does not match that which is on record for this candidate ({checksum_before}). Did any input layers get modified?"
            )

        gdf = self.layers[checksum_after]

        if not keep:
            del self.layers[checksum_after]

        return gdf

    def sort(self, by: str):
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
        Prune candidates based on a given attribute (e.g. `k_min`).
        If the value for that attribute is less than `min` or greater than `max`,
        drop the candidate.
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
        Saves candidates to a JSON file. As long as the input GeoDataFrames are
        also preserved by the user, this JSON file can be used to later reconstruct
        the atlas, including all resulting candidate GeoDataFrames.
        """
        with open(file, "w") as f:
            json.dump(self.candidates, f)

    @classmethod
    def from_json(
        cls, sensitive, candidate_json, population: GeoDataFrame = None, layers: list = None
    ):
        with open("/tmp/tmp_test.json") as f:
            candidates = json.load(f)

        atlas = cls(sensitive, candidates, population)
        if layers:
            atlas.add_layers(*layers)
        return atlas

    def as_df(self):
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
