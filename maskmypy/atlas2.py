import json
from dataclasses import dataclass, field
from pathlib import Path
from time import time_ns
from typing import Callable

from geopandas import GeoDataFrame
from pandas import DataFrame, Series, concat

from . import masks, tools


@dataclass
class Atlas2:
    sensitive: GeoDataFrame
    candidates: list = field(default_factory=list)
    # This should be in the post init
    contexts: dict = field(default_factory=dict)
    context_layer_keys = ["addresses", "container", "census"]

    def __getitem__(self, idx):
        return self.candidates[idx]

    def __setitem__(self, idx, val):
        self.candidates[idx] = val

    def __len__(self):
        return len(self.candidates)

    def sort(self, by):
        return sorted(self.candidates, key=by)

    def drop_gdfs(self):
        """
        Drop GeoDataFrames from all candidates. Use this
        to save memory. To regenerate a dropped GeoDataFrame,
        use 'Atlas.gen_gdf()'.
        """
        for candidate in self.candidates:
            candidate.pop("gdf", None)

    def gen_gdf(self, idx, persist=False):
        """
        Regenerates the GeoDataFrame for a given candidate.
        """
        checksum_before = self.candidates[idx]["checksum"]

        mask_func = getattr(masks, self.candidates[idx]["mask"])

        candidate = self.mask(
            mask_func, append=False, drop_gdf=False, **self.candidates[idx]["kwargs"]
        )
        gdf = candidate["gdf"]
        checksum_after = candidate.pop("checksum")

        assert checksum_before == checksum_after

        self.candidates[idx] = candidate

        if not persist:
            del candidate["gdf"]

        return gdf

    def to_shp(self, idx=None, hash=None, filename=None):
        """
        Create a shapefile named `filename`.shp for a given candidate based on it's
        index (`idx`) or hash (`hash`). If no filename is provided, the shapefile
        is named `hash`.shp.
        """
        if not filename:
            if idx:
                hash = tools._checksum(self.candidates[idx])
            elif hash:
                filename = f"{hash}.shp"
        self.to_gdf(idx).to_file(filename)

    def add_contexts(self, *gdf: GeoDataFrame):
        for x in gdf:
            self.contexts[tools._checksum(x)] = x

    def prune(self, by, min=None, max=None):
        """
        Prune candidates based on a given attribute (e.g. `k_min`).
        If the value for that attribute is below `min` or above `max`,
        drop the candidate.
        """
        self.candidates = [c for c in self.candidates if c[by] >= min and c[by] <= max]

    def save_candidates(self, file: Path = None):
        gdfs = []
        for candidate in self.candidates:
            gdfs.append(candidate.pop("gdf", None))

        with open(file, "w") as f:
            json.dump(self.candidates, f)

        for i in range(len(gdfs)):
            if gdfs[i] is not None:
                self.candidates[i]["gdf"] = gdfs[i]

    def _hydrate_mask_kwargs(self, **mask_kwargs: dict) -> dict:
        """
        Find any keyword arguments that contain context layer checksums and
        attempt to restore the layer from Atlas.contexts.
        """
        for key, value in mask_kwargs.items():
            if isinstance(value, str) and value.startswith("context_"):
                checksum = value.split("_")[1]
                try:
                    mask_kwargs[key] = self.contexts[checksum]
                except KeyError as e:
                    raise KeyError(
                        f"Error: cannot find context layer for '{key}, {value}', \
                        try loading it first using Atlas.add_contexts(). {e}"
                    )
        return mask_kwargs

    def _dehydrate_mask_kwargs(self, **mask_kwargs: dict) -> dict:
        for key, value in mask_kwargs.items():
            if isinstance(value, GeoDataFrame):
                mask_kwargs[key] = "_".join(["context", tools._checksum(value)])
        return mask_kwargs

    def mask(self, mask_func: Callable, drop_gdf: bool = True, append: bool = True, **kwargs):
        candidate = {
            "mask": mask_func.__name__,
            "kwargs": self._hydrate_mask_kwargs(**kwargs),
            "timestamp_ns": time_ns(),
        }
        candidate["kwargs"]["seed"] = candidate["kwargs"].get("seed") or tools.gen_seed()

        candidate["gdf"] = mask_func(self.sensitive, **candidate["kwargs"])

        checksum_before = kwargs.get("checksum", None)
        checksum_after = tools._checksum(candidate["gdf"])
        if checksum_before and checksum_before != checksum_after:
            raise ValueError(
                f"Checksum of masked GeoDataFrame ({checksum_after}) does not match that which is on record \
                for this candidate ({checksum_before}). Did any input layers get modified?"
            )
        else:
            candidate["checksum"] = checksum_after

        # Analyze results
        candidate["stats"] = analyze(candidate["gdf"], self.sensitive)

        candidate["kwargs"] = self._dehydrate_mask_kwargs(**candidate["kwargs"])

        if drop_gdf:
            del candidate["gdf"]
        if append:
            self.candidates.append(candidate)
        return candidate

    def as_df(self):
        df = DataFrame(data=self.candidates)
        df.drop(columns="gdf", errors="ignore", axis=1)
        df = concat([df.drop(["kwargs"], axis=1), df["kwargs"].apply(Series)], axis=1)
        df = concat([df.drop(["stats"], axis=1), df["stats"].apply(Series)], axis=1)
        return df


def analyze(candidate_gdf, sensitive_gdf) -> dict:
    return {"test": "Hello"}
    # if idx is None and candidate is None:
    #     for candidate in self.candidates:
    #         candidate = self.analyze_privacy(candidate)
    #         candidate = self.analyze_loss(candidate)
    #
    # elif idx is not None and candidate is None:
    #     self.candidates[idx] = self.analyze_privacy(self.candidates[idx])
    #     self.candidates[idx] = self.analyze_loss(self.candidates[idx])
    #
    # elif idx is None and candidate is not None:
    #     candidate = self.analyze_privacy(candidate)
    #     candidate = self.analyze_loss(candidate)
    #     return candidate
    #
    # elif idx is not None and candidate is not None:
    #     raise Error

    def as_df(columns=None):
        pass
