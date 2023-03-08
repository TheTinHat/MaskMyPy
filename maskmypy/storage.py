from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    PickleType,
    String,
    Table,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session

metadata_obj = MetaData()


class Base(DeclarativeBase):
    pass


class AtlasMeta(Base):
    __table__ = Table(
        "atlas_meta",
        metadata_obj,
        Column("name", String, primary_key=True),
        Column("sid", String),
        Column("autosave", Boolean),
        Column("autoflush", Boolean),
        Column("container_id", String),
        Column("population_id", String),
    )


class CandidateMeta(Base):
    __table__ = Table(
        "candidate_meta",
        metadata_obj,
        Column("cid", String, primary_key=True),
        Column("sid", ForeignKey("atlas_meta.sid")),
        Column("parameters", PickleType),
        Column("author", String),
        Column("timestamp", Integer),
    )


class CandidateStats(Base):
    __table__ = Table(
        "candidate_stats",
        metadata_obj,
        Column("id", Integer, primary_key=True),
        Column("cid", ForeignKey("candidate_meta.cid")),
    )


@dataclass
class Storage:
    directory: Path
    name: str
    session: Session = None

    def __post_init__(self):
        engine = create_engine(f"sqlite:///{self.sqlite}")
        self.session = Session(engine)
        metadata_obj.create_all(engine)
        self.directory = Path(self.directory)

    @property
    def gpkg(self):
        return self.directory / Path(f"{str(self.name)}.gpkg")

    @property
    def sqlite(self):
        return self.directory / Path(f"{str(self.name)}.db")

    def save_gdf(self, gdf, layer_name):
        gdf.to_file(self.gpkg, layer=layer_name, driver="GPKG")

    def read_gdf(self, layer_name):
        return gpd.read_file(self.gpkg, layer=layer_name, driver="GPKG")
