from dataclasses import dataclass
from pathlib import Path
import geopandas as gpd
from sqlalchemy import (
    create_engine,
    Integer,
    String,
    Boolean,
    Column,
    PickleType,
    Table,
    MetaData,
    ForeignKey,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.dialects.sqlite import insert

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
        Column("keep_last", Integer),
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


@dataclass
class Storage:
    directory: Path
    name: str

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

    def save_atlas(self, atlas):
        atlas.sensitive.to_file(self.gpkg, layer_name=atlas.name, driver="GPKG")
        insert_stmt = insert(AtlasMeta).values(
            name=atlas.name,
            sid=atlas.sid,
            autosave=atlas.autosave,
            autoflush=atlas.autoflush,
            keep_last=atlas.keep_last,
        )
        self.session.execute(insert_stmt.on_conflict_do_nothing())
        self.session.commit()

        for candidate in atlas.candidates:
            self.save_candidate(candidate)

    def save_candidate(self, candidate):
        candidate.mdf.to_file(self.gpkg, layer_name=candidate.cid, driver="GPKG")
        insert_stmt = insert(CandidateMeta).values(
            cid=candidate.cid,
            sid=candidate.sid,
            parameters=candidate.parameters,
            author=candidate.author,
            timestamp=candidate.timestamp,
        )
        self.session.execute(insert_stmt.on_conflict_do_nothing())
        self.session.commit()

    def get_sensitive_gdf(self, name):
        return gpd.GeoDataFrame.from_file(self.gpkg, layer_name=name, driver="GPKG")

    def get_atlas_meta(self, name):
        return self.session.execute(select(AtlasMeta).filter_by(name=name)).scalars().first()

    def list_candidates(self, sid):
        return (
            self.session.execute(
                select(CandidateMeta).filter_by(sid=sid).order_by(CandidateMeta.timestamp)
            )
            .scalars()
            .all()
        )

    def get_candidate_mdf(self, cid):
        return gpd.GeoDataFrame.from_file(self.gpkg, layer_name=cid, driver="GPKG")

    def get_candidate_meta(self, cid):
        return self.session.execute(select(CandidateMeta).filter_by(cid=cid)).scalars().first()
