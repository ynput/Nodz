"""
Models module for Nodz.

This module contains the data models for the Nodz graph editor.
Models are responsible only for data storage and validation,
with no UI or rendering logic.
"""

from typing import Any, Dict, List, Optional, Union, get_origin, get_args
from collections import OrderedDict
from qtpy import QtCore


class BaseModel:
    """Base class for all models."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert the model to a dictionary."""
        raise NotImplementedError("Subclasses must implement to_dict()")


class AttrModel(BaseModel):
    """Model for a node attribute."""

    def __init__(
        self,
        attribute: str,
        index: int,
        preset: str,
        plug: bool,
        socket: bool,
        data_type: type,
        plug_max_connections: int = -1,
        socket_max_connections: int = -1,
        **kwargs,
    ) -> None:
        self._attribute = attribute
        self._index = index
        self._preset = preset
        self._plug = plug
        self._socket = socket
        self._data_type = data_type
        self._plug_max_connections = plug_max_connections
        self._socket_max_connections = socket_max_connections
        self._kwargs = kwargs or {}

    @property
    def attribute(self) -> str:
        return self._attribute

    @attribute.setter
    def attribute(self, value: str) -> None:
        self._attribute = value

    @property
    def index(self) -> int:
        return self._index

    @index.setter
    def index(self, value: int) -> None:
        self._index = value

    @property
    def preset(self) -> str:
        return self._preset

    @property
    def plug(self) -> bool:
        return self._plug

    @property
    def socket(self) -> bool:
        return self._socket

    @property
    def data_type(self) -> type:
        return self._data_type

    @property
    def plug_max_connections(self) -> int:
        return self._plug_max_connections

    @property
    def socket_max_connections(self) -> int:
        return self._socket_max_connections

    @property
    def kwargs(self) -> Dict[str, Any]:
        return self._kwargs

    def to_dict(self) -> Dict[str, Any]:
        """Convert the attribute model to a dictionary."""
        return {
            "attribute": self._attribute,
            "index": self._index,
            "preset": self._preset,
            "plug": self._plug,
            "socket": self._socket,
            "data_type": self._data_type,
            "plug_max_connections": self._plug_max_connections,
            "socket_max_connections": self._socket_max_connections,
            "kwargs": self._kwargs,
        }

    @staticmethod
    def is_compatible_type(plug_type: Any, socket_type: Any) -> bool:
        """
        Check if the source type is compatible with the target type.
        This method supports subclasses, Any and Union types.

        Args:
            plug_type: The source data type.
            socket_type: The destination data type.
        Returns:
            bool: True if compatible, False otherwise.
        """

        if str(plug_type) == "typing.Any" or str(socket_type) == "typing.Any":
            return True
        elif get_origin(plug_type) is Union:
            if get_origin(socket_type) is not Union:
                return any(
                    [
                        issubclass(src, socket_type)
                        for src in get_args(plug_type)
                    ]
                )
            else:
                return any(
                    [
                        issubclass(src, get_args(socket_type))
                        for src in get_args(plug_type)
                    ]
                )
        elif get_origin(socket_type) is Union:
            return issubclass(plug_type, get_args(socket_type))
        elif isinstance(plug_type, type) and isinstance(socket_type, type):
            # FIXME: issubclass may yield undesirable results, like:
            #       issubclass(bool, int) == True
            return issubclass(plug_type, socket_type)
        return False


class NodeModel(BaseModel):
    """Model for a node."""

    def __init__(
        self,
        name: str,
        preset: str,
        alternate: bool = True,
        position: Optional[QtCore.QPointF] = None,
        **kwargs,
    ) -> None:
        self._name = name
        self._preset = preset
        self._alternate = alternate
        self._position = position or QtCore.QPointF(-1.0, -1.0)
        self._attributes: OrderedDict[str, AttrModel] = OrderedDict()
        self._kwargs = kwargs or {}

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    @property
    def preset(self) -> str:
        return self._preset

    @preset.setter
    def preset(self, value: str) -> None:
        self._preset = value

    @property
    def alternate(self) -> bool:
        return self._alternate

    @alternate.setter
    def alternate(self, value: bool) -> None:
        self._alternate = value

    @property
    def position(self) -> QtCore.QPointF:
        return self._position

    @position.setter
    def position(self, value: QtCore.QPointF) -> None:
        self._position = value

    @property
    def attributes(self) -> OrderedDict[str, AttrModel]:
        return self._attributes

    @property
    def kwargs(self) -> Dict[str, Any]:
        return self._kwargs

    def add_attribute(self, attr_model: AttrModel) -> None:
        """Add an attribute to this node."""
        if attr_model.attribute in self._attributes:
            raise ValueError(
                f"Attribute '{attr_model.attribute}' already exists"
            )

        self._attributes[attr_model.attribute] = attr_model

    def remove_attribute(self, attr_name: str) -> None:
        """Remove an attribute from this node."""
        if attr_name not in self._attributes:
            raise ValueError(f"Attribute '{attr_name}' does not exist")

        self._attributes.pop(attr_name)

    def rename_attribute(self, old_name: str, new_name: str) -> None:
        """Rename an attribute."""
        if old_name not in self._attributes:
            raise ValueError(f"Attribute '{old_name}' does not exist")
        if new_name in self._attributes:
            raise ValueError(f"Attribute '{new_name}' already exists")

        attr = self._attributes.pop(old_name)
        attr.attribute = new_name
        self._attributes[new_name] = attr

    def sort_attributes(self) -> None:
        """Sort attributes based on their index."""
        self._attributes = OrderedDict(
            {
                v.attribute: v
                for _, v in sorted(
                    self._attributes.items(), key=lambda x: x[1].index
                )
            }
        )

    def valid_position(self) -> bool:
        """Check if the position is valid."""
        return self._position.x() >= 0.0 and self._position.y() >= 0.0

    def attribute_name_from_index(self, idx: int) -> str:
        """Get attribute name from index."""
        return list(self._attributes.keys())[idx]

    def to_dict(self) -> Dict[str, Any]:
        """Convert the node model to a dictionary."""
        return {
            "name": self._name,
            "preset": self._preset,
            "alternate": self._alternate,
            "position": self._position,
            "attributes": {
                k: v.to_dict() for k, v in self._attributes.items()
            },
            "kwargs": self._kwargs,
        }


