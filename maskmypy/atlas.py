import json
from collections import deque
from dataclasses import asdict, dataclass, field
from functools import cached_property
from hashlib import sha256
from pathlib import Path

import geopandas as gpd
from pandas.util import hash_pandas_object

from .candidate import Candidate
from .donut import donut
from .messages import *


@dataclass
class Atlas:
    sensitive: gpd.GeoDataFrame = field(metadata={"exclude_from_dict": True}, repr=False)
    candidates: deque = field(metadata={"exclude_from_dict": True}, default=None, repr=False)
    directory: Path = field(metadata={"dict_type": str()}, default_factory=lambda: Path.cwd())
    autosave: bool = False
    autoflush: bool = False
    name: str = None
    keep_last: int = 10

    def __post_init__(self):
        self.directory = Path(self.directory)

        if not self.name:
            self.name = "".join(["atlas_", self.checksum[0:8]])

        if not self.directory.is_dir():
            self.directory.mkdir(exist_ok=True, parents=True)

        if not self.candidates:
            self.candidates = deque(maxlen=self.keep_last)

    @cached_property
    def checksum(self):
        return sha256(hash_pandas_object(self.sensitive.geometry).values).hexdigest()

    @cached_property
    def crs(self):
        return self.sensitive.crs

    @property
    def gpkg_path(self):
        return self.directory / f"{str(self.name)}.atlas.gpkg"

    @property
    def archive_path(self):
        return self.directory / f"{str(self.name)}.atlas.json"

    @property
    def metadata(self):
        return asdict(self, dict_factory=self.dict_factory)

    def set(self, candidate):
        assert candidate.gdf.crs == self.crs, candidate_crs_mismatch_msg
        assert candidate.checksum != self.checksum, candidate_identical_to_sensitive_msg
        self.candidates.append(candidate)
        if self.autosave:
            self.save_candidate(-1)

    def get(self, index=-1):
        candidate = self.candidates[index]

        if candidate.gdf is None:
            try:
                candidate.gdf = gpd.read_file(
                    self.gpkg_path, layer=candidate.layer_name, driver="GPKG"
                )
            except Exception as err:
                print(f"Unable to load candidate dataframe: {err}")
        elif not isinstance(candidate.gdf, gpd.GeoDataFrame):
            raise Exception("Candidate dataframe is an unknown data type.")

        return candidate

    def save_candidate(self, index=None, flush=None):
        candidate = self.candidates[index]
        if isinstance(candidate.gdf, gpd.GeoDataFrame):
            candidate.gdf.to_file(self.gpkg_path, layer=candidate.layer_name, driver="GPKG")
            if flush or self.autoflush:
                candidate.gdf = None
        return True

    def save_atlas(self):
        candidate_parameters = {cand.layer_name: cand.parameters for cand in self.candidates}
        archive = {"metadata": self.metadata, "candidates": candidate_parameters}

        with open(self.archive_path, "w") as file:
            file.write(json.dumps(archive))

        self.sensitive.to_file(self.gpkg_path, layer="sensitive", driver="GPKG")
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
        gpkg_path = directory / Path(f"{name}.atlas.gpkg")
        sensitive = gpd.read_file(gpkg_path, layer="sensitive", driver="GPKG")

        # Load candidates
        candidates = []
        for layer_name, parameters in sorted(archive["candidates"].items()):
            layer = gpd.read_file(gpkg_path, layer=layer_name, driver="GPKG")
            candidates.append(Candidate(gdf=layer, parameters=parameters))

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

    def donut(self, min, max, **kwargs):
        candidate = donut(self.sensitive, min, max, **kwargs)
        self.set(candidate)
        return candidate
