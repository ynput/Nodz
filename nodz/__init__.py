"""
Nodz - A node-based graph editor for Python and Qt.

This package provides a node-based graph editor with a clean MVC architecture.
"""

# Import main modules
from .models import (
    BaseModel,
    NodeModel,
    AttrModel,
    ConnectionModel,
    GraphModel,
)

from .views import (
    ViewSignals,
    NodeView,
    SlotView,
    PlugView,
    SocketView,
    ConnectionView,
)

from .controllers import (
    NodzAPI,
    NodeController,
    ConnectionController,
    GraphController,
    NodzError,
    NodzNodeError,
    NodzNodeNotFoundError,
    NodzNodeExistsError,
    NodzAttributeError,
    NodzAttributeNotFoundError,
    NodzConnectionError,
    NodzIncompatibleTypesError,
)

from .main import NodzView, NodzScene, create_nodz_view

__all__ = [
    "BaseModel",
    "NodeModel",
    "AttrModel",
    "ConnectionModel",
    "GraphModel",
    "ViewSignals",
    "NodeView",
    "SlotView",
    "PlugView",
    "SocketView",
    "ConnectionView",
    "NodzAPI",
    "NodeController",
    "ConnectionController",
    "GraphController",
    "NodzError",
    "NodzNodeError",
    "NodzNodeNotFoundError",
    "NodzNodeExistsError",
    "NodzAttributeError",
    "NodzAttributeNotFoundError",
    "NodzConnectionError",
    "NodzIncompatibleTypesError",
    "NodzView",
    "NodzScene",
    "create_nodz_view",
]

# Version information
__version__ = "2.0.0-beta.1"
__author__ = "Ynput / LeGoffLoic"
__license__ = "MIT"
