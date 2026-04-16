"""Fan-in package: reducer protocol and built-in implementations."""

from squadron.pipeline.intelligence.fan_in.protocol import FanInReducer
from squadron.pipeline.intelligence.fan_in.reducers import get_reducer

__all__ = ["FanInReducer", "get_reducer"]
