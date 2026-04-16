"""Fan-in package: reducer protocol and built-in implementations."""

from squadron.pipeline.intelligence.fan_in.protocol import FanInReducer
from squadron.pipeline.intelligence.fan_in.reducers import (
    _REDUCER_REGISTRY,
    get_reducer,
)

__all__ = ["FanInReducer", "_REDUCER_REGISTRY", "get_reducer"]
