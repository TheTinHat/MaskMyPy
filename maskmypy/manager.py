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
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)
from . import tools, analysis
from .masks import Donut, LocationSwap, Street, Voronoi
from sqlalchemy.exc import IntegrityError


class Base(DeclarativeBase):
    pass


@dataclass
class Atlas:
    name: str
    filepath: Path = field(default_factory=lambda: Path.cwd() / "atlas.db")
    in_memory: bool = False

    def __post_init__(self):
        if self.in_memory:
            self.layers = dict()
            self.engine = create_engine("sqlite://")
        else:
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
    def containers_all(self):
        return self.session.scalars(select(Container)).all()

    @property
    def populations(self):
        return self.sensitive.populations

    @property
    def populations_all(self):
        return self.session.scalars(select(Population)).all()

    @classmethod
    def load(cls, name, filepath):
        filepath = Path(filepath).with_suffix(".db")
        atlas = cls(name, filepath)
        atlas.sensitive = atlas.session.get(Sensitive, atlas.name)
        return atlas

    def read_gdf(self, id):
        if self.in_memory:
            return self.layers.get(id)
        else:
            return read_file(self.gpkg_path, driver="GPKG", layer=id)

    def save_gdf(self, gdf, id):
        if self.in_memory:
            self.layers[id] = gdf.copy(deep=True)
        else:
            gdf.to_file(self.gpkg_path, driver="GPKG", layer=id)

    def add_sensitive(self, gdf):
        if self.session.get(Sensitive, self.name) is not None:
            raise ValueError("Sensitive layer already exists.")
        id = tools.checksum(gdf)
        nnd = analysis.nnd(gdf)

        self.sensitive = Sensitive(
            name=self.name, id=id, nnd_min=nnd.min, nnd_max=nnd.max, nnd_mean=nnd.mean
        )
        self.session.add(self.sensitive)
        self.save_gdf(gdf, id)
        self.session.commit()

    def add_candidate(self, gdf, params, container=None, population=None):
        if self.session.get(Sensitive, self.name) is None:
            raise ValueError("Add sensitive layer before adding candidates.")

        id = tools.checksum(gdf)
        nnd = analysis.nnd(gdf)

        if self.session.get(Candidate, id) is not None:
            raise ValueError("Candidate already exists.")

        candidate = Candidate(
            id=id,
            sensitive=self.sensitive,
            params=params,
            container=container,
            population=population,
            nnd_min=nnd.min,
            nnd_max=nnd.max,
            nnd_mean=nnd.mean,
        )

        self.session.add(candidate)
        self.save_gdf(gdf, id)
        self.session.commit()
        return candidate

    def add_container(self, gdf, name):
        if self.session.get(Sensitive, self.name) is None:
            raise ValueError("Add sensitive layer before adding containers.")

        if self.session.get(Container, name) is not None:
            raise ValueError("Container with this name already exists.")

        id = tools.checksum(gdf)
        container = Container(name=name, id=id, sensitive=self.sensitive)
        self.session.add(container)
        self.save_gdf(gdf, id)
        self.session.commit()
        return container

    def get_container(self, name):
        return self.session.get(Container, name)

    def add_population(self, gdf, name):
        if self.session.get(Sensitive, self.name) is None:
            raise ValueError("Add sensitive layer before adding populations.")

        if self.session.get(Population, name) is not None:
            raise ValueError("Population with this name already exists.")
        id = tools.checksum(gdf)
        population = Population(name=name, id=id, sensitive=self.sensitive)
        self.session.add(population)
        self.save_gdf(gdf, id)
        self.session.commit()
        return population

    def get_population(self, name):
        return self.session.get(Population, name)

    def mask(self, mask, **kwargs):
        mask_args = {"gdf": self.sdf}
        candidate_args = {}
        if hasattr(mask, "container"):
            container = kwargs.pop("container", None)
            if isinstance(container, str):
                container = self.get_container(container)
            if isinstance(container, Container):
                mask_args["container"] = self.read_gdf(container.id)
                candidate_args["container"] = container

        if hasattr(mask, "population"):
            population = kwargs.pop("population", None)
            if isinstance(population, str):
                population = self.get_population(population)
            if isinstance(population, Population):
                mask_args["population"] = self.read_gdf(population.id)
                candidate_args["population"] = population

        m = mask(**mask_args, **kwargs)
        mdf = m.run()
        params = m.params
        return self.add_candidate(mdf, params, **candidate_args)

    def donut(self, low: float, high: float, **kwargs):
        return self.mask(Donut, low=low, high=high, **kwargs)

    def drift(self, candidate):
        candidate.drift = analysis.drift(self.sdf, self.mdf(candidate))
        self.session.commit()

    def estimate_k(self, candidate, population):
        kdf = analysis.estimate_k(
            self.sdf, self.mdf(candidate), population_gdf=self.read_gdf(population.id)
        )
        k = analysis.summarize_k(kdf)
        candidate.k_min = k.k_min
        candidate.k_max = k.k_max
        candidate.k_mean = k.k_min
        candidate.k_med = k.k_med
        self.session.commit()


