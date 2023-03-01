import json
from dataclasses import asdict, dataclass, field
from functools import cached_property
from getpass import getuser
from hashlib import sha256
from time import time_ns
from datetime import datetime
import geopandas as gpd
from pandas.util import hash_pandas_object

from .messages import *
from .storage import Storage
from . import tools


@dataclass
class Candidate:
    sid: str
    mdf: gpd.GeoDataFrame
    storage: Storage
    parameters: dict = field(default_factory=lambda: dict())
    author: str = field(default_factory=lambda: getuser())
    timestamp: int = field(default_factory=lambda: int(time_ns()))

    def __post_init__(self):
        pass

    @cached_property
    def cid(self):
        return tools.checksum(self.mdf)

    @property
    def get(self):
        self.mdf = self.storage.get_candidate(self.cid)

    def put(self):
        pass

    def flush(self):
        self.storage.save_candidate(self)
        self.mdf = None

    @property
    def time(self):
        return datetime.fromtimestamp(self.timestamp // 1000000000).strftime("%Y-%m-%d %H:%M:%S")
