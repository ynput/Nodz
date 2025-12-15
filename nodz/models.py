"""
Models module for Nodz.

This module contains the data models for the Nodz graph editor.
Models are responsible only for data storage and validation,
with no UI or rendering logic.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
    get_args,
    get_origin,
)

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

        def _get_all_types(type_entry: Any) -> List[Any]:
            from collections.abc import Iterable

            if isinstance(type_entry, Iterable):
                return [
                    orig_type
                    for entry in type_entry
                    for orig_type in _get_all_types(entry)
                ]
            if get_origin(type_entry) is Optional:
                return [None] + _get_all_types(get_args(type_entry))
            if get_origin(type_entry) is Union:
                return _get_all_types(get_args(type_entry))

            return [type_entry]

        def __is_compatible(type1: Any, type2: Any) -> bool:
            if str(type2) == "typing.Any" or str(type1) == "typing.Any":
                # if type1 is Any this means the connection input is very
                # permissive and can contain anything, correct values and/or
                # incorrect values.
                # Connection is fine but it will be at runtime to check this is OK.
                return True

            # List
            if get_origin(type1) is list and get_origin(type1) == get_origin(type2):
                return _is_compatible_types(
                    _get_all_types(get_args(type1)),
                    _get_all_types(get_args(type2)),
                )

            # Dict
            if get_origin(type1) is dict and get_origin(type1) == get_origin(type2):
                keys1, values1 = get_args(type1)
                keys2, values2 = get_args(type2)

                # Keys
                compatible_keys = _is_compatible_types(
                    _get_all_types(keys1),
                    _get_all_types(keys2),
                )

                # Values
                compatible_values = _is_compatible_types(
                    _get_all_types(values1),
                    _get_all_types(values2),
                )

                return compatible_keys and compatible_values

            if isinstance(type1, type) and isinstance(type2, type):
                # FIXME: issubclass may yield undesirable results, like:
                #       issubclass(bool, int) == True
                return issubclass(type1, type2)

            return type1 == type2

        def _is_compatible_types(types1: List[Any], types2: List[Any]) -> bool:
            for type1 in types1:
                for type2 in types2:
                    if __is_compatible(type1, type2):
                        return True
            return False

        return _is_compatible_types(
            _get_all_types(plug_type),
            _get_all_types(socket_type),
        )


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
            raise ValueError(f"Attribute '{attr_model.attribute}' already exists")

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
                for _, v in sorted(self._attributes.items(), key=lambda x: x[1].index)
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
            "attributes": {k: v.to_dict() for k, v in self._attributes.items()},
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


class NodeGroupModel(BaseModel):
    """Model for a node group.

    A node group is a visual container for organizing related nodes.
    Groups are stored as metadata separate from the graph structure.
    A node can only belong to one group at a time.

    Attributes:
        name: Unique name for the group.
        color: RGBA color tuple for the group background.
        members: List of node names in the group.
        rect: Optional explicit bounding rect, or calculated from members.
        kwargs: Additional custom properties.
    """

    def __init__(
        self,
        name: str,
        color: Tuple[int, int, int, int] = (100, 100, 100, 50),
        members: Optional[List[str]] = None,
        rect: Optional[QtCore.QRectF] = None,
        **kwargs,
    ) -> None:
        """Initialize a node group model.

        Args:
            name: Unique name for the group.
            color: RGBA color tuple (default: semi-transparent gray).
            members: List of node names to include in the group.
            rect: Optional explicit bounding rect.
            **kwargs: Additional custom properties.
        """
        self._name = name
        self._color = color
        self._members: List[str] = members or []
        self._rect = rect
        self._kwargs = kwargs or {}

    @property
    def name(self) -> str:
        """Get the group name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set the group name."""
        self._name = value

    @property
    def color(self) -> Tuple[int, int, int, int]:
        """Get the group RGBA color."""
        return self._color

    @color.setter
    def color(self, value: Tuple[int, int, int, int]) -> None:
        """Set the group RGBA color."""
        self._color = value

    @property
    def members(self) -> List[str]:
        """Get the list of member node names."""
        return self._members

    @property
    def rect(self) -> Optional[QtCore.QRectF]:
        """Get the group bounding rect."""
        return self._rect

    @rect.setter
    def rect(self, value: QtCore.QRectF) -> None:
        """Set the group bounding rect."""
        self._rect = value

    @property
    def kwargs(self) -> Dict[str, Any]:
        """Get additional custom properties."""
        return self._kwargs

    def add_member(self, node_name: str) -> None:
        """Add a node to this group.

        Args:
            node_name: Name of the node to add.
        """
        if node_name not in self._members:
            self._members.append(node_name)

    def remove_member(self, node_name: str) -> None:
        """Remove a node from this group.

        Args:
            node_name: Name of the node to remove.
        """
        if node_name in self._members:
            self._members.remove(node_name)

    def contains_node(self, node_name: str) -> bool:
        """Check if a node is in this group.

        Args:
            node_name: Name of the node to check.

        Returns:
            True if the node is in this group, False otherwise.
        """
        return node_name in self._members

    def to_dict(self) -> Dict[str, Any]:
        """Convert the group model to a dictionary.

        Returns:
            Dictionary representation of the group.
        """
        rect_data = None
        if self._rect is not None:
            rect_data = [
                self._rect.x(),
                self._rect.y(),
                self._rect.width(),
                self._rect.height(),
            ]
        return {
            "name": self._name,
            "color": list(self._color),
            "members": self._members.copy(),
            "rect": rect_data,
            "kwargs": self._kwargs,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NodeGroupModel:
        """Create a NodeGroupModel from a dictionary.

        Args:
            data: Dictionary containing group data.

        Returns:
            A new NodeGroupModel instance.
        """
        rect = None
        if data.get("rect") is not None:
            rect_data = data["rect"]
            rect = QtCore.QRectF(rect_data[0], rect_data[1], rect_data[2], rect_data[3])

        color_data = data.get("color", [100, 100, 100, 50])
        color: Tuple[int, int, int, int] = (
            color_data[0],
            color_data[1],
            color_data[2],
            color_data[3],
        )
        kwargs = data.get("kwargs", {})

        return cls(
            name=data["name"],
            color=color,
            members=data.get("members", []),
            rect=rect,
            **kwargs,
        )


class GraphModel(BaseModel):
    """Model for a complete node graph."""

    def __init__(self) -> None:
        self._nodes: Dict[str, NodeModel] = {}
        self._connections: List[ConnectionModel] = []
        self._groups: Dict[str, NodeGroupModel] = {}
        self._node_to_group: Dict[str, str] = {}

    @property
    def nodes(self) -> Dict[str, NodeModel]:
        """Get all nodes in the graph."""
        return self._nodes

    @property
    def connections(self) -> List[ConnectionModel]:
        """Get all connections in the graph."""
        return self._connections

    @property
    def groups(self) -> Dict[str, NodeGroupModel]:
        """Get all groups in the graph."""
        return self._groups

    def add_node(self, node: NodeModel) -> None:
        """Add a node to the graph."""
        if node.name in self._nodes:
            raise ValueError(f"Node '{node.name}' already exists")

        self._nodes[node.name] = node

    def remove_node(self, name: str) -> None:
        """Remove a node from the graph."""
        if name not in self._nodes:
            raise ValueError(f"Node '{name}' does not exist")

        # Remove node from any group it belongs to
        group_name = self._node_to_group.get(name)
        if group_name and group_name in self._groups:
            self._groups[group_name].remove_member(name)
            del self._node_to_group[name]

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

        # Update group membership
        group_name = self._node_to_group.get(name)
        if group_name and group_name in self._groups:
            group = self._groups[group_name]
            group.remove_member(name)
            group.add_member(new_name)
            del self._node_to_group[name]
            self._node_to_group[new_name] = group_name

    def add_connection(self, conn: ConnectionModel) -> None:
        """Add a connection to the graph."""
        if conn in self._connections:
            return

        # Validate connection
        if conn.plug_node not in self._nodes:
            raise ValueError(f"Plug node '{conn.plug_node}' does not exist")
        if conn.socket_node not in self._nodes:
            raise ValueError(f"Socket node '{conn.socket_node}' does not exist")

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

    def add_group(self, group: NodeGroupModel) -> None:
        """Add a group to the graph.

        Args:
            group: The group model to add.

        Raises:
            ValueError: If a group with the same name already exists.
        """
        if group.name in self._groups:
            raise ValueError(f"Group '{group.name}' already exists")

        self._groups[group.name] = group

        # Update reverse lookup for all members
        for member in group.members:
            self._node_to_group[member] = group.name

    def remove_group(self, name: str) -> None:
        """Remove a group from the graph.

        Args:
            name: Name of the group to remove.

        Raises:
            ValueError: If the group does not exist.
        """
        if name not in self._groups:
            raise ValueError(f"Group '{name}' does not exist")

        group = self._groups.pop(name)

        # Clean up reverse lookup
        for member in group.members:
            if self._node_to_group.get(member) == name:
                del self._node_to_group[member]

    def get_group(self, name: str) -> Optional[NodeGroupModel]:
        """Get a group by name.

        Args:
            name: Name of the group.

        Returns:
            The group model, or None if not found.
        """
        return self._groups.get(name)

    def get_groups(self) -> List[NodeGroupModel]:
        """Get all groups in the graph.

        Returns:
            List of all group models.
        """
        return list(self._groups.values())

    def get_group_for_node(self, node_name: str) -> Optional[str]:
        """Get the group name for a node.

        Args:
            node_name: Name of the node.

        Returns:
            Name of the group containing the node, or None if not in a group.
        """
        return self._node_to_group.get(node_name)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the graph model to a dictionary."""
        return {
            "nodes": {name: node.to_dict() for name, node in self._nodes.items()},
            "connections": [conn.to_dict() for conn in self._connections],
            "groups": {name: group.to_dict() for name, group in self._groups.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GraphModel:
        """Create a GraphModel from a dictionary.

        This method loads the graph structure including nodes, connections,
        and groups. Note that node and connection data types are stored as
        serialized type information and need to be reconstructed by the
        controller layer.

        Args:
            data: Dictionary containing graph data with 'nodes',
                'connections', and optionally 'groups' keys.

        Returns:
            A new GraphModel instance with groups loaded.
        """
        graph = cls()

        # Note: Full node/connection loading is handled by GraphController
        # This method focuses on loading group data for deserialization

        # Load groups if present (backward compatible)
        groups_data = data.get("groups", {})
        for group_name, group_data in groups_data.items():
            group = NodeGroupModel.from_dict(group_data)
            graph._groups[group_name] = group
            # Update reverse lookup
            for member in group.members:
                graph._node_to_group[member] = group_name

        return graph
