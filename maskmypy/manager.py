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
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)
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
        self.session = Session(self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)

    @property
    def gpkg_path(self):
        return self.filepath.with_suffix(".gpkg")

    @cached_property
    def sdf(self):
        return self.read_gdf(self.sensitive.id)

    def mdf(self, candidate_or_id):
        c = candidate_or_id
        if isinstance(c, str):
            return self.read_gdf(c)
        elif isinstance(c, Candidate):
            return self.read_gdf(c.id)

    @property
    def candidates(self):
        return self.sensitive.candidates

    @property
    def containers(self):
        return self.sensitive.containers

    @property
    def populations(self):
        return self.sensitive.populations

    @classmethod
    def load(cls, name, filepath):
        filepath = Path(filepath).with_suffix(".db")
        atlas = cls(name, filepath)
        atlas.sensitive = atlas.session.get(Sensitive, atlas.name)
        return atlas

    def read_gdf(self, id):
        return read_file(self.gpkg_path, driver="GPKG", layer=id)

    def save_gdf(self, gdf, id):
        gdf.to_file(self.gpkg_path, driver="GPKG", layer=id)

    def add_sensitive(self, gdf):
        if self.session.get(Sensitive, self.name) is not None:
            raise ValueError("Sensitive layer already exists.")
        id = tools.checksum(gdf)
        self.sensitive = Sensitive(name=self.name, id=id)
        self.session.add(self.sensitive)
        self.save_gdf(gdf, id)
        self.session.commit()

    def add_candidate(self, gdf, params):
        if self.session.get(Sensitive, self.name) is None:
            raise ValueError("Add sensitive layer before adding candidates.")

        id = tools.checksum(gdf)
        if self.session.get(Candidate, id) is not None:
            raise ValueError("Candidate with identical geometry already exists.")

        candidate = Candidate(id=id, sensitive=self.sensitive, params=params)
        self.session.add(candidate)
        self.save_gdf(gdf, id)
        self.session.commit()

    def add_container(self, gdf, name):
        if self.session.get(Container, name) is not None:
            raise ValueError("Container with this name already exists.")
        id = tools.checksum(gdf)
        container = Container(name=name, id=id, sensitive=self.sensitive)
        self.session.add(container)
        self.save_gdf(gdf, id)
        self.session.commit()

    def mask(self, mask, **kwargs):
        m = mask(gdf=self.sdf, **kwargs)
        mdf = m.run()
        params = m.params
        return self.add_candidate(mdf, params)


class Sensitive(Base):
    __tablename__ = "sensitive_table"
    name: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str]
    candidates: Mapped[Optional[List["Candidate"]]] = relationship(back_populates="sensitive")
    containers: Mapped[Optional[List["Container"]]] = relationship(back_populates="sensitive")
    populations: Mapped[Optional[List["Population"]]] = relationship(back_populates="sensitive")

    def __repr__(self):
        return (
            "Sensitive\n"
            f"- Name: {self.name}\n"
            f"- ID: {self.id}\n"
            f"- Candidates: {len(self.candidates)}\n"
            f"- Containers: {len(self.containers)}\n"
            f"- Populations: {len(self.populations)}\n"
        )


class Candidate(Base):
    __tablename__ = "candidate_table"
    id: Mapped[str] = mapped_column(primary_key=True)
    params = mapped_column(PickleType)
    sensitive_name: Mapped[str] = mapped_column(ForeignKey("sensitive_table.name"))
    sensitive: Mapped["Sensitive"] = relationship(back_populates="candidates")
    container: Mapped[Optional["Container"]] = relationship(back_populates="candidate")
    population: Mapped[Optional["Population"]] = relationship(back_populates="candidate")

    def __repr__(self):
        param_string = "\n- ".join([f"{key} = {value}" for key, value in self.params.items()])

        return (
            "Candidate\n"
            f"- ID: {self.id}\n"
            f"Parameters:\n"
            f"- {param_string}\n"
            "Related Layers:\n"
            f"- Sensitive Name: {self.sensitive_name}\n"
            f"- Container Name: {self.container.name if self.container else 'None'}\n"
            f"- Population Name: {self.population.name if self.population else 'None'}\n"
        )


class Container(Base):
    __tablename__ = "containers_table"
    name: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str]
    sensitive_name: Mapped[str] = mapped_column(ForeignKey("sensitive_table.name"))
    sensitive: Mapped["Sensitive"] = relationship(back_populates="containers")
    candidate_id: Mapped[Optional[str]] = mapped_column(ForeignKey("candidate_table.id"))
    candidate: Mapped[Optional["Candidate"]] = relationship(back_populates="container")

    def __repr__(self):
        return f"({self.name}, {self.id})"


class Population(Base):
    __tablename__ = "population_table"
    name: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str]
    sensitive_name: Mapped[str] = mapped_column(ForeignKey("sensitive_table.name"))
    sensitive: Mapped["Sensitive"] = relationship(back_populates="populations")
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidate_table.id"))
    candidate: Mapped["Candidate"] = relationship(back_populates="population")

    def __repr__(self):
        return f"({self.name}, {self.id})"


# class Stats(Base):
#     __tablename__ = "stats_table"
#     id
