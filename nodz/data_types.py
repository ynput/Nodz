from dataclasses import dataclass, field, fields, asdict
from typing import Tuple
from qtpy import QtCore

# =============================================================================
# Data Models
# =============================================================================


@dataclass
class BaseModel:
    """Common additional methods for all models."""

    def to_dict(self):
        return asdict(self)


@dataclass
class AttrModel(BaseModel):
    """Serializable data model for a node attribute."""
    attribute: str
    index: int
    preset: str
    plug: bool
    socket: bool
    data_type: str
    plug_max_connections: int
    socket_max_connections: int
    kwargs: dict = field(default_factory=dict)


@dataclass
class NodeModel(BaseModel):
    """Serializable data model for a node."""
    name: str
    alternate: bool
    preset: str
    position: QtCore.QPointF = field(
        default_factory=lambda: QtCore.QPointF(-1.0, -1.0)
    )
    attributes: list[AttrModel] = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)

    def valid_position(self):
        return self.position.x() >= 0.0 and self.position.y() >= 0.0


@dataclass
class ConnectionModel(BaseModel):
    """Serializable data model for a connection."""
    plug_node: str = ""
    plug_attr: str = ""
    socket_node: str = ""
    socket_attr: str = ""
    kwargs: dict = field(default_factory=dict)
