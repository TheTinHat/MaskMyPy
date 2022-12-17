import json
from dataclasses import dataclass, field
from functools import cached_property
from getpass import getuser
from hashlib import sha256
from time import time_ns

import geopandas as gpd
from pandas.util import hash_pandas_object

from .messages import *


@dataclass
class Candidate:
    df: gpd.GeoDataFrame = field(repr=False)
    parameters: dict = field(default_factory=lambda: dict())

    def __post_init__(self):
        if "author" not in self.parameters:
            try:
                self.parameters["author"] = getuser()
            except:
                self.paramters["author"] = "Unkown Author"

        if "created_at" not in self.parameters:
            self.parameters["created_at"] = int(time_ns())

        if "checksum" not in self.parameters:
            self.parameters["checksum"] = self.checksum
        elif "checksum" in self.parameters:
            assert self.parameters["checksum"] == self.checksum, candidate_checksum_mismatch_msg

    def __str__(self):
        return json.dumps(self.parameters)

    @cached_property
    def checksum(self):
        return sha256(hash_pandas_object(self.df.geometry).values).hexdigest()

    @property
    def layer_name(self):
        return "_".join([str(self.parameters["created_at"]), self.checksum[0:8]])
