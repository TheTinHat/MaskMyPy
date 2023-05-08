from functools import cached_property
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass, field
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
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship
from . import tools
from sqlalchemy.exc import IntegrityError


class Base(DeclarativeBase):
    pass


@dataclass
class Atlas:
    name: str
    filepath: Path = field(default_factory=lambda: Path.cwd() / "atlas.db")

    def __post_init__(self):
        self.filepath = Path(self.filepath)
        if self.filepath.suffix != ".db":
            self.filepath = self.filepath.parent / (self.filepath.name + ".db")

        self.engine = create_engine(f"sqlite:///{self.filepath}")
        self.session = Session(self.engine)
        Base.metadata.create_all(self.engine)

    @property
    def geopath(self):
        return self.filepath.with_suffix(".gpkg")

    @property
    def candidates(self):
        return self.sensitive.candidates

    @classmethod
    def load(cls, name, filepath):
        filepath = Path(filepath).with_suffix(".db")
        atlas = cls(name, filepath)
        atlas.sensitive = atlas.session.get(Sensitive, atlas.name)
        return atlas

    def read_gdf(self, name):
        return read_file(self.geopath, driver="GPKG", layer=name)

    def save_gdf(self, gdf, name):
        gdf.to_file(self.geopath, driver="GPKG", layer=name)

    def add_sensitive(self, gdf):
        with self.session.begin():
            if self.session.get(Sensitive, self.name) is not None:
                raise ValueError("Sensitive layer already exists.")
            self.sensitive = Sensitive(name=self.name)
            self.session.add(self.sensitive)
            self.save_gdf(gdf, self.name)

    def add_candidate(self, gdf, params):
        with self.session.begin():
            if self.session.get(Sensitive, self.name) is None:
                raise ValueError("Add sensitive layer before adding candidates.")

            id = tools.checksum(gdf)
            if self.session.get(Candidate, id) is not None:
                raise ValueError("Candidate with identical geometry already exists.")

            candidate = Candidate(id=id, sensitive=self.sensitive, params=params)
            self.session.add(candidate)
            self.save_gdf(gdf, id)


class Sensitive(Base):
    __tablename__ = "sensitive_table"
    name: Mapped[str] = mapped_column(primary_key=True)
    candidates: Mapped[Optional[List["Candidate"]]] = relationship(back_populates="sensitive")
    containers: Mapped[Optional[List["Container"]]] = relationship(back_populates="sensitive")
    populations: Mapped[Optional[List["Population"]]] = relationship(back_populates="sensitive")


class Candidate(Base):
    __tablename__ = "candidate_table"
    id: Mapped[str] = mapped_column(primary_key=True)
    params = mapped_column(PickleType)
    sensitive_name: Mapped[str] = mapped_column(ForeignKey("sensitive_table.name"))
    sensitive: Mapped["Sensitive"] = relationship(back_populates="candidates")
    container: Mapped[Optional["Container"]] = relationship(back_populates="candidate")
    population: Mapped[Optional["Population"]] = relationship(back_populates="candidate")


class Container(Base):
    __tablename__ = "containers_table"
    name: Mapped[str] = mapped_column(primary_key=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidate_table.id"))
    candidate: Mapped["Candidate"] = relationship(back_populates="container")
    sensitive_name: Mapped[str] = mapped_column(ForeignKey("sensitive_table.name"))
    sensitive: Mapped["Sensitive"] = relationship(back_populates="containers")


class Population(Base):
    __tablename__ = "population_table"
    name: Mapped[str] = mapped_column(primary_key=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidate_table.id"))
    candidate: Mapped["Candidate"] = relationship(back_populates="population")
    sensitive_name: Mapped[str] = mapped_column(ForeignKey("sensitive_table.name"))
    sensitive: Mapped["Sensitive"] = relationship(back_populates="populations")
