from dataclasses import dataclass, field
from getpass import getuser
from itertools import zip_longest
from pathlib import Path

import pandas as pd
from geopandas import GeoDataFrame
from pointpats.distance_statistics import KtestResult
from pyproj.crs.crs import CRS
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from .. import analysis
from .. import messages as msg
from .. import tools
from ..candidate import Candidate
from ..masks import Donut, LocationSwap, Street, Voronoi
from .reference import Reference
from .sensitive import Sensitive
from .storage import AtlasMeta, CandidateMeta, Storage


@dataclass
class Atlas:
    name: str
    input: GeoDataFrame = field(repr=False)
    container: GeoDataFrame = None
    population: GeoDataFrame = None
    pop_col: str = "pop"
    sensitive: Sensitive = None
    candidates: list[Candidate] = field(default_factory=list[Candidate])
    reference: dict[Reference] = field(default_factory=dict[Reference])
    directory: Path = field(default_factory=lambda: Path.cwd())
    author: str = field(default_factory=lambda: getuser())
    storage: Storage = None
    autosave: bool = True
    autoflush: bool = True
    nominee: str = None

    def __post_init__(self) -> None:
        if not self.storage:
            self.storage = Storage(directory=Path(self.directory), name=self.name)

        if isinstance(self.directory, str):
            self.directory = Path(self.directory)

        if not self.sensitive:
            self.sensitive = Sensitive(sdf=self.input, storage=self.storage)
        del self.input

        if self.container is not None:
            tools._validate_crs(self.crs, self.container.crs)
            tools._validate_geom_type(self.container, "Polygon", "MultiPolygon")
            self._container_id = "_".join([self.sid, "container"])
        else:
            self._container_id = "NULL"

        if self.population is not None:
            assert self.population.crs == self.crs
            tools._validate_geom_type(self.population, "Polygon", "MultiPolygon", "Point")
            self._population_id = "_".join([self.sid, "population"])
        else:
            self._population_id = "NULL"

        if self.autosave:
            self.save()

    @property
    def sid(self) -> str:
        return self.sensitive.sid

    @property
    def cids(self) -> list[str]:
        return [candidate.cid for candidate in self.candidates]

    @property
    def crs(self) -> CRS:
        return self.sensitive.sdf.crs

    def save(self) -> None:
        # Save sensitive
        self.sensitive.save()

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
                sid=self.sensitive.sid,
                author=self.author,
                autosave=self.autosave,
                autoflush=self.autoflush,
                container_id=self._container_id,
                population_id=self._population_id,
                pop_col=self.pop_col,
                nominee=self.nominee,
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
        sensitive = Sensitive.load(atlas_meta.sid, storage=storage)

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
            population = storage.read_gdf(atlas_meta.population_id)
        else:
            population = None

        return cls(
            name=name,
            input=sensitive.sdf,
            sensitive=sensitive,
            candidates=candidates,
            directory=directory,
            container=container,
            population=population,
            pop_col=atlas_meta.pop_col,
            author=atlas_meta.author,
            autosave=atlas_meta.autosave,
            autoflush=atlas_meta.autoflush,
            nominee=atlas_meta.nominee,
        )

    def set(self, candidate: Candidate) -> None:
        assert candidate.mdf.crs == self.crs, msg.candidate_crs_mismatch_msg
        assert candidate.cid != self.sid, msg.candidate_identical_to_sensitive_msg
        assert candidate.sid == self.sid, msg.candidate_atlas_sid_mismatch_msg

        if candidate.cid not in self.cids:
            self.candidates.append(candidate)
            if self.autosave:
                candidate.save()
            if self.autoflush:
                candidate.flush()
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

    def flush(self) -> None:
        for candidate in self.candidates:
            candidate.flush()

    def create_candidate(self, mdf: GeoDataFrame, parameters: dict) -> Candidate:
        candidate = Candidate(
            sid=self.sid,
            storage=self.storage,
            mdf=mdf,
            parameters=parameters,
        )
        self.set(candidate)
        return candidate

    def nominate(self, cid: str):
        self.nominee = cid

    def get_nominee(self):
        return self.get(cid=self.nominee)

    def mask(self, mask, **kwargs) -> Candidate:
        m = mask(gdf=self.sensitive.sdf, **kwargs)
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
        return self.mask_i(Donut, low_list, high_list, container=self.container, **kwargs)

    def street(self, low: float, high: float, **kwargs) -> Candidate:
        return self.mask(Street, low=low, high=high, **kwargs)

    def street_i(self, low_list: list, high_list: list, **kwargs) -> list[Candidate]:
        return self.mask_i(Street, low_list, high_list, **kwargs)

    def locationswap(self, low: float, high: float, **kwargs) -> Candidate:
        return self.mask(LocationSwap, low=low, high=high, addresses=self.population, **kwargs)

    def locationswap_i(self, low_list: list, high_list: list, **kwargs) -> list[Candidate]:
        return self.mask_i(LocationSwap, low_list, high_list, addresses=self.population, **kwargs)

    def voronoi(self, **kwargs) -> Candidate:
        return self.mask(Voronoi, **kwargs)

    def benchmark_custom_mask(self, CustomMask):
        for candidate in self.candidates:
            self.ripleys_k(candidate)

    def ripleys_k(
        self,
        candidate: Candidate = None,
        steps: int = 10,
        max_dist: float = None,
        graph: bool = False,
        subtitle: str = None,
    ) -> KtestResult:
        candidate = self.get() if not candidate else candidate.get()
        max_dist = analysis.ripleys_rot(self.sensitive.sdf) if not max_dist else max_dist

        sensitive_rk = self.sensitive.ripleys_k(steps=steps, max_dist=max_dist)

        candidate_rk = analysis.ripleys_k(
            candidate.mdf, max_dist=max_dist, min_dist=(max_dist / steps), steps=steps
        )
        candidate.ripley_rmse = analysis.ripley_rmse(candidate_rk, sensitive_rk)

        if graph:
            subtitle = candidate.cid if subtitle is None else subtitle
            analysis.graph_ripleyresults(candidate_rk, sensitive_rk, subtitle).savefig(
                f"{self.directory}/rk_{candidate.cid}.png"
            )

        return candidate_rk

    def ripleys_all(self, *args, **kwargs) -> bool:
        for candidate in self.candidates:
            kwargs["candidate"] = candidate
            self.ripleys_k(*args, **kwargs)
        return

    def estimate_k(self, candidate: Candidate = None) -> GeoDataFrame:
        candidate = self.get() if candidate is None else candidate.get()

        candidate_k = analysis.estimate_k(
            sensitive_gdf=self.sensitive.sdf,
            candidate_gdf=candidate.mdf,
            population_gdf=self.population,
            pop_col=self.pop_col,
        )

        return candidate_k

    def summarize_k(self, candidate: Candidate = None):
        candidate = self.get() if candidate is None else candidate.get()

        candidate_k = self.estimate_k(candidate)

        k_summary = analysis.summarize_k(candidate_k)

        candidate.k_min = k_summary.k_min
        candidate.k_max = k_summary.k_max
        candidate.k_med = k_summary.k_med
        candidate.k_mean = k_summary.k_mean

        return k_summary

    def summarize_k_all(self):
        for candidate in self.candidates:
            self.summarize_k(candidate)
        return

    def drift(self, candidate: Candidate = None):
        candidate = self.get() if candidate is None else candidate.get()
        candidate.drift = analysis.drift(candidate.mdf, self.sensitive.sdf)
        return candidate.drift

    def rank(self, metric, min_k=None, desc=False):
        candidates = [
            candidate
            for candidate in self.candidates
            if hasattr(candidate, metric) and getattr(candidate, metric) is not None
        ]

        candidates_sorted = sorted(candidates, key=lambda x: getattr(x, metric), reverse=desc)

        if min_k:
            candidates_sorted = [
                candidate
                for candidate in candidates_sorted
                if candidate.k_min and candidate.k_min >= min_k
            ]

        df = pd.DataFrame()
        df["CID"] = [candidate.cid for candidate in candidates_sorted]
        df[metric] = [getattr(candidate, metric) for candidate in candidates_sorted]

        if min_k is not None:
            k_col = [candidate.k_min for candidate in candidates_sorted]
            df["min_k"] = k_col

        return df

    @staticmethod
    def _zip_longest_autofill(a: any, b: any) -> list:
        fill = max(b) if len(b) < len(a) else max(a)
        return list(zip_longest(a, b, fillvalue=fill))
