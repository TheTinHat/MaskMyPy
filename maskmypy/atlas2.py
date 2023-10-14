from dataclasses import dataclass, field
from pathlib import Path
from time import time_ns

from geopandas import GeoDataFrame

from . import tools


@dataclass
class Atlas2:
    sensitive: GeoDataFrame
    candidates: list = field(default_factory=list)
    contexts: dict = field(default_factory=dict)

    def add_contexts(self, *args: GeoDataFrame):
        for arg in args:
            self.contexts[checksum(arg)] = arg

    def __getitem__(self, idx):
        return self.candidates[idx]

    def __setitem__(self, idx, val):
        self.candidates[idx] = val

    def __len__(self):
        return len(self.candidates)

    def sort(self, by):
        return sorted(self.candidates, key=by)

    def mkgdf(self, idx, persist=False):
        gdf = self.mask(self.sensitive, self.candidates[idx]["kwargs"])
        if persist:
            self.candidates[idx]["gdf"]

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

    def prune(self, by, min=None, max=None):
        """
        Prune candidates based on a given attribute (e.g. `k_min`).
        If the value for that attribute is below `min` or above `max`,
        drop the candidate.
        """
        self.candidates = [
            c for c in self.candidates if getattr(c, by) >= min and getattr(c, by) <= max
        ]

    def to_json(self, file: Path = None):
        pass

    def from_json(self, json, gdf=None):
        pass

    def mask(self, mask, **kwargs):
        candidate = {"mask": mask.__name__, "kwargs": kwargs, "timestamp_ns": time_ns()}
        if "seed" not in candidate["kwargs"]:
            candidate["kwargs"]["seed"] = genseed()

        candidate["gdf"] = mask(self.sensitive, seed=candidate["args"]["seed"], **kwargs)
        candidate = analyze(candidate["gdf"], self.sensitive)
        del candidate["gdf"]
        self.candidates.append(candidate)
        return candidate


def analyze(candidate_gdf, sensitive_gdf) -> dict:
    pass

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
