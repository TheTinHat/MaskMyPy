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
        return (
            "Sensitive\n"
            f"- Name: {self.name}\n"
            f"- ID: {self.id}\n"
            f"- Candidates: {len(self.candidates)}\n"
            f"- Nominee: {self.nominee}\n"
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
