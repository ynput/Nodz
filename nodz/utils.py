import json
import logging
import typing
from qtpy import QtCore

logging.basicConfig(
    format="[%(name)s]  %(levelname)8s  %(msg)s",
    level=logging.INFO,
)
nlog = logging.getLogger("Nodz")


def set_logging_level(level):
    """
    Set the logging level for Nodz.

    Args:
        level: Logging level (logging.DEBUG, logging.INFO, logging.WARNING,
               logging.ERROR, logging.CRITICAL) or string ('DEBUG', 'INFO',
               'WARNING', 'ERROR', 'CRITICAL')
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper())

    nlog.setLevel(level)
    # Also update the root logger handler level
    for handler in logging.getLogger().handlers:
        handler.setLevel(level)


def get_logging_level():
    """
    Get the current logging level for Nodz.

    Returns:
        int: Current logging level
    """
    return nlog.level


def json_encoder(obj):
    if isinstance(obj, QtCore.QPointF):
        obj = (obj.x(), obj.y())
    elif isinstance(obj, type):
        obj = str(obj)
    elif typing.get_origin(obj):
        obj = str(obj)
    return obj


def json_decoder(d: dict):
    """decode specific fields to avoid code duplication."""

    if "position" in d:
        d["position"] = QtCore.QPointF(*d["position"])
    if "data_type" in d:
        d["data_type"] = str_to_type(d["data_type"])
    return d


def str_to_type(val: typing.Union[str, type]):
    if isinstance(val, str):
        if val.find("<") == 0:
            return eval(str(val.split("'")[1]))
        else:
            return eval(val)
    return val
