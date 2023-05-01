from dataclasses import dataclass
from . import analysis
from .atlas import Atlas


@dataclass
class Analyst:
    atlas: Atlas

    def summarize_k(self):
        if self.atlas.population is not None:
            for candidate in self.atlas.candidates:
                candidate.kdf = analysis.estimate_k(self.atlas.sdf, candidate.get().mdf)
                k_values = analysis.summarize_k(candidate.kdf)
                candidate.k_min = k_values.k_min
                candidate.k_max = k_values.k_max
                candidate.k_mean = k_values.k_mean
                candidate.k_med = k_values.k_med


# Analyst uses the Atlas which stores Sensitive objects, Context objects, and Candidate objects"
