from dataclasses import dataclass, field
from datetime import datetime
from getpass import getuser
from time import time_ns

import geopandas as gpd
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from . import tools
from .storage import CandidateMeta, Storage


@dataclass
class Candidate:
    sid: str
    cid: str = field(init=False)
    mdf: gpd.GeoDataFrame = field(repr=False)
    storage: Storage = field(repr=False)
    parameters: dict = field(default_factory=lambda: dict())
    author: str = field(default_factory=lambda: getuser())
    timestamp: int = field(default_factory=lambda: int(time_ns()))
    notes: str = ""

    def __post_init__(self) -> None:
        self.cid = self._calc_cid()

    def _calc_cid(self) -> str:
        return tools.checksum(self.mdf)

    def get(self) -> "Candidate":
        if not isinstance(self.mdf, gpd.GeoDataFrame):
            self.mdf = self.storage.read_gdf(self.cid)
        return self

    def save(self) -> None:
        self.get()
        self.storage.save_gdf(self.mdf, self.cid)
        self.storage.session.execute(
            insert(CandidateMeta)
            .values(
                cid=self.cid,
                sid=self.sid,
                parameters=self.parameters,
                author=self.author,
                timestamp=self.timestamp,
                notes=self.notes,
            )
            .on_conflict_do_nothing()
        )
        self.storage.session.commit()

    @classmethod
    def load(cls, cid: str, storage: Storage) -> "Candidate":
        candidate_meta = (
            storage.session.execute(select(CandidateMeta).filter_by(cid=cid)).scalars().first()
        )
        return cls(
            sid=candidate_meta.sid,
            mdf=storage.read_gdf(cid),
            storage=storage,
            parameters=candidate_meta.parameters,
            author=candidate_meta.author,
            timestamp=candidate_meta.timestamp,
            notes=candidate_meta.notes,
        )

    def flush(self) -> None:
        if self.mdf is None:
            return
        else:
            self.save()
            self.mdf = None

    @property
    def time(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp // 1000000000).strftime("%Y-%m-%d %H:%M:%S")
