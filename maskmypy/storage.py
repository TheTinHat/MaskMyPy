from dataclasses import dataclass
from pathlib import Path
from geopandas import GeoDataFrame, read_file
from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    PickleType,
    String,
    Table,
    Text,
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
        Column("author", String),
        Column("container_id", String),
        Column("population_id", String),
        Column("pop_col", String),
        Column("nnd_max", Float),
        Column("nnd_min", Float),
        Column("nnd_mean", Float),
    )


class SensitiveMeta(Base):
    __table__ = Table(
        "sensitive_meta",
        metadata_obj,
        Column("sid", String, primary_key=True),
        Column("timestamp", Integer),
        Column("ripley_results", PickleType),
        Column("nnd_max", Float),
        Column("nnd_min", Float),
        Column("nnd_mean", Float),
    )


class ReferenceMeta(Base):
    __table__ = Table(
        "reference_meta",
        metadata_obj,
        Column("rid", String, primary_key=True),
        Column("timestamp", Integer),
        Column("population", Boolean),
        Column("pop_col", String),
        Column("container", Boolean),
    )


class CandidateMeta(Base):
    __table__ = Table(
        "candidate_meta",
        metadata_obj,
        Column("cid", String, primary_key=True),
        Column("sid", ForeignKey("atlas_meta.sid")),
        Column("parameters", PickleType),
        Column("timestamp", Integer),
        Column("notes", Text),
        Column("k_min", Integer),
        Column("k_max", Integer),
        Column("k_med", Float),
        Column("k_mean", Float),
        Column("ripley_rmse", Float),
        Column("drift", Float),
        Column("nnd_max", Float),
        Column("nnd_min", Float),
        Column("nnd_mean", Float),
    )


@dataclass
class Storage:
    directory: Path
    name: str
    session: Session = None

    def __post_init__(self) -> None:
        engine = create_engine(f"sqlite:///{self.sqlite}")
        self.session = Session(engine)
        metadata_obj.create_all(engine)
        self.directory = Path(self.directory)

    @property
    def gpkg(self) -> Path:
        return self.directory / Path(f"{str(self.name)}.gpkg")

    @property
    def sqlite(self) -> Path:
        return self.directory / Path(f"{str(self.name)}.db")

    def save_gdf(self, gdf: GeoDataFrame, layer_name: str) -> None:
        gdf.to_file(self.gpkg, layer=layer_name, driver="GPKG")

    def read_gdf(self, layer_name: str) -> GeoDataFrame:
        return read_file(self.gpkg, layer=layer_name, driver="GPKG")
