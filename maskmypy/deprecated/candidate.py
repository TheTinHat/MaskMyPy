from dataclasses import dataclass, field
from datetime import datetime
from time import time_ns

from geopandas import GeoDataFrame
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from . import analysis, tools
from .deprecated.storage import CandidateMeta, Storage


@dataclass
class Candidate:
    sid: str
    mdf: GeoDataFrame = field(repr=False)
    storage: Storage = field(repr=False)
    parameters: dict = field(default_factory=lambda: dict())
    timestamp: int = field(default_factory=lambda: int(time_ns()))
    cid: str = None
    notes: str = ""
    k_min: int = None
    k_max: int = None
    k_med: float = None
    k_mean: float = None
    ripley_rmse: float = None
    drift: float = None
    nnd_max: float = None
    nnd_min: float = None
    nnd_mean: float = None

    def __post_init__(self) -> None:
        if not self.cid:
            self.cid = tools.checksum(self.mdf)
        elif self.cid:
            assert self.cid == tools.checksum(self.mdf)

        self.nnd_min, self.nnd_max, self.nnd_mean = analysis.nnd(self.mdf)

    def get(self) -> "Candidate":
        if self.mdf is None:
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
                timestamp=self.timestamp,
                notes=self.notes,
                k_min=self.k_min,
                k_max=self.k_max,
                k_med=self.k_med,
                k_mean=self.k_mean,
                ripley_rmse=self.ripley_rmse,
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
            timestamp=candidate_meta.timestamp,
            notes=candidate_meta.notes,
            k_min=candidate_meta.k_min,
            k_max=candidate_meta.k_max,
            k_med=candidate_meta.k_med,
            k_mean=candidate_meta.k_mean,
            ripley_rmse=candidate_meta.ripley_rmse,
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
