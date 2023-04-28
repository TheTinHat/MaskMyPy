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
    k_min: int = None
    k_max: int = None
    k_med: float = None
    k_mean: float = None
    ripley_rmsd: float = None
    drift: float = None
    nnd_max: float = None
    nnd_min: float = None
    nnd_mean: float = None

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
                k_min=self.k_min,
                k_max=self.k_max,
                k_med=self.k_med,
                k_mean=self.k_mean,
                ripley_rmsd=self.ripley_rmsd,
                drift=self.drift,
                nnd_max=self.nnd_max,
                nnd_min=self.nnd_min,
                nnd_mean=self.nnd_mean,
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
            k_min=candidate_meta.k_min,
            k_max=candidate_meta.k_max,
            k_med=candidate_meta.k_med,
            k_mean=candidate_meta.k_mean,
            ripley_rmsd=candidate_meta.ripley_rmsd,
            drift=candidate_meta.drift,
            nnd_max=candidate_meta.nnd_max,
            nnd_min=candidate_meta.nnd_min,
            nnd_mean=candidate_meta.nnd_mean,
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
