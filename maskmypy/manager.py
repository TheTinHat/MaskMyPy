from dataclasses import dataclass, field
from functools import cached_property
from inspect import getfullargspec
from pathlib import Path

from pandas import DataFrame
from geopandas import GeoDataFrame, read_file
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from . import analysis, tools
from .db import Address, Base, Candidate, Census, Container, Sensitive, CANDIDATE_STATS_FIELDS
from .masks import Donut, LocationSwap, Street, Voronoi


@dataclass
class Atlas:
    name: str
    filepath: Path = field(default_factory=lambda: Path.cwd() / "atlas.db")
    in_memory: bool = False

    def __post_init__(self) -> None:
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

    @cached_property
    def _gpkg_path(self) -> Path:
        return self.filepath.with_suffix(".gpkg")

    @cached_property
    def sdf(self) -> GeoDataFrame:
        return self.read_gdf(self.sensitive.id)

    def mdf(self, candidate_or_id: Candidate | str) -> GeoDataFrame:
        c = candidate_or_id
        if isinstance(c, str):
            return self.read_gdf(c)
        elif isinstance(c, Candidate):
            return self.read_gdf(c.id)

    @property
    def candidates(self) -> list[Candidate]:
        return self.sensitive.candidates

    @property
    def containers(self) -> list[Container]:
        return self.sensitive.containers

    @property
    def containers_all(self) -> list[Container]:
        return self.session.scalars(select(Container)).all()

    @property
    def censuses(self) -> list[Census]:
        return self.sensitive.censuses

    @property
    def censuses_all(self) -> list[Census]:
        return self.session.scalars(select(Census)).all()

    @property
    def addresses(self) -> list[Address]:
        return self.sensitive.addresses

    @property
    def addresses_all(self) -> list[Address]:
        return self.session.scalars(select(Address)).all()

    @property
    def nominee(self) -> Candidate:
        return self.session.get(Candidate, self.sensitive.nominee)

    @classmethod
    def load(cls, name: str, filepath: Path | str) -> "Atlas":
        filepath = Path(filepath).with_suffix(".db")
        atlas = cls(name, filepath)
        atlas.sensitive = atlas.session.get(Sensitive, atlas.name)
        return atlas

    def read_gdf(self, id: str, project: bool = False) -> GeoDataFrame:
        if self.in_memory:
            gdf = self.layers.get(id)
        else:
            gdf = read_file(self._gpkg_path, driver="GPKG", layer=id)

        if project:
            gdf = gdf.to_crs(self.sensitive.crs)
        return gdf

    def _save_gdf(self, gdf: GeoDataFrame, id: str) -> bool:
        if self.in_memory:
            self.layers[id] = gdf.copy(deep=True)
            return True
        else:
            gdf.to_file(self._gpkg_path, driver="GPKG", layer=id)
            return True

    def add_sensitive(self, gdf: GeoDataFrame) -> Sensitive:
        if self.session.get(Sensitive, self.name) is not None:
            raise ValueError("Sensitive layer already exists.")
        id = tools.checksum(gdf)
        nnd = analysis.nnd(gdf)

        self.sensitive = Sensitive(
            name=self.name,
            id=id,
            nnd_min=nnd.min,
            nnd_max=nnd.max,
            nnd_mean=nnd.mean,
            crs=gdf.crs.srs,
        )
        self.session.add(self.sensitive)
        self._save_gdf(gdf, id)
        self.session.commit()
        return self.sensitive

    def add_candidate(
        self,
        gdf: GeoDataFrame,
        params: dict,
        container: Container = None,
        census: Census = None,
        address: Address = None,
    ) -> Candidate:
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
        self._save_gdf(gdf, id)
        self.session.commit()
        return candidate

    def add_container(self, gdf: GeoDataFrame, name: str) -> Container:
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
        self._save_gdf(gdf, id)
        self.session.commit()
        return container

    def add_census(self, gdf: GeoDataFrame, name: str, pop_col: str) -> Census:
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
        self._save_gdf(gdf, id)
        self.session.commit()
        return census

    def add_address(self, gdf: GeoDataFrame, name: str) -> Address:
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
        self._save_gdf(gdf, id)
        self.session.commit()
        return address

    def relate_census(self, name: str) -> Census:
        census = self.get_census(name, other=True)
        self.sensitive.containers.append(census)
        self.session.commit()
        return census

    def relate_container(self, name: str) -> Container:
        container = self.get_container(name, other=True)
        self.sensitive.containers.append(container)
        self.session.commit()
        return container

    def relate_address(self, name: str) -> Address:
        address = self.get_address(name, other=True)
        self.sensitive.containers.append(address)
        self.session.commit()
        return address

    def get_candidate(self, id: str) -> Candidate:
        candidate = self.session.get(Candidate, id)
        if candidate not in self.candidates:
            raise ValueError("Specified candidate is for a different sensitive layer.")
        return candidate

    def get_container(self, name: str, other: bool = False) -> Container:
        container = self.session.get(Container, name)
        if container not in self.containers and other is False:
            raise ValueError(
                "Specified container is for a different sensitive layer. Either set `other=True` or use `relate_container()` first."
            )
        return container

    def get_census(self, name: str, other: bool = False) -> Census:
        """NEEDS TESTS"""
        census = self.session.get(Census, name)
        if census not in self.censuses and other is False:
            raise ValueError(
                "Specified census layer is for a different sensitive layer. Either set `other=True` or use `relate_census()` first."
            )
        return census

    def get_address(self, name: str, other: bool = False) -> Address:
        address = self.session.get(Address, name)
        if address not in self.addresses and other is False:
            raise ValueError(
                "Specified address layer is for a different sensitive layer. Either set `other=True` or use `relate_address()` first."
            )
        return address

    def drop_candidate(self, id: str, delete: bool = False):
        pass

    def drop_container(self, name: str, delete: bool = False):
        pass

    def drop_census(self, name: str, delete: bool = False):
        pass

    def drop_address(self, name: str, delete: bool = False):
        pass

    def mask(self, mask, **kwargs) -> Candidate:
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

    def donut(self, low: float, high: float, **kwargs: dict) -> Candidate:
        return self.mask(Donut, low=low, high=high, **kwargs)

    def donut_i(self, distance_list: list, **kwargs) -> list[Candidate]:
        results = []
        for distance_pair in distance_list:
            low = distance_pair[0]
            high = distance_pair[1]
            if low > high:
                raise ValueError("Low distance value exceeds high distance value.")
            results.append(self.donut(low=low, high=high, **kwargs))
        return results

    def street(self, low: int, high: int, **kwargs) -> Candidate:
        return self.mask(Street, low=low, high=high, **kwargs)

    def voronoi(self, **kwargs) -> Candidate:
        return self.mask(Voronoi, **kwargs)

    def location_swap(self, low: float, high: float, address_name: str, **kwargs) -> Candidate:
        return self.mask(LocationSwap, low=low, high=high, address=address_name, **kwargs)

    def drift(self, candidate_id: Candidate | str) -> Candidate:
        candidate = self.get_candidate(candidate_id)
        candidate.drift = analysis.drift(self.sdf, self.mdf(candidate))
        self.session.commit()
        return candidate

    def estimate_k(
        self, candidate_id: str, census_name: str, return_gdf: bool = False
    ) -> Candidate | GeoDataFrame:
        candidate = self.get_candidate(candidate_id)
        census = self.get_census(census_name)

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
        if return_gdf:
            return kdf
        return candidate

    def calculate_k(
        self, candidate_id: str, address_name: str, return_gdf: bool = False
    ) -> Candidate | GeoDataFrame:
        candidate = self.get_candidate(candidate_id)
        address = self.get_address(address_name)

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
        if return_gdf:
            return kdf
        return Candidate

    def ripley(self):
        pass

    def analyze_all(self, address_name: str = None, census_name: str = None) -> bool:
        K_FIELDS = ["k_min", "k_max", "k_mean", "k_med"]

        for candidate in self.candidates:
            if not candidate.drift:
                self.drift(candidate.id)

            if not all([getattr(candidate, field) for field in K_FIELDS]):
                if address_name:
                    self.calculate_k(candidate.id, address_name)
                elif census_name:
                    self.estimate_k(candidate.id, census_name)
        return True

    def rank(self, metric: str, min_k: int = None, desc: bool = False) -> list:
        if metric not in CANDIDATE_STATS_FIELDS:
            raise ValueError(
                f"Invalid metric name. Valid choices include: {[field for field in CANDIDATE_STATS_FIELDS]}"
            )

        stmt = select(Candidate).where(Candidate.sensitive == self.sensitive)
        stmt = stmt.where(Candidate.k_min >= min_k) if min_k is not None else stmt
        metric_object = getattr(Candidate, metric).desc() if desc else getattr(Candidate, metric)
        stmt = stmt.order_by(metric_object)

        ranked_candidates = self.session.execute(stmt).scalars().all()

        df = DataFrame().from_records([candidate.as_dict for candidate in ranked_candidates])
        metric_col = df.pop(metric)
        df.insert(1, metric, metric_col)
        return df

    def nominate(self, candidate_id: str) -> None:
        candidate = self.get_candidate(candidate_id)

        self.sensitive.nominee = candidate.id
        self.session.commit()
