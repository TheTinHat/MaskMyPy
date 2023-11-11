from dataclasses import dataclass, field
from datetime import datetime
from time import time_ns

import geopandas as gpd
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from .. import analysis, tools
from .storage import SensitiveMeta, Storage


@dataclass()
class Sensitive:
    sdf: gpd.GeoDataFrame = field(repr=False)
    storage: Storage = field(repr=False)
    sid: str = None
    timestamp: int = field(default_factory=lambda: int(time_ns()))
    ripley_results: dict = field(default_factory=lambda: dict())
    nnd_max: float = None
    nnd_min: float = None
    nnd_mean: float = None

    def __post_init__(self) -> None:
        self.sdf = self.sdf.copy(deep=True)
        if not self.sid:
            self.sid = tools._checksum(self.sdf)
        elif self.sid:
            assert self.sid == tools._checksum(self.sdf)

        self.nnd_min, self.nnd_max, self.nnd_mean = analysis.nnd(self.sdf)

    def save(self) -> None:
        self.storage.save_gdf(self.sdf, self.sid)
        self.storage.session.execute(
            insert(SensitiveMeta)
            .values(
                sid=self.sid,
                timestamp=self.timestamp,
                ripley_results=self.ripley_results,
                nnd_max=self.nnd_max,
                nnd_min=self.nnd_min,
                nnd_mean=self.nnd_mean,
            )
            .on_conflict_do_nothing()
        )
        self.storage.session.commit()

    @classmethod
    def load(cls, sid: str, storage: Storage) -> "Sensitive":
        sensitive_meta = (
            storage.session.execute(select(SensitiveMeta).filter_by(sid=sid)).scalars().first()
        )
        return cls(
            sid=sensitive_meta.sid,
            sdf=storage.read_gdf(sid),
            storage=storage,
            timestamp=sensitive_meta.timestamp,
            ripley_results=sensitive_meta.ripley_results,
            nnd_max=sensitive_meta.nnd_max,
            nnd_min=sensitive_meta.nnd_min,
            nnd_mean=sensitive_meta.nnd_mean,
        )

    @property
    def time(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp // 1000000000).strftime("%Y-%m-%d %H:%M:%S")

    def ripleys_k(self, steps=10, max_dist=None):
        max_dist = analysis._ripleys_rot(self.sdf) if not max_dist else max_dist
        try:
            return self.ripley_results[steps][max_dist]
        except Exception:
            result = analysis.ripleys_k(
                self.sdf,
                max_dist=analysis._ripleys_rot(self.sdf),
                min_dist=(max_dist / steps),
                steps=steps,
            )
            self.ripley_results[steps] = {max_dist: result}
            return result
