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
    ModelObserver,
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
    NodeError,
    NodeNotFoundError,
    NodeExistsError,
    AttributeError,
    AttributeNotFoundError,
    ConnectionError,
    IncompatibleTypesError,
)

from .main import NodzView, NodzScene, create_nodz_view

# Version information
__version__ = "2.0.0-beta.1"
__author__ = "Ynput"
__license__ = "MIT"