class Sensitive(Base):
    __tablename__ = "sensitive_table"
    name: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str]
    candidates: Mapped[Optional[List["Candidate"]]] = relationship(back_populates="sensitive")
    containers: Mapped[Optional[List["Container"]]] = relationship(back_populates="sensitive")
    populations: Mapped[Optional[List["Population"]]] = relationship(back_populates="sensitive")
    nnd_min: Mapped[Optional[float]]
    nnd_max: Mapped[Optional[float]]
    nnd_mean: Mapped[Optional[float]]

    def __repr__(self):
        return (
            "Sensitive\n"
            f"- Name: {self.name}\n"
            f"- ID: {self.id}\n"
            f"- Candidates: {len(self.candidates)}\n"
            f"- Containers: {len(self.containers)}\n"
            f"- Populations: {len(self.populations)}\n"
            f"- Nearest Neighbor Distance (Min/Max/Mean): {self.nnd_min, self.nnd_max, self.nnd_mean}\n"
        )


class Candidate(Base):
    __tablename__ = "candidate_table"
    id: Mapped[str] = mapped_column(primary_key=True)
    params = mapped_column(PickleType)
    sensitive_name: Mapped[str] = mapped_column(ForeignKey("sensitive_table.name"))
    sensitive: Mapped["Sensitive"] = relationship(back_populates="candidates")
    container: Mapped[Optional["Container"]] = relationship(back_populates="candidate")
    population: Mapped[Optional["Population"]] = relationship(back_populates="candidate")
    k_min: Mapped[Optional[int]]
    k_max: Mapped[Optional[int]]
    k_med: Mapped[Optional[float]]
    k_mean: Mapped[Optional[float]]
    ripley: Mapped[Optional[float]]
    drift: Mapped[Optional[float]]
    nnd_min: Mapped[Optional[float]]
    nnd_max: Mapped[Optional[float]]
    nnd_mean: Mapped[Optional[float]]

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

    @property
    def stats(self):
        print(
            "Candidate Statistics\n"
            f"- ID: {self.id}\n"
            f"- K-Anonmity (Min, Max, Mean, Median): {self.k_min, self.k_max, self.k_mean, self.k_med}\n"
            f"- Ripley: {self.ripley}\n"
            f"- Drift: {self.drift}\n"
            f"- NND (Min/Max/Mean): {self.nnd_min, self.nnd_max, self.nnd_mean}\n"
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
    candidate_id: Mapped[Optional[str]] = mapped_column(ForeignKey("candidate_table.id"))
    candidate: Mapped[Optional["Candidate"]] = relationship(back_populates="population")

    def __repr__(self):
        return f"({self.name}, {self.id})"


# class Stats(Base):
#     __tablename__ = "stats_table"
#     id
