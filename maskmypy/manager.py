from functools import cached_property
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from geopandas import GeoDataFrame, read_file
from sqlalchemy import ForeignKey, PickleType, create_engine, select, Column, Table
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
)
from . import tools, analysis
from .masks import Donut, LocationSwap, Street, Voronoi
from inspect import getfullargspec


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
    def censuses(self):
        return self.sensitive.censuses

    @property
    def censuses_all(self):
        return self.session.scalars(select(Census)).all()

    @property
    def addresses(self):
        return self.sensitive.addresses

    @property
    def addresses_all(self):
        return self.session.scalars(select(Address)).all()

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

    def add_candidate(self, gdf, params, container=None, census=None, address=None):
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
            census=census,
            address=address,
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

        id = tools.checksum(gdf)
        container = self.session.get(Container, name)

        if container and container.id != id:
            raise ValueError("A different container layer with this name already exists")

        elif container and container.id == id:
            if container not in self.containers:
                self.sensitive.containers.append(container)
            else:
                return container

        else:
            container = Container(name=name, id=id)
            self.sensitive.containers.append(container)

        self.session.add(container)
        self.save_gdf(gdf, id)
        self.session.commit()
        return container

    def relate_container(self, name):
        container = self.get_container(name)
        self.sensitive.containers.append(container)
        self.session.commit()

    def get_container(self, name):
        return self.session.get(Container, name)

    def add_census(self, gdf, name, pop_col):
        """NEEDS TESTS"""
        if self.session.get(Sensitive, self.name) is None:
            raise ValueError("Add sensitive layer before adding census layers.")

        id = tools.checksum(gdf)
        census = self.session.get(Census, name)

        if census and census.id != id:
            raise ValueError("A different census layer with this name already exists")
        elif census and census.id == id:
            if census not in self.censuses:
                self.sensitive.censuses.append(census)
            else:
                return census

        else:
            census = Census(name=name, id=id, pop_col=pop_col)
            self.sensitive.censuses.append(census)

        self.session.add(census)
        self.save_gdf(gdf, id)
        self.session.commit()
        return census

    def relate_census(self, name):
        census = self.get_census(name)
        self.sensitive.containers.append(census)
        self.session.commit()

    def get_census(self, name):
        """NEEDS TESTS"""
        return self.session.get(Census, name)

    def add_address(self, gdf, name):
        if self.session.get(Sensitive, self.name) is None:
            raise ValueError("Add sensitive layer before adding address layers.")

        id = tools.checksum(gdf)
        address = self.session.get(Address, name)

        if address and address.id != id:
            raise ValueError("A different address layer with this name already exists")

        elif address and address.id == id:
            if address not in self.addresses:
                self.sensitive.addresses.append(address)
            else:
                return address

        else:
            address = Address(name=name, id=id)
            self.sensitive.addresses.append(address)

        self.session.add(address)
        self.save_gdf(gdf, id)
        self.session.commit()
        return address

    def relate_address(self, name):
        address = self.get_address(name)
        self.sensitive.containers.append(address)
        self.session.commit()

    def get_address(self, name):
        return self.session.get(Address, name)

    def mask(self, mask, **kwargs):
        mask_args = {"gdf": self.sdf}
        candidate_args = {}
        arg_spec = getfullargspec(mask)[0]

        if "container" in arg_spec:
            container = kwargs.pop("container", None)
            if isinstance(container, str):
                container = self.get_container(container)
            if isinstance(container, Container):
                mask_args["container"] = self.read_gdf(container.id)
                candidate_args["container"] = container

        if "census" in arg_spec:
            census = kwargs.pop("census", None)
            if isinstance(census, str):
                census = self.get_census(census)
            if isinstance(census, Census):
                mask_args["census"] = self.read_gdf(census.id)
                candidate_args["census"] = census

        if "address" in arg_spec:
            address = kwargs.pop("address", None)
            if isinstance(address, str):
                address = self.get_address(address)
            if isinstance(address, Address):
                mask_args["address"] = self.read_gdf(address.id)
                candidate_args["address"] = address

        m = mask(**mask_args, **kwargs)
        mdf = m.run()
        params = m.params
        return self.add_candidate(mdf, params, **candidate_args)

    def donut(self, low: float, high: float, **kwargs):
        return self.mask(Donut, low=low, high=high, **kwargs)

    def donut_i(self, distance_list, **kwargs):
        results = []
        for distance_pair in distance_list:
            low = distance_pair[0]
            high = distance_pair[1]
            if low > high:
                raise ValueError("Low distance value exceeds high distance value.")
            results.append(self.donut(low=low, high=high, **kwargs))
        return results

    def street(self, low: int, high: int, **kwargs):
        return self.mask(Street, low=low, high=high, **kwargs)

    def voronoi(self, **kwargs):
        return self.mask(Voronoi, **kwargs)

    def location_swap(self, low: float, high: float, address, **kwargs):
        return self.mask(LocationSwap, low=low, high=high, address=address, **kwargs)

    def drift(self, candidate):
        candidate.drift = analysis.drift(self.sdf, self.mdf(candidate))
        self.session.commit()

    def estimate_k(self, candidate, census):
        kdf = analysis.estimate_k(
            self.sdf,
            self.mdf(candidate),
            census_gdf=self.read_gdf(census.id),
            pop_col=census.pop_col,
        )
        k = analysis.summarize_k(kdf)
        candidate.k_min = k.k_min
        candidate.k_max = k.k_max
        candidate.k_mean = k.k_min
        candidate.k_med = k.k_med
        self.session.commit()

    def calculate_k(self, candidate, address):
        kdf = analysis.calculate_k(
            self.sdf,
            self.mdf(candidate),
            address=self.read_gdf(address.id),
        )
        k = analysis.summarize_k(kdf)
        candidate.k_min = k.k_min
        candidate.k_max = k.k_max
        candidate.k_mean = k.k_min
        candidate.k_med = k.k_med
        self.session.commit()

    def analyze_all(self, address=None, census=None):
        K_FIELDS = ["k_min", "k_max", "k_mean", "k_med"]

        address = self.get_address(address) if isinstance(address, str) else address
        census = self.get_census(census) if isinstance(census, str) else census

        for candidate in self.candidates:
            if not candidate.drift:
                self.drift(candidate)

            if not all([getattr(candidate, field) for field in K_FIELDS]):
                if address:
                    self.calculate_k(candidate, address)
                elif census:
                    self.estimate_k(candidate, census)

    def rank(self, metric, min_k=None, desc=False):
        stmt = select(Candidate).where(Candidate.sensitive == self.sensitive)

        if min_k:
            stmt = stmt.where(Candidate.k_min >= min_k)

        metric = getattr(Candidate, metric)

        if not desc:
            stmt = stmt.order_by(metric)
        elif desc:
            stmt = stmt.order_by(metric.desc())

        results = self.session.execute(stmt).scalars()
        return [result for result in results]


