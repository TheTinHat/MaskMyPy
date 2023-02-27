import json
from dataclasses import asdict, dataclass, field
from functools import cached_property
from getpass import getuser
from hashlib import sha256
from time import time_ns

import geopandas as gpd
from pandas.util import hash_pandas_object

from .messages import *


@dataclass
class Candidate:
    gdf: gpd.GeoDataFrame = field(metadata={"exclude_from_dict": True}, repr=False)
    parameters: dict = field(default_factory=lambda: dict())
    author: str = field(default_factory=lambda: getuser())
    created_at: int = field(default_factory=lambda: int(time_ns()))

    def __post_init__(self):
        pass

    def __str__(self):
        return json.dumps(self.parameters)

    @cached_property
    def checksum(self):
        return sha256(hash_pandas_object(self.gdf.geometry).values).hexdigest()

    @property
    def layer_name(self):
        return "_".join([str(self.created_at), self.checksum[0:8]])

    def to_dict(self):
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
