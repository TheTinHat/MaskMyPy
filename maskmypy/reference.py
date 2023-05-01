from dataclasses import dataclass, field
from datetime import datetime
from time import time_ns
import geopandas as gpd
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from . import analysis, tools
from .storage import ReferenceMeta, Storage


@dataclass()
class Reference:
    gdf: gpd.GeoDataFrame = field(repr=False)
    storage: Storage = field(repr=False)
    population: bool = False
    pop_col: str = "pop"
    container: bool = False
    rid: str = None
    timestamp: int = field(default_factory=lambda: int(time_ns()))

    def __post_init__(self) -> None:
        self.gdf = self.gdf.copy(deep=True)
        if not self.rid:
            self.rid = tools.checksum(self.gdf)
        elif self.rid:
            assert self.rid == tools.checksum(self.gdf)

        self.nnd_min, self.nnd_max, self.nnd_mean = analysis.nnd(self.gdf)

    def save(self) -> None:
        self.storage.save_gdf(self.sdf, self.rid)
        self.storage.session.execute(
            insert(ReferenceMeta)
            .values(
                rid=self.rid,
                timestamp=self.timestamp,
                population=self.population,
                container=self.container,
                pop_col=self.pop_col,
            )
            .on_conflict_do_nothing()
        )
        self.storage.session.commit()

    @classmethod
    def load(cls, rid: str, storage: Storage) -> "Reference":
        reference_meta = (
            storage.session.execute(select(ReferenceMeta).filter_by(rid=rid)).scalars().first()
        )
        return cls(
            rid=reference_meta.rid,
            gdf=storage.read_gdf(rid),
            storage=storage,
            timestamp=reference_meta.timestamp,
            population=reference_meta.population,
            container=reference_meta.container,
            pop_col=reference_meta.pop_col,
        )

    @property
    def time(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp // 1000000000).strftime("%Y-%m-%d %H:%M:%S")
