from dataclasses import dataclass, field
from functools import cached_property
from itertools import zip_longest
from pathlib import Path

from geopandas import GeoDataFrame
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from . import tools
from .candidate import Candidate
from .masks.donut import Donut
from .masks.street import Street
from .messages import *
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

    def __post_init__(self):
        if not self.storage:
            self.storage = Storage(directory=Path(self.directory), name=self.name)

        if isinstance(self.directory, str):
            self.directory = Path(self.directory)

        if isinstance(self.container, GeoDataFrame):
            assert self.container.crs == self.crs
            tools.validate_geom_type(self.container, "Polygon", "MultiPolygon")
            self._container_id = "_".join([self.sid, "container"])
        else:
            self._container_id = "NULL"

        if isinstance(self.population, GeoDataFrame):
            assert self.population.crs == self.crs
            tools.validate_geom_type(self.population, "Polygon", "MultiPolygon", "Point")
            self._population_id = "_".join([self.sid, "population"])
        else:
            self._population_id = "NULL"

        if self.autosave:
            self.save()

    @cached_property
    def sid(self):
        return tools.checksum(self.sensitive)

    @property
    def cids(self):
        return [candidate.cid for candidate in self.candidates]

    @property
    def crs(self):
        return self.sensitive.crs

    def save(self):
        # Save sensitive
        self.storage.save_gdf(self.sensitive, self.name)

        # Save candidates
        for candidate in self.candidates:
            candidate.save()

        # Save container
        if isinstance(self.container, GeoDataFrame):
            self.storage.save_gdf(self.container, self._container_id)

        # Save population
        if isinstance(self.population, GeoDataFrame):
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
    def load(cls, name, directory=Path.cwd()):
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

    def set(self, candidate):
        assert candidate.mdf.crs == self.crs, candidate_crs_mismatch_msg
        assert candidate.cid != self.sid, candidate_identical_to_sensitive_msg
        assert candidate.sid == self.sid, candidate_atlas_sid_mismatch_msg

        if candidate.cid not in self.cids:
            self.candidates.append(candidate)
            if self.autosave:
                candidate.save()
        else:
            print(f"Candidate {candidate.cid} already exists. Skipping...")

    def get(self, index=-1, cid=None) -> Candidate:
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

    def flush_candidates(self):
        for candidate in self.candidates:
            candidate.flush()

    def create_candidate(self, mdf, parameters):
        candidate = Candidate(sid=self.sid, storage=self.storage, mdf=mdf, parameters=parameters)
        self.set(candidate)
        return candidate

    def donut(self, low, high, **kwargs):
        if isinstance(low, (int, float)) and isinstance(high, (int, float)):
            mdf, parameters = Donut(
                self.sensitive, low, high, container=self.container, **kwargs
            ).run()
            return self.create_candidate(mdf, parameters)

        elif isinstance(low, list) and isinstance(high, list):
            distances = self._zip_longest_autofill(low, high)
            for low_val, high_val in distances:
                mdf, parameters = Donut(
                    self.sensitive, low_val, high_val, container=self.container, **kwargs
                ).run()
                self.create_candidate(mdf, parameters)
            return list(self.candidates)[(0 - len(distances)) :]

        else:
            raise ValueError(
                "Low and high arguments must both be numbers (int, float) or lists of numbers."
            )

    def street(self, low, high, **kwargs):
        if isinstance(low, list) and isinstance(high, list):
            distances = self._zip_longest_autofill(low, high)
            for low_val, high_val in distances:
                mdf, parameters = Street(self.sensitive, low_val, high_val, **kwargs).run()
                self.create_candidate(mdf, parameters)
            return list(self.candidates)[(0 - len(distances)) :]

        elif isinstance(low, (int, float)) and isinstance(high, (int, float)):
            mdf, parameters = Street(self.sensitive, low, high, **kwargs).run()
            return self.create_candidate(mdf, parameters)

        else:
            raise ValueError(
                "Low and high arguments must both be numbers (int, float) or lists of numbers."
            )

    @staticmethod
    def _zip_longest_autofill(a, b):
        fill = max(b) if len(b) < len(a) else max(a)
        return list(zip_longest(a, b, fillvalue=fill))