class ConnectionModel(BaseModel):
    """Model for a connection between two node attributes."""

    def __init__(
        self,
        plug_node: str = "",
        plug_attr: str = "",
        socket_node: str = "",
        socket_attr: str = "",
        **kwargs,
    ) -> None:
        self._plug_node = plug_node
        self._plug_attr = plug_attr
        self._socket_node = socket_node
        self._socket_attr = socket_attr
        self._kwargs = kwargs or {}

    @property
    def plug_node(self) -> str:
        return self._plug_node

    @plug_node.setter
    def plug_node(self, value: str) -> None:
        self._plug_node = value

    @property
    def plug_attr(self) -> str:
        return self._plug_attr

    @plug_attr.setter
    def plug_attr(self, value: str) -> None:
        self._plug_attr = value

    @property
    def socket_node(self) -> str:
        return self._socket_node

    @socket_node.setter
    def socket_node(self, value: str) -> None:
        self._socket_node = value

    @property
    def socket_attr(self) -> str:
        return self._socket_attr

    @socket_attr.setter
    def socket_attr(self, value: str) -> None:
        self._socket_attr = value

    @property
    def kwargs(self) -> Dict[str, Any]:
        return self._kwargs

    def to_dict(self) -> Dict[str, Any]:
        """Convert the connection model to a dictionary."""
        return {
            "plug_node": self._plug_node,
            "plug_attr": self._plug_attr,
            "socket_node": self._socket_node,
            "socket_attr": self._socket_attr,
            "kwargs": self._kwargs,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ConnectionModel):
            return False
        return (
            self._plug_node == other._plug_node
            and self._plug_attr == other._plug_attr
            and self._socket_node == other._socket_node
            and self._socket_attr == other._socket_attr
        )


class GraphModel(BaseModel):
    """Model for a complete node graph."""

    def __init__(self) -> None:
        self._nodes: Dict[str, NodeModel] = {}
        self._connections: List[ConnectionModel] = []

    @property
    def nodes(self) -> Dict[str, NodeModel]:
        return self._nodes

    @property
    def connections(self) -> List[ConnectionModel]:
        return self._connections

    def add_node(self, node: NodeModel) -> None:
        """Add a node to the graph."""
        if node.name in self._nodes:
            raise ValueError(f"Node '{node.name}' already exists")

        self._nodes[node.name] = node

    def remove_node(self, name: str) -> None:
        """Remove a node from the graph."""
        if name not in self._nodes:
            raise ValueError(f"Node '{name}' does not exist")

        self._nodes.pop(name)

    def update_node(self, name: str, node: NodeModel) -> None:
        """Update a node in the graph."""
        if name not in self._nodes:
            raise ValueError(f"Node '{name}' does not exist")

        self._nodes[name] = node

    def rename_node(self, name: str, new_name: str) -> None:
        """Rename a node in the graph."""
        if name not in self._nodes:
            raise ValueError(f"Node '{name}' does not exist")
        if new_name in self._nodes:
            raise ValueError(f"Node '{new_name}' already exists")

        node = self._nodes.pop(name)
        node.name = new_name
        self._nodes[new_name] = node

        # Update connections
        for conn in self._connections:
            if conn.plug_node == name:
                conn.plug_node = new_name
            if conn.socket_node == name:
                conn.socket_node = new_name

    def add_connection(self, conn: ConnectionModel) -> None:
        """Add a connection to the graph."""
        if conn in self._connections:
            return

        # Validate connection
        if conn.plug_node not in self._nodes:
            raise ValueError(f"Plug node '{conn.plug_node}' does not exist")
        if conn.socket_node not in self._nodes:
            raise ValueError(
                f"Socket node '{conn.socket_node}' does not exist"
            )

        plug_node = self._nodes[conn.plug_node]
        socket_node = self._nodes[conn.socket_node]

        if conn.plug_attr not in plug_node.attributes:
            raise ValueError(
                f"Plug attribute '{conn.plug_attr}' does not exist on node "
                f"'{conn.plug_node}'"
            )
        if conn.socket_attr not in socket_node.attributes:
            raise ValueError(
                f"Socket attribute '{conn.socket_attr}' does not exist on "
                f"node '{conn.socket_node}'"
            )

        self._connections.append(conn)

    def remove_connection(self, conn: ConnectionModel) -> None:
        """Remove a connection from the graph."""
        if conn not in self._connections:
            return

        self._connections.remove(conn)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the graph model to a dictionary."""
        return {
            "nodes": {
                name: node.to_dict() for name, node in self._nodes.items()
            },
            "connections": [conn.to_dict() for conn in self._connections],
        }
