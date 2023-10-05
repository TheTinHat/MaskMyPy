# atlas = Atlas(sensitive)
#
# atlas.donut()
# altas.street()
# atlas.analyze(save_graphs=true)
#
# # The 'ranking' is just a list of results. Provide functions to sort this list.
# atlas.prune(by="k_est", min="5")
# atlas.sort_by("ddist")
#
# atlas[0]
# test_1 = atlas.to_gdf(0)
# atlas.to_json(file="./results.json")
# del atlas
#
# atlas = Atlas.from_json(file="./results.json", gdf=sensitive)
#
# test_2 = atlas.to_gdf(0)
#
# assert test_1 == test_2
from dataclasses import dataclass, field
from pathlib import Path
from time import time_ns

from geopandas import GeoDataFrame


@dataclass
class Atlas2:
    sensitive: GeoDataFrame
    candidates: list = field(default_factory=list)

    def __getitem__(self, idx):
        return self.candidates[idx]

    def __setitem__(self, idx, val):
        self.candidates[idx] = val

    def __len__(self):
        return len(self.candidates)

    def sort(by):
        return sorted(self.candidates, key=by)

    def mkgdf(idx, persist=False):
        gdf = self.mask(self.sensitive, self.candidates[idx]["kwargs"])
        if persist:
            self.candidates[idx]["gdf"]

        return gdf

    def to_shp(idx, filename):
        self.to_gdf(idx).to_file(filename)

    def prune(by, min=None, max=None):
        self.candidates = [
            c for c in self.candidates if getattr(c, by) >= min and getattr(c, by) <= max
        ]

    def to_json(file: Path = None):
        pass

    def from_json(json, gdf=None):
        pass

    def mask(mask, **kwargs):
        candidate = {"mask": str(mask), "kwargs": kwargs, "timestamp_ns": time_ns()}
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
