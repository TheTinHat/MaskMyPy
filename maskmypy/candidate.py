from dataclasses import dataclass, field
from functools import cached_property
from getpass import getuser
from time import time_ns
from datetime import datetime
import geopandas as gpd

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
        self.cid

    def __repr__(self):
        return ",".join([self.cid, str(self.parameters)])

    @cached_property
    def cid(self):
        return tools.checksum(self.mdf)

    def get(self):
        if not isinstance(self.mdf, gpd.GeoDataFrame):
            self.mdf = self.storage.get_candidate_mdf(self.cid)
        return self

    def save(self):
        self.storage.save_candidate(self)

    def flush(self):
        self.save()
        self.mdf = None

    @property
    def time(self):
        return datetime.fromtimestamp(self.timestamp // 1000000000).strftime("%Y-%m-%d %H:%M:%S")
