from abc import ABC, abstractmethod
from dataclasses import dataclass

from geopandas import GeoDataFrame


@dataclass
class AbstractMask(ABC):
    gdf: GeoDataFrame

    @abstractmethod
    def run(self) -> GeoDataFrame:
        pass
