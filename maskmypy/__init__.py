import warnings

from shapely.errors import ShapelyDeprecationWarning

from .donut import Donut, Donut_MaxK, Donut_Multiply
from .street import Street

warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)

name = "maskmypy"
