"""PLPR core: Persian license plate reading on ONNX Runtime."""
from .engine import Engine, PlateRead
from .plate import PlateNumber, parse_codes
from .tracking import PlateTracker

__all__ = ["Engine", "PlateNumber", "PlateRead", "PlateTracker", "parse_codes"]
__version__ = "2.0.0"