container_association_table = Table(
    "container_association_table",
    Base.metadata,
    Column("sensitive_name", ForeignKey("sensitive_table.name"), primary_key=True),
    Column("container_name", ForeignKey("container_table.name"), primary_key=True),
)

census_association_table = Table(
    "census_association_table",
    Base.metadata,
    Column("sensitive_name", ForeignKey("sensitive_table.name"), primary_key=True),
    Column("census_name", ForeignKey("census_table.name"), primary_key=True),
)

address_association_table = Table(
    "address_association_table",
    Base.metadata,
    Column("sensitive_name", ForeignKey("sensitive_table.name"), primary_key=True),
    Column("address_name", ForeignKey("address_table.name"), primary_key=True),
)


class Sensitive(Base):
    __tablename__ = "sensitive_table"
    name: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str]
    candidates: Mapped[Optional[List["Candidate"]]] = relationship(back_populates="sensitive")
    containers: Mapped[Optional[List["Container"]]] = relationship(
        secondary=container_association_table, back_populates="sensitives"
    )
    censuses: Mapped[Optional[List["Census"]]] = relationship(
        secondary=census_association_table, back_populates="sensitives"
    )
    addresses: Mapped[Optional[List["Address"]]] = relationship(
        secondary=address_association_table, back_populates="sensitives"
    )
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
            f"- Census Layers: {len(self.censuses)}\n"
            f"- Address Layers: {len(self.addresses)}\n"
            f"- Nearest Neighbor Distance (Min/Max/Mean): {self.nnd_min, self.nnd_max, self.nnd_mean}\n"
        )


