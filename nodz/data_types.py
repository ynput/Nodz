from dataclasses import dataclass, field, asdict
from collections import OrderedDict
from typing import Any, List
from enum import Enum
from copy import copy
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
    data_type: type
    plug_max_connections: int = -1
    socket_max_connections: int = -1
    kwargs: dict = field(default_factory=dict)


@dataclass
class NodeModel(BaseModel):
    """Serializable data model for a node."""

    name: str
    preset: str
    alternate: bool = True
    position: QtCore.QPointF = field(
        default_factory=lambda: QtCore.QPointF(-1.0, -1.0)
    )
    attributes: OrderedDict[str, AttrModel] = field(
        default_factory=OrderedDict
    )
    kwargs: dict = field(default_factory=dict)

    def valid_position(self):
        return self.position.x() >= 0.0 and self.position.y() >= 0.0

    def attribute_name_from_index(self, idx) -> str:
        return list(self.attributes.keys())[idx]

    def sort_attributes(self):
        # Sort attibutes based on their index
        # Make sure attr names == dict key.
        self.attributes = OrderedDict(
            {
                v.attribute: v
                for _, v in sorted(
                    self.attributes.items(), key=lambda x: x[1].index
                )
            }
        )


@dataclass
class ConnectionModel(BaseModel):
    """Serializable data model for a connection."""

    plug_node: str = ""
    plug_attr: str = ""
    socket_node: str = ""
    socket_attr: str = ""
    kwargs: dict = field(default_factory=dict)


@dataclass
class GraphModel(BaseModel):
    """Serializable data model for a node graph."""

    nodes: dict[str, NodeModel] = field(default_factory=dict)
    connections: List[ConnectionModel] = field(default_factory=list)

    def add_node(self, node: NodeModel):
        self.nodes[node.name] = node

    def remove_node(self, name: str):
        del self.nodes[name]

    def update_node(self, name: str, node: NodeModel):
        self.nodes[name] = node

    def rename_node(self, name, new_name):
        self.nodes[new_name] = copy(self.nodes[name])
        del self.nodes[name]
        self.nodes[new_name].name = new_name


# =============================================================================
# Data Adapter
# =============================================================================


class ModelEdit(Enum):
    Create = 0
    Update = 1
    Delete = 2


class ModelEntity(Enum):
    Attr = 0
    Node = 1
    Connection = 2
    Graph = 3


class NodzAdapter:
    def to_attr_model(self, data: Any) -> AttrModel:
        if isinstance(data, AttrModel):
            return data
        raise NotImplementedError()

    def to_node_model(self, data: Any) -> NodeModel:
        if isinstance(data, NodeModel):
            return data
        raise NotImplementedError()

    def to_connecttion_model(self, data: Any) -> ConnectionModel:
        if isinstance(data, ConnectionModel):
            return data
        raise NotImplementedError()

    def to_graph_model(self, data: Any) -> GraphModel:
        if isinstance(data, GraphModel):
            return data
        raise NotImplementedError()

    def from_attr_model(self, data: AttrModel) -> Any:
        if isinstance(data, AttrModel):
            return data
        raise NotImplementedError()

    def from_node_model(self, data: NodeModel) -> Any:
        if isinstance(data, NodeModel):
            return data
        raise NotImplementedError()

    def from_connecttion_model(self, data: ConnectionModel) -> Any:
        if isinstance(data, ConnectionModel):
            return data
        raise NotImplementedError()

    def from_graph_model(self, data: GraphModel) -> Any:
        if isinstance(data, GraphModel):
            return data
        raise NotImplementedError()
