from .donut import Donut, Donut_MaxK, Donut_Multiply
from .street import Street
from shapely.errors import ShapelyDeprecationWarning
import warnings
warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)

name = 'maskmypy'