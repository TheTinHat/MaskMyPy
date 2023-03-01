import json
from collections import deque
from dataclasses import asdict, dataclass, field
from functools import cached_property
from itertools import zip_longest
from pathlib import Path

import geopandas as gpd

from . import tools
from .candidate import Candidate
from .masks.donut import Donut
from .masks.street import Street
from .messages import *
from .storage import Storage


@dataclass
class Atlas:
    name: str
    sensitive: gpd.GeoDataFrame
    candidates: deque = field(default=None)
    directory: Path = field(default_factory=lambda: Path.cwd())
    autosave: bool = False
    autoflush: bool = False
    keep_last: int = 50

    def __post_init__(self):
        if not self.candidates:
            self.candidates = deque(maxlen=self.keep_last)

        self.storage = Storage(directory=Path(self.directory), name=self.name)

        if isinstance(self.directory, str):
            self.directory = Path(self.directory)

    def save(self):
        self.storage.save_atlas(self)

    def load_candidate(self, cid):
        meta = self.storage.get_candidate_meta(cid)
        mdf = self.storage.get_candidate_mdf(cid)

        return Candidate(
            sid=meta.sid,
            mdf=mdf,
            storage=self,
            parameters=meta.parameters,
            author=meta.author,
            timestamp=meta.timestamp,
        )

    @cached_property
    def sid(self):
        return tools.checksum(self.sensitive)

    @classmethod
    def load(cls, name, directory=Path.cwd()):
        storage = Storage(name=name, directory=directory)

        atlas_meta = storage.get_atlas_meta(name=name)
        sensitive = storage.get_sensitive_gdf(name=name)

        candidates_db = storage.list_candidates(atlas_meta.sid)

        candidates = deque(maxlen=atlas_meta.keep_last)
        for candidate in candidates_db:
            candidate_mdf = storage.get_candidate_mdf(candidate.cid)
            candidates.append(
                Candidate(
                    atlas_meta.sid,
                    mdf=candidate_mdf,
                    storage=storage,
                    parameters=candidate.parameters,
                    author=candidate.author,
                    timestamp=candidate.timestamp,
                )
            )

        return cls(
            name=name,
            sensitive=sensitive,
            candidates=candidates,
            directory=directory,
            autosave=atlas_meta.autosave,
            autoflush=atlas_meta.autoflush,
            keep_last=atlas_meta.keep_last,
        )

    @property
    def crs(self):
        return self.sensitive.crs

    @property
    def metadata(self):
        return asdict(self, dict_factory=self.dict_factory)

    def set(self, candidate):
        # assert candidate.mdf.crs == self.crs, candidate_crs_mismatch_msg
        # assert candidate.checksum != self.checksum, candidate_identical_to_sensitive_msg
        self.candidates.append(candidate)

    def get(self, index=-1):
        candidate = self.candidates[index]

        if candidate.mdf is None:
            try:
                candidate.mdf = gpd.read_file(self.gpkg, layer=candidate.cid, driver="GPKG")
            except Exception as err:
                print(f"Unable to load candidate dataframe: {err}")
        elif not isinstance(candidate.mdf, gpd.GeoDataFrame):
            raise Exception("Candidate dataframe is an unknown data type.")

        return candidate

    def delete(self, index):
        pass

    # def save_candidate(self, index=None, flush=None):
    #     candidate = self.candidates[index]
    #     if isinstance(candidate.mdf, gpd.GeoDataFrame):
    #         candidate.mdf.to_file(self.gpkg, layer=candidate.cid, driver="GPKG")
    #         if flush or self.autoflush:
    #             candidate.mdf = None
    #     return True

    def save_atlas(self):
        candidate_parameters = {cand.cid: cand.parameters for cand in self.candidates}
        archive = {"metadata": self.metadata, "candidates": candidate_parameters}

        with open(self.archive_path, "w") as file:
            file.write(json.dumps(archive))

        self.sensitive.to_file(self.gpkg, layer="sensitive", driver="GPKG")
        for index in range(len(self.candidates)):
            self.save_candidate(index)

        return True

    @classmethod
    def open_atlas(cls, directory, name=None):
        directory = Path(directory)

        # Detect atlas name
        if not name:
            atlases = [archive for archive in directory.glob("*.atlas.json")]
            if len(atlases) > 1:
                raise Exception(multiple_atlases_detected_msg)
            name = atlases[0].with_suffix("").with_suffix("").stem

        # Read Archive
        archive_path = directory / Path(f"{name}.atlas.json")
        with open(archive_path, "r") as file:
            archive = json.load(file)

        # Read geopackage
        gpkg = directory / Path(f"{name}.atlas.gpkg")
        sensitive = gpd.read_file(gpkg, layer="sensitive", driver="GPKG")

        # Load candidates
        candidates = []
        for cid, parameters in sorted(archive["candidates"].items()):
            layer = gpd.read_file(gpkg, layer=cid, driver="GPKG")
            candidates.append(Candidate(mdf=layer, parameters=parameters))

        return cls(sensitive, candidates=candidates, **archive["metadata"])

    def dict_factory(self, data):
        dictionary = {}
        for key, value in data:
            metadata = self.__dataclass_fields__[key].metadata
            if "exclude_from_dict" in metadata:
                continue

            if "dict_type" in metadata:
                value = type(metadata["dict_type"])(value)

            dictionary[key] = value
        return dictionary

    def donut(self, low, high, **kwargs):
        if isinstance(low, list) and isinstance(high, list):
            distances = self._zip_longest_autofill(low, high)
            for low_val, high_val in distances:
                candidate = Donut(self.sensitive, low_val, high_val, **kwargs).run()
                self.set(candidate)
            return list(self.candidates)[(0 - len(distances)) :]

        elif isinstance(low, (int, float)) and isinstance(high, (int, float)):
            candidate = Donut(self.sensitive, low, high, **kwargs).run()
            self.set(candidate)
            return candidate

        else:
            raise ValueError(
                "Low and high arguments must both be numbers (int, float) or lists of numbers."
            )

    def street(self, low, high, **kwargs):
        if isinstance(low, list) and isinstance(high, list):
            distances = self._zip_longest_autofill(low, high)
            for low_val, high_val in distances:
                candidate = Street(self.sensitive, low_val, high_val, **kwargs).run()
                self.set(candidate)
            return list(self.candidates)[(0 - len(distances)) :]

        elif isinstance(high, (int, float)) and isinstance(low, (int, float)):
            candidate = Street(self.sensitive, low, high, **kwargs).run()
            self.set(candidate)
            return candidate

        else:
            raise ValueError(
                "Low and high arguments must both be numbers (int, float) or lists of numbers."
            )

    @staticmethod
    def _zip_longest_autofill(a, b):
        fill = max(b) if len(b) < len(a) else max(a)
        return list(zip_longest(a, b, fillvalue=fill))
