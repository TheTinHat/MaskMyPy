from dataclasses import dataclass, field
from functools import cached_property
from itertools import zip_longest
from pathlib import Path

from geopandas import GeoDataFrame
from pyproj.crs.crs import CRS
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from . import messages as msg
from . import tools
from .candidate import Candidate
from .masks import Donut, Street, Voronoi
from .storage import AtlasMeta, CandidateMeta, Storage


@dataclass
class Atlas:
    name: str
    sensitive: GeoDataFrame
    directory: Path = field(default_factory=lambda: Path.cwd())
    container: GeoDataFrame = None
    population: GeoDataFrame = None
    candidates: list[Candidate] = field(default_factory=list[Candidate])
    storage: Storage = None
    autosave: bool = True
    autoflush: bool = True

    def __post_init__(self) -> None:
        if not self.storage:
            self.storage = Storage(directory=Path(self.directory), name=self.name)

        if isinstance(self.directory, str):
            self.directory = Path(self.directory)

        if self.container is not None:
            tools.validate_crs(self.crs, self.container.crs)
            tools.validate_geom_type(self.container, "Polygon", "MultiPolygon")
            self._container_id = "_".join([self.sid, "container"])
        else:
            self._container_id = "NULL"

        if self.population is not None:
            assert self.population.crs == self.crs
            tools.validate_geom_type(self.population, "Polygon", "MultiPolygon", "Point")
            self._population_id = "_".join([self.sid, "population"])
        else:
            self._population_id = "NULL"

        if self.autosave:
            self.save()

    @cached_property
    def sid(self) -> str:
        return tools.checksum(self.sensitive)

    @property
    def cids(self) -> list[str]:
        return [candidate.cid for candidate in self.candidates]

    @property
    def crs(self) -> CRS:
        return self.sensitive.crs

    def save(self) -> None:
        # Save sensitive
        self.storage.save_gdf(self.sensitive, self.name)

        # Save candidates
        for candidate in self.candidates:
            candidate.save()

        # Save container
        if self.container is not None:
            self.storage.save_gdf(self.container, self._container_id)

        # Save population
        if self.population is not None:
            self.storage.save_gdf(self.population, self._population_id)

        # Save metadata to database
        self.storage.session.execute(
            insert(AtlasMeta)
            .values(
                name=self.name,
                sid=self.sid,
                autosave=self.autosave,
                autoflush=self.autoflush,
                container_id=self._container_id,
                population_id=self._population_id,
            )
            .on_conflict_do_nothing()
        )
        self.storage.session.commit()

    @classmethod
    def load(cls, name: str, directory: Path = Path.cwd()) -> "Atlas":
        storage = Storage(name=name, directory=directory)

        # Load atlas metadata
        atlas_meta = (
            storage.session.execute(select(AtlasMeta).filter_by(name=name)).scalars().first()
        )

        # Load sensitive
        sensitive = storage.read_gdf(name)

        # Load candidates
        candidate_list = (
            storage.session.execute(
                select(CandidateMeta)
                .filter_by(sid=atlas_meta.sid)
                .order_by(CandidateMeta.timestamp)
            )
            .scalars()
            .all()
        )
        candidates = []
        for candidate in candidate_list:
            candidates.append(Candidate.load(candidate.cid, storage))

        # Load container
        if atlas_meta.container_id != "NULL":
            container = storage.read_gdf(atlas_meta.container_id)
        else:
            container = None

        # Load population
        if atlas_meta.population_id != "NULL":
            population = storage.read_gdf(atlas_meta.container_id)
        else:
            population = None

        return cls(
            name=name,
            sensitive=sensitive,
            candidates=candidates,
            directory=directory,
            container=container,
            population=population,
            autosave=atlas_meta.autosave,
            autoflush=atlas_meta.autoflush,
        )

    def set(self, candidate: Candidate) -> None:
        assert candidate.mdf.crs == self.crs, msg.candidate_crs_mismatch_msg
        assert candidate.cid != self.sid, msg.candidate_identical_to_sensitive_msg
        assert candidate.sid == self.sid, msg.candidate_atlas_sid_mismatch_msg

        if candidate.cid not in self.cids:
            self.candidates.append(candidate)
            if self.autosave:
                candidate.save()
        else:
            print(f"Candidate {candidate.cid} already exists. Skipping...")

    def get(self, index: int = -1, cid: str = None) -> Candidate:
        if cid is not None:
            candidate = [c for c in self.candidates if c.cid == cid]
            if len(candidate) == 1:
                return candidate[0].get()
            elif len(candidate) == 0:
                raise ValueError("Could not find candidate")
            elif len(candidate) > 1:
                raise RuntimeError("Found multiple candidates with same CID")
        else:
            return self.candidates[index].get()

    def flush_candidates(self) -> None:
        for candidate in self.candidates:
            candidate.flush()

    def create_candidate(self, mdf: GeoDataFrame, parameters: dict) -> Candidate:
        candidate = Candidate(sid=self.sid, storage=self.storage, mdf=mdf, parameters=parameters)
        self.set(candidate)
        return candidate

    def mask(self, mask, **kwargs) -> Candidate:
        m = mask(gdf=self.sensitive, **kwargs)
        mdf = m.run()
        params = m.params
        return self.create_candidate(mdf, params)

    def mask_i(self, mask, low_list: list, high_list: list, **kwargs) -> list[Candidate]:
        values = self._zip_longest_autofill(low_list, high_list)
        for low_val, high_val in values:
            self.mask(mask, low=low_val, high=high_val, **kwargs)
        return list(self.candidates)[(0 - len(values)) :]

    def donut(self, low: float, high: float, **kwargs) -> Candidate:
        return self.mask(Donut, low=low, high=high, container=self.container, **kwargs)

    def donut_i(self, low_list: list, high_list: list, **kwargs) -> list[Candidate]:
        return self.mask_i(Donut, low_list, high_list, **kwargs)

    def street(self, low: float, high: float, **kwargs) -> Candidate:
        return self.mask(Street, low=low, high=high, **kwargs)

    def street_i(self, low_list: list, high_list: list, **kwargs) -> list[Candidate]:
        return self.mask_i(Street, low_list, high_list, **kwargs)

    def voronoi(self, **kwargs) -> Candidate:
        return self.mask(Voronoi, **kwargs)

    @staticmethod
    def _zip_longest_autofill(a: any, b: any) -> list:
        fill = max(b) if len(b) < len(a) else max(a)
        return list(zip_longest(a, b, fillvalue=fill))
