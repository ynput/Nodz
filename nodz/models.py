"""
Models module for Nodz.

This module contains the data models for the Nodz graph editor.
Models are responsible only for data storage and validation,
with no UI or rendering logic.
"""

from typing import Any, Dict, List, Optional, Set, Union
from collections import OrderedDict
from dataclasses import dataclass, field
from qtpy import QtCore


class ModelObserver:
    """Interface for objects that observe model changes."""

    def on_model_changed(
        self,
        model: "BaseModel",
        property_name: str,
        old_value: Any,
        new_value: Any,
    ) -> None:
        """Called when a model property changes."""
        pass


class BaseModel:
    """Base class for all models with observer pattern support."""

    def __init__(self) -> None:
        self._observers: List[ModelObserver] = []

    def add_observer(self, observer: ModelObserver) -> None:
        """Add an observer to this model."""
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: ModelObserver) -> None:
        """Remove an observer from this model."""
        if observer in self._observers:
            self._observers.remove(observer)

    def _notify_change(
        self, property_name: str, old_value: Any, new_value: Any
    ) -> None:
        """Notify all observers of a property change."""
        for observer in self._observers:
            observer.on_model_changed(
                self, property_name, old_value, new_value
            )

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
        super().__init__()
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
        old_value = self._attribute
        self._attribute = value
        self._notify_change("attribute", old_value, value)

    @property
    def index(self) -> int:
        return self._index

    @index.setter
    def index(self, value: int) -> None:
        old_value = self._index
        self._index = value
        self._notify_change("index", old_value, value)

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
        from typing import Any as TypingAny, Union, get_origin, get_args

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
        super().__init__()
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
        old_value = self._name
        self._name = value
        self._notify_change("name", old_value, value)

    @property
    def preset(self) -> str:
        return self._preset

    @preset.setter
    def preset(self, value: str) -> None:
        old_value = self._preset
        self._preset = value
        self._notify_change("preset", old_value, value)

    @property
    def alternate(self) -> bool:
        return self._alternate

    @alternate.setter
    def alternate(self, value: bool) -> None:
        old_value = self._alternate
        self._alternate = value
        self._notify_change("alternate", old_value, value)

    @property
    def position(self) -> QtCore.QPointF:
        return self._position

    @position.setter
    def position(self, value: QtCore.QPointF) -> None:
        old_value = self._position
        self._position = value
        self._notify_change("position", old_value, value)

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
        self._notify_change("attributes", None, attr_model)

    def remove_attribute(self, attr_name: str) -> None:
        """Remove an attribute from this node."""
        if attr_name not in self._attributes:
            raise ValueError(f"Attribute '{attr_name}' does not exist")

        attr = self._attributes.pop(attr_name)
        self._notify_change("attributes", attr, None)

    def rename_attribute(self, old_name: str, new_name: str) -> None:
        """Rename an attribute."""
        if old_name not in self._attributes:
            raise ValueError(f"Attribute '{old_name}' does not exist")
        if new_name in self._attributes:
            raise ValueError(f"Attribute '{new_name}' already exists")

        attr = self._attributes.pop(old_name)
        attr.attribute = new_name
        self._attributes[new_name] = attr
        self._notify_change("attributes", old_name, new_name)

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
        self._notify_change("attributes_order", None, None)

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
        super().__init__()
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
        old_value = self._plug_node
        self._plug_node = value
        self._notify_change("plug_node", old_value, value)

    @property
    def plug_attr(self) -> str:
        return self._plug_attr

    @plug_attr.setter
    def plug_attr(self, value: str) -> None:
        old_value = self._plug_attr
        self._plug_attr = value
        self._notify_change("plug_attr", old_value, value)

    @property
    def socket_node(self) -> str:
        return self._socket_node

    @socket_node.setter
    def socket_node(self, value: str) -> None:
        old_value = self._socket_node
        self._socket_node = value
        self._notify_change("socket_node", old_value, value)

    @property
    def socket_attr(self) -> str:
        return self._socket_attr

    @socket_attr.setter
    def socket_attr(self, value: str) -> None:
        old_value = self._socket_attr
        self._socket_attr = value
        self._notify_change("socket_attr", old_value, value)

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
        super().__init__()
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
        self._notify_change("nodes", None, node)

    def remove_node(self, name: str) -> None:
        """Remove a node from the graph."""
        if name not in self._nodes:
            raise ValueError(f"Node '{name}' does not exist")

        node = self._nodes.pop(name)

        # Remove connections associated with this node
        connections_to_remove = []
        for conn in self._connections:
            if conn.plug_node == name or conn.socket_node == name:
                connections_to_remove.append(conn)

        for conn in connections_to_remove:
            self._connections.remove(conn)

        self._notify_change("nodes", node, None)

    def update_node(self, name: str, node: NodeModel) -> None:
        """Update a node in the graph."""
        if name not in self._nodes:
            raise ValueError(f"Node '{name}' does not exist")

        old_node = self._nodes[name]
        self._nodes[name] = node
        self._notify_change("nodes", old_node, node)

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

        self._notify_change("nodes", name, new_name)

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
                f"Plug attribute '{conn.plug_attr}' does not exist on node '{conn.plug_node}'"
            )
        if conn.socket_attr not in socket_node.attributes:
            raise ValueError(
                f"Socket attribute '{conn.socket_attr}' does not exist on node '{conn.socket_node}'"
            )

        self._connections.append(conn)
        self._notify_change("connections", None, conn)

    def remove_connection(self, conn: ConnectionModel) -> None:
        """Remove a connection from the graph."""
        if conn not in self._connections:
            return

        self._connections.remove(conn)
        self._notify_change("connections", conn, None)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the graph model to a dictionary."""
        return {
            "nodes": {
                name: node.to_dict() for name, node in self._nodes.items()
            },
            "connections": [conn.to_dict() for conn in self._connections],
        }
