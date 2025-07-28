from dataclasses import dataclass, field, asdict
from collections import OrderedDict
from typing import Any, List, Union, get_origin, get_args
from qtpy import QtCore
from .utils import str_to_type, nlog

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

    def __post_init__(self):
        self.data_type = str_to_type(self.data_type)

    @staticmethod
    def is_compatible_type(plug_type: Any, socket_type: Any) -> bool:
        """
        Check if the source type is compatible with the target type.
        This method supports subclasses, Any and Union types.

        Args:
            plug_type (Any): The source data type.
            socket_type (Any): The destination data type.
        Returns:
            bool: True if compatible, False otherwise.
        """
        status = False
        if str(plug_type) == "typing.Any" or str(socket_type) == "typing.Any":
            status = True
        elif get_origin(plug_type) is Union:
            if get_origin(socket_type) is not Union:
                status = any(
                    [
                        issubclass(src, socket_type)
                        for src in get_args(plug_type)
                    ]
                )
            else:
                status = any(
                    [
                        issubclass(src, get_args(socket_type))
                        for src in get_args(plug_type)
                    ]
                )
        elif get_origin(socket_type) is Union:
            status = issubclass(plug_type, get_args(socket_type))
        elif isinstance(plug_type, type) and isinstance(socket_type, type):
            status = issubclass(plug_type, socket_type)
        nlog.debug(
            f"  >>  is_compatible_type:  source_type: {plug_type} -> "
            f"target_type: {socket_type} = {status}"
        )
        return status


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
        self.nodes[new_name] = self.nodes.pop(name)
        self.nodes[new_name].name = new_name

    def add_connection(self, con: ConnectionModel):
        if con not in self.connections:
            self.connections.append(con)


# Note: ModelEdit, ModelEntity, and NodzAdapter classes have been removed
# as they are no longer needed with the new MVC architecture and unified API.
# The functionality has been replaced by the controllers and models in the new architecture.
