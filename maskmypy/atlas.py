from getpass import getuser
import json
from dataclasses import dataclass, field, asdict
from functools import cached_property
from hashlib import sha256
from pathlib import Path
from time import time, time_ns
from collections import deque
import geopandas as gpd
from pandas.util import hash_pandas_object
from messages import *


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

    @property
    def srid(self):
        return self.sensitive.crs

    @cached_property
    def checksum(self):
        return sha256(hash_pandas_object(self.sensitive).values).hexdigest()

    @property
    def gpkg_path(self):
        return self.directory / f"{str(self.name)}.atlas.gpkg"

    @property
    def archive_path(self):
        return self.directory / f"{str(self.name)}.atlas.json"

    @property
    def metadata(self):
        return asdict(self, dict_factory=self.dict_factory)

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
            candidates.append(Candidate(df=layer, parameters=parameters))

        return cls(sensitive, candidates=candidates, **archive["metadata"])

    def save_atlas(self):
        candidate_parameters = {cand.layer_name: cand.parameters for cand in self.candidates}

        archive = {"metadata": self.metadata, "candidates": candidate_parameters}

        with open(self.archive_path, "w") as file:
            file.write(json.dumps(archive))

        self.sensitive.to_file(self.gpkg_path, layer="sensitive", driver="GPKG")
        for index in range(len(self.candidates)):
            self.save_candidate(index)

        return True

    def save_candidate(self, index=None, flush=None):
        candidate = self.candidates[index]
        if isinstance(candidate.df, gpd.GeoDataFrame):
            candidate.df.to_file(self.gpkg_path, layer=candidate.layer_name, driver="GPKG")
            if flush or self.autoflush:
                candidate.df = None
        return True

    def set(self, candidate):
        self.candidates.append(candidate)
        if self.autosave:
            self.save_candidate(-1)

    def get(self, index=-1, parameters=False):
        candidate = self.candidates[index]

        if candidate.df is None:
            try:
                candidate.df = gpd.read_file(
                    self.gpkg_path, layer=candidate.layer_name, driver="GPKG"
                )
            except Exception as err:
                print(f"Unable to load candidate dataframe: {err}")
        elif not isinstance(candidate.df, gpd.GeoDataFrame):
            raise Exception("Candidate dataframe is an unknown data type.")

        if not parameters:
            return candidate.df

        return {"df": candidate.df, "parameters": candidate.parameters}


@dataclass
class Candidate:
    df: gpd.GeoDataFrame = field(repr=False)
    parameters: dict = None

    def __post_init__(self):
        if "author" not in self.parameters:
            self.parameters["author"] = getuser()

        if "created_at" not in self.parameters:
            self.parameters["created_at"] = int(time_ns())

        if "checksum" not in self.parameters:
            self.parameters["checksum"] = self.checksum
        elif "checksum" in self.parameters:
            assert self.parameters["checksum"] == self.checksum, candidate_checksum_mismatch_msg

    def __str__(self):
        parameters = self.parameters
        return json.dumps(parameters)

    @cached_property
    def checksum(self):
        return sha256(hash_pandas_object(self.df).values).hexdigest()

    @property
    def layer_name(self):
        return "_".join([str(self.parameters["created_at"]), self.checksum[0:8]])