class Candidate(Base):
    __tablename__ = "candidate_table"
    id: Mapped[str] = mapped_column(primary_key=True)
    params = mapped_column(PickleType)
    sensitive_name: Mapped[str] = mapped_column(ForeignKey("sensitive_table.name"))
    sensitive: Mapped["Sensitive"] = relationship(back_populates="candidates")
    container_name: Mapped[Optional[str]] = mapped_column(ForeignKey("container_table.name"))
    container: Mapped[Optional["Container"]] = relationship(back_populates="candidates")
    census_name: Mapped[Optional[str]] = mapped_column(ForeignKey("census_table.name"))
    census: Mapped[Optional["Census"]] = relationship(back_populates="candidates")
    address_name: Mapped[Optional[str]] = mapped_column(ForeignKey("address_table.name"))
    address: Mapped[Optional["Address"]] = relationship(back_populates="candidates")
    k_min: Mapped[Optional[int]]
    k_max: Mapped[Optional[int]]
    k_med: Mapped[Optional[float]]
    k_mean: Mapped[Optional[float]]
    ripley: Mapped[Optional[float]]
    drift: Mapped[Optional[float]]
    nnd_min: Mapped[Optional[float]]
    nnd_max: Mapped[Optional[float]]
    nnd_mean: Mapped[Optional[float]]

    @property
    def pretty(self):
        param_string = "\n- ".join([f"{key} = {value}" for key, value in self.params.items()])

        return (
            "Candidate\n"
            f"- ID: {self.id}\n"
            f"Parameters:\n"
            f"- {param_string}\n"
            "Related Layers:\n"
            f"- Sensitive Name: {self.sensitive_name}\n"
            f"- Container Name: {self.container.name if self.container else 'None'}\n"
            f"- Census Name: {self.census.name if self.census else 'None'}\n"
            f"- Addresses Name: {self.address.name if self.address else 'None'}\n"
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
    __tablename__ = "container_table"
    name: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str]
    sensitives: Mapped[Optional[List["Sensitive"]]] = relationship(
        secondary=container_association_table, back_populates="containers"
    )
    candidates: Mapped[Optional[List["Candidate"]]] = relationship(back_populates="container")

    def __repr__(self):
        return f"({self.name}, {self.id})"


class Census(Base):
    __tablename__ = "census_table"
    name: Mapped[str] = mapped_column(primary_key=True)
    pop_col: Mapped[str]
    id: Mapped[str]
    sensitives: Mapped[Optional[List["Sensitive"]]] = relationship(
        secondary=census_association_table, back_populates="censuses"
    )
    candidates: Mapped[Optional[List["Candidate"]]] = relationship(back_populates="census")

    def __repr__(self):
        return f"({self.name}, {self.id})"


class Address(Base):
    __tablename__ = "address_table"
    name: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str]
    sensitives: Mapped[Optional[List["Sensitive"]]] = relationship(
        secondary=address_association_table, back_populates="addresses"
    )
    candidates: Mapped[Optional[List["Candidate"]]] = relationship(back_populates="address")

    def __repr__(self):
        return f"({self.name}, {self.id})"
