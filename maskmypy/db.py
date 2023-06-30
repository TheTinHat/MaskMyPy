from typing import List, Optional

from sqlalchemy import Column, ForeignKey, PickleType, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


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

SENSITIVE_STATS_FIELDS = ["nnd_min", "nnd_mean", "nnd_max"]


class Sensitive(Base):
    __tablename__ = "sensitive_table"
    name: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str]
    crs: Mapped[str]
    candidates: Mapped[Optional[List["Candidate"]]] = relationship(
        back_populates="sensitive", foreign_keys="[Candidate.sensitive_name]"
    )
    nominee: Mapped[Optional[str]] = mapped_column(ForeignKey("candidate_table.id"))
    containers: Mapped[Optional[List["Container"]]] = relationship(
        secondary=container_association_table,
        back_populates="sensitives",
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
        return f"Sensitive({self.name}, {self.id})"

    @property
    def as_dict(self):
        data = {"name": self.name, "id": self.id}
        for field in SENSITIVE_STATS_FIELDS:
            data[field] = getattr(self, field)

        data["containers"] = [container.name for container in self.containers]
        data["censuses"] = [census.name for census in self.censuses]
        data["addresses"] = [address.name for address in self.addresses]
        return data


CANDIDATE_STATS_FIELDS = [
    "k_min",
    "k_mean",
    "k_med",
    "k_max",
    "drift",
    "nnd_min",
    "nnd_mean",
    "nnd_max",
    "ripley",
]


class Candidate(Base):
    __tablename__ = "candidate_table"
    id: Mapped[str] = mapped_column(primary_key=True)
    params = mapped_column(PickleType)
    sensitive_name: Mapped[str] = mapped_column(ForeignKey("sensitive_table.name"))
    sensitive: Mapped["Sensitive"] = relationship(
        back_populates="candidates", foreign_keys=[sensitive_name]
    )
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

    def __repr__(self):
        return f"Candidate({self.sensitive_name}, {self.id})"

    @property
    def as_dict(self):
        data = {"id": self.id}
        for field in CANDIDATE_STATS_FIELDS:
            data[field] = getattr(self, field)

        data["container"] = self.container.name if self.container else "None"
        data["census"] = self.census.name if self.census else "None"
        data["address"] = self.address.name if self.address else "None"
        for key, value in self.params.items():
            data[key] = value
        return data


class Container(Base):
    __tablename__ = "container_table"
    name: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str]
    sensitives: Mapped[Optional[List["Sensitive"]]] = relationship(
        secondary=container_association_table, back_populates="containers"
    )
    candidates: Mapped[Optional[List["Candidate"]]] = relationship(back_populates="container")

    def __repr__(self):
        return f"Container({self.name}, {self.id})"


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
        return f"Census({self.name}, {self.id})"


class Address(Base):
    __tablename__ = "address_table"
    name: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[str]
    sensitives: Mapped[Optional[List["Sensitive"]]] = relationship(
        secondary=address_association_table, back_populates="addresses"
    )
    candidates: Mapped[Optional[List["Candidate"]]] = relationship(back_populates="address")

    def __repr__(self):
        return f"Address({self.name}, {self.id})"
