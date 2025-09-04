"""
Controllers module for Nodz.

This module contains the controller classes for the Nodz graph editor.
Controllers are responsible for coordinating between models and views,
handling user interactions, and implementing business logic.
"""

import os
import json
from typing import Any, Dict, List, Optional, Tuple, Union
import functools
from qtpy import QtCore, QtGui, QtWidgets

from .models import (
    NodeModel,
    AttrModel,
    ConnectionModel,
    GraphModel,
)
from .views import (
    NodeView,
    PlugView,
    SocketView,
    ConnectionView,
    ViewSignals,
)
from .utils import (
    json_decoder,
    json_encoder,
    nlog,
    set_logging_level,
    get_logging_level,
)


class NodzError(Exception):
    """Base class for all Nodz exceptions."""

    pass


class NodeError(NodzError):
    """Base class for node-related errors."""

    pass


class NodeNotFoundError(NodeError):
    """Raised when a node is not found."""

    def __init__(self, node_name: str):
        self.node_name = node_name
        super().__init__(f"Node '{node_name}' not found")


class NodeExistsError(NodeError):
    """Raised when attempting to create a node that already exists."""

    def __init__(self, node_name: str):
        self.node_name = node_name
        super().__init__(f"Node '{node_name}' already exists")


class AttributeError(NodzError):
    """Base class for attribute-related errors."""

    pass


class AttributeNotFoundError(AttributeError):
    """Raised when an attribute is not found."""

    def __init__(self, node_name: str, attr_name: str):
        self.node_name = node_name
        self.attr_name = attr_name
        super().__init__(
            f"Attribute '{attr_name}' not found on node '{node_name}'"
        )


class ConnectionError(NodzError):
    """Base class for connection-related errors."""

    pass


class IncompatibleTypesError(ConnectionError):
    """Raised when attempting to connect incompatible attribute types."""

    def __init__(self, source_type: Any, target_type: Any):
        self.source_type = source_type
        self.target_type = target_type
        super().__init__(
            "Cannot connect incompatible types: "
            f"{source_type} -> {target_type}"
        )


class SelfConnectionError(ConnectionError):
    """Raised when attempting to connect a node to itself."""

    def __init__(self, node_name: str):
        self.node_name = node_name
        super().__init__(f"Cannot connect node '{node_name}' to itself")


class MaxConnectionsExceededError(ConnectionError):
    """Raised when attempting to exceed maximum connections for an attribute."""

    def __init__(self, node_name: str, attr_name: str, max_connections: int):
        self.node_name = node_name
        self.attr_name = attr_name
        self.max_connections = max_connections
        super().__init__(
            f"Maximum connections ({max_connections}) exceeded for "
            f"attribute '{attr_name}' on node '{node_name}'"
        )


class DuplicateConnectionError(ConnectionError):
    """Raised when attempting to create a connection that already exists."""

    def __init__(
        self,
        source_node: str,
        source_attr: str,
        target_node: str,
        target_attr: str,
    ):
        self.source_node = source_node
        self.source_attr = source_attr
        self.target_node = target_node
        self.target_attr = target_attr
        super().__init__(
            f"Connection already exists: {source_node}.{source_attr} -> "
            f"{target_node}.{target_attr}"
        )


def validate_node_exists(func):
    """Decorator to validate that a node exists."""

    @functools.wraps(func)
    def wrapper(self, node_name, *args, **kwargs):
        if node_name not in self.graph_model.nodes:
            raise NodeNotFoundError(node_name)
        return func(self, node_name, *args, **kwargs)

    return wrapper


def validate_attribute_exists(func):
    """Decorator to validate that an attribute exists on a node."""

    @functools.wraps(func)
    def wrapper(self, node_name, attr_name, *args, **kwargs):
        if node_name not in self.graph_model.nodes:
            raise NodeNotFoundError(node_name)
        node = self.graph_model.nodes[node_name]
        if attr_name not in node.attributes:
            raise AttributeNotFoundError(node_name, attr_name)
        return func(self, node_name, attr_name, *args, **kwargs)

    return wrapper


class BaseController:
    """Base class for all controllers."""

    def __init__(
        self,
        graph_model: GraphModel,
        scene: QtWidgets.QGraphicsScene,
        config: Dict[str, Any],
        signals: ViewSignals,
    ):
        """Initialize the controller."""
        self.graph_model = graph_model
        self.scene = scene
        self.config = config
        self.signals = signals


class NodeController(BaseController):
    """Controller for node operations."""

    def __init__(
        self,
        graph_model: GraphModel,
        scene: QtWidgets.QGraphicsScene,
        config: Dict[str, Any],
        signals: ViewSignals,
    ):
        """Initialize the node controller."""
        super().__init__(graph_model, scene, config, signals)

        self._updating_node_position = False

        # Connect signals
        self.signals.node_moved.connect(self.on_node_moved)
        self.signals.node_selected.connect(self.on_node_selected)
        self.signals.node_double_clicked.connect(self.on_node_double_clicked)

    def create_node(
        self,
        name: str,
        preset: str = "node_default",
        position: Optional[QtCore.QPointF] = None,
        alternate: bool = True,
        **kwargs,
    ) -> NodeModel:
        """Create a new node."""
        # Validate
        if name in self.graph_model.nodes:
            raise NodeExistsError(name)

        # Create model
        node_model = NodeModel(name, preset, alternate, position, **kwargs)

        # Add to graph model
        self.graph_model.add_node(node_model)

        # Create view
        node_view = NodeView(node_model, self.config, self.signals)
        self.scene.addItem(node_view)

        # Position the view
        if position:
            node_view.setPos(position)
        else:
            # Center in view if no position specified
            view = self.scene.views()[0] if self.scene.views() else None
            if view:
                center = view.mapToScene(view.viewport().rect().center())
                node_view.setPos(center)

        return node_model

    @validate_node_exists
    def delete_node(self, node_name: str) -> None:
        """Delete a node."""
        # Find the node view
        node_view = self._find_node_view(node_name)
        if node_view:
            # Remove from scene
            self.scene.removeItem(node_view)

        # Remove from model
        self.graph_model.remove_node(node_name)

        # Emit node deleted signal
        self.signals.node_deleted.emit(node_name)

    @validate_node_exists
    def rename_node(self, node_name: str, new_name: str) -> str:
        """Rename a node."""
        if new_name in self.graph_model.nodes:
            raise NodeExistsError(new_name)

        # Rename in model
        self.graph_model.rename_node(node_name, new_name)

        return new_name

    @validate_node_exists
    def create_attribute(
        self,
        node_name: str,
        attr_name: str,
        index: int = -1,
        preset: str = "attr_default",
        plug: bool = True,
        socket: bool = True,
        data_type: Any = None,
        plug_max_connections: int = -1,
        socket_max_connections: int = 1,
        **kwargs,
    ) -> None:
        """Create an attribute on a node."""
        # Get the node model
        node_model = self.graph_model.nodes[node_name]

        # Validate
        if attr_name in node_model.attributes:
            raise ValueError(
                f"Attribute '{attr_name}' already exists on node '{node_name}'"
            )

        # Create attribute model
        attr_model = AttrModel(
            attr_name,
            index,
            preset,
            plug,
            socket,
            data_type,
            plug_max_connections,
            socket_max_connections,
            **kwargs,
        )

        # Add to node model
        node_model.add_attribute(attr_model)

    @validate_attribute_exists
    def delete_attribute(self, node_name: str, attr_name: str) -> None:
        """Delete an attribute from a node."""
        # Get the node model
        node_model = self.graph_model.nodes[node_name]

        # Remove from node model
        node_model.remove_attribute(attr_name)

    @validate_attribute_exists
    def edit_attribute(
        self,
        node_name: str,
        attr_name: str,
        new_name: Optional[str] = None,
        new_index: Optional[int] = None,
    ) -> None:
        """Edit an attribute."""
        # Get the node model
        node_model = self.graph_model.nodes[node_name]

        # Rename if needed
        if new_name and new_name != attr_name:
            if new_name in node_model.attributes:
                raise ValueError(
                    f"Attribute '{new_name}' already exists on node "
                    f"'{node_name}'"
                )
            node_model.rename_attribute(attr_name, new_name)
            attr_name = new_name

        # Change index if needed
        if new_index is not None:
            attr_model = node_model.attributes[attr_name]
            attr_model.index = new_index
            node_model.sort_attributes()

    def on_node_moved(self, node_name: str, position: QtCore.QPointF) -> None:
        """Handle node moved signal."""
        if self._updating_node_position:
            return

        try:
            self._updating_node_position = True

            # Update model position directly without triggering observers
            if node_name in self.graph_model.nodes:
                node_model = self.graph_model.nodes[node_name]
                # Directly set the internal position without triggering
                # notifications
                node_model._position = position

            # Don't emit the signal again to prevent our handler from being
            # called. The original method would emit the signal, causing our
            # handler to run

        finally:
            self._updating_node_position = False

    def on_node_selected(self, node_name: str, selected: bool) -> None:
        """Handle node selected signal."""
        # This could emit a higher-level signal or update application state
        pass

    def on_node_double_clicked(self, node_name: str) -> None:
        """Handle node double clicked signal."""
        # This could open a node editor or perform other actions
        pass

    def _find_node_view(self, node_name: str) -> Optional[NodeView]:
        """Find a node view by name."""
        for item in self.scene.items():
            if isinstance(item, NodeView) and item.model.name == node_name:
                return item
        return None


class ConnectionController(BaseController):
    """Controller for connection operations."""

    def __init__(
        self,
        graph_model: GraphModel,
        scene: QtWidgets.QGraphicsScene,
        config: Dict[str, Any],
        signals: ViewSignals,
    ):
        """Initialize the connection controller."""
        super().__init__(graph_model, scene, config, signals)

        # Connection being drawn
        self.temp_connection: Optional[ConnectionView] = None

        # colors
        self.non_connectable_color = QtGui.QColor(
            *self.config["non_connectable_color"]
        )

        # Connect signals
        self.signals.attr_connection_started.connect(
            self.on_connection_started
        )
        self.signals.attr_connection_dragged.connect(
            self.on_connection_dragged
        )
        self.signals.connection_created.connect(self.on_connection_created)
        self.signals.connection_deleted.connect(self.on_connection_deleted)
        self.signals.node_moved.connect(self.on_node_moved)
        self.signals.node_deleted.connect(self.on_node_deleted)

    def create_connection(
        self,
        source_node: str,
        source_attr: str,
        target_node: str,
        target_attr: str,
    ) -> ConnectionModel:
        """Create a connection between two node attributes."""
        # Validate nodes exist
        if source_node not in self.graph_model.nodes:
            raise NodeNotFoundError(source_node)
        if target_node not in self.graph_model.nodes:
            raise NodeNotFoundError(target_node)

        # Validate no self-connection
        if source_node == target_node:
            raise SelfConnectionError(source_node)

        # Validate attributes exist
        source_node_model = self.graph_model.nodes[source_node]
        target_node_model = self.graph_model.nodes[target_node]

        if source_attr not in source_node_model.attributes:
            raise AttributeNotFoundError(source_node, source_attr)
        if target_attr not in target_node_model.attributes:
            raise AttributeNotFoundError(target_node, target_attr)

        # Get attribute models
        source_attr_model = source_node_model.attributes[source_attr]
        target_attr_model = target_node_model.attributes[target_attr]

        # Validate plug/socket compatibility
        if not source_attr_model.plug:
            raise ConnectionError(
                f"Attribute '{source_attr}' on node '{source_node}' "
                "is not a plug"
            )
        if not target_attr_model.socket:
            raise ConnectionError(
                f"Attribute '{target_attr}' on node '{target_node}' "
                "is not a socket"
            )

        # Validate data type compatibility
        if not AttrModel.is_compatible_type(
            source_attr_model.data_type, target_attr_model.data_type
        ):
            raise IncompatibleTypesError(
                source_attr_model.data_type, target_attr_model.data_type
            )

        # Check for duplicate connection
        for existing_conn in self.graph_model.connections:
            if (
                existing_conn.plug_node == source_node
                and existing_conn.plug_attr == source_attr
                and existing_conn.socket_node == target_node
                and existing_conn.socket_attr == target_attr
            ):
                raise DuplicateConnectionError(
                    source_node, source_attr, target_node, target_attr
                )

        # Check maximum connections for source (plug)
        if source_attr_model.plug_max_connections > 0:
            existing_plug_connections = sum(
                1
                for conn in self.graph_model.connections
                if conn.plug_node == source_node
                and conn.plug_attr == source_attr
            )
            if (
                existing_plug_connections
                >= source_attr_model.plug_max_connections
            ):
                raise MaxConnectionsExceededError(
                    source_node,
                    source_attr,
                    source_attr_model.plug_max_connections,
                )

        # Check maximum connections for target (socket)
        if target_attr_model.socket_max_connections > 0:
            existing_socket_connections = sum(
                1
                for conn in self.graph_model.connections
                if conn.socket_node == target_node
                and conn.socket_attr == target_attr
            )
            if (
                existing_socket_connections
                >= target_attr_model.socket_max_connections
            ):
                raise MaxConnectionsExceededError(
                    target_node,
                    target_attr,
                    target_attr_model.socket_max_connections,
                )

        # Create connection model
        connection_model = ConnectionModel(
            source_node, source_attr, target_node, target_attr
        )

        # Add to graph model
        self.graph_model.add_connection(connection_model)

        # Create connection view
        source_view = self._find_plug_view(source_node, source_attr)
        target_view = self._find_socket_view(target_node, target_attr)

        if source_view and target_view:
            connection_view = ConnectionView(
                connection_model,
                source_view.center(),
                target_view.center(),
                self.config,
                self.signals,
            )
            if source_view.slot_drawer_enabled:
                connection_view.set_data_type(source_view.model.data_type)
            self.scene.addItem(connection_view)

        return connection_model

    def delete_connection(
        self,
        source_node: str,
        source_attr: str,
        target_node: str,
        target_attr: str,
    ) -> None:
        """Delete a connection."""
        # Find the connection model
        connection_model = None
        for conn in self.graph_model.connections:
            if (
                conn.plug_node == source_node
                and conn.plug_attr == source_attr
                and conn.socket_node == target_node
                and conn.socket_attr == target_attr
            ):
                connection_model = conn
                break

        if not connection_model:
            return

        # Find the connection view
        connection_view = self._find_connection_view(connection_model)
        if connection_view:
            # Remove from scene
            self.scene.removeItem(connection_view)

        # Remove from model
        self.graph_model.remove_connection(connection_model)

    def on_connection_started(
        self, node_name: str, attr_name: str, position: QtCore.QPoint
    ) -> None:
        """Handle connection started signal."""
        # Import SlotView to access the static variable
        from .views import SlotView

        # Clear any previous snapped target slot
        SlotView.snapped_target_slot = None

        # Create a temporary connection for visual feedback
        if self.temp_connection:
            self.scene.removeItem(self.temp_connection)
            self.temp_connection = None

        # Determine if the source is a plug or a socket
        source_node = self.graph_model.nodes.get(node_name)
        if not source_node or attr_name not in source_node.attributes:
            return

        source_attr = source_node.attributes[attr_name]

        # Find the source slot view to determine its type
        source_slot = None
        if source_attr.plug:
            source_slot = self._find_plug_view(node_name, attr_name)
            # Create a temporary connection model with source as plug
            temp_model = ConnectionModel(node_name, attr_name, "", "")
        elif source_attr.socket:
            source_slot = self._find_socket_view(node_name, attr_name)
            # Create a temporary connection model with source as socket
            temp_model = ConnectionModel("", "", node_name, attr_name)
        else:
            return  # Not a plug or socket

        if not source_slot:
            return

        # Create a temporary connection view
        self.temp_connection = ConnectionView(
            temp_model,
            QtCore.QPointF(position),
            QtCore.QPointF(position),
            self.config,
            self.signals,
        )
        if source_slot.slot_drawer_enabled:
            self.temp_connection.set_data_type(source_slot.model.data_type)
        self.scene.addItem(self.temp_connection)

    def on_connection_dragged(self, position: QtCore.QPoint) -> None:
        """Handle connection dragged signal."""
        if self.temp_connection:
            # Update visual feedback for compatible/incompatible slots
            self._update_slot_compatibility_feedback(position)

            # Find the closest compatible slot
            closest_slot = self._find_closest_compatible_slot(position)

            # Import SlotView to access the static variable
            from .views import SlotView

            if closest_slot:
                # Snap to the closest slot and store it for connection
                # acceptance
                self.temp_connection.target_point = closest_slot.center()
                SlotView.snapped_target_slot = closest_slot
            else:
                # Update the temporary connection end point to the mouse
                # position
                self.temp_connection.target_point = QtCore.QPointF(position)
                SlotView.snapped_target_slot = None

            self.temp_connection.update_path()

    def _update_slot_compatibility_feedback(
        self, position: QtCore.QPoint
    ) -> None:
        """Update visual feedback for compatible/incompatible slots."""
        if not self.temp_connection or not isinstance(
            self.temp_connection, ConnectionView
        ):
            return

        # Get the source slot type (plug or socket)
        source_is_plug = self.temp_connection.model.plug_attr != ""
        source_node_name = (
            self.temp_connection.model.plug_node
            if source_is_plug
            else self.temp_connection.model.socket_node
        )
        source_attr_name = (
            self.temp_connection.model.plug_attr
            if source_is_plug
            else self.temp_connection.model.socket_attr
        )

        # Get the source node and attribute
        source_node = self.graph_model.nodes.get(source_node_name)
        if not source_node or source_attr_name not in source_node.attributes:
            return

        source_attr = source_node.attributes[source_attr_name]
        source_type = source_attr.data_type

        # Reset all slots to their original appearance
        self._reset_all_slots_appearance()

        # Find nodes near the mouse cursor
        hovered_node = None
        hovered_node_view = None

        # Create a larger area around the mouse cursor for node detection
        detection_radius = 100  # pixels
        detection_rect = QtCore.QRectF(
            position.x() - detection_radius,
            position.y() - detection_radius,
            detection_radius * 2,
            detection_radius * 2,
        )

        # Get all items in the detection area
        items_in_area = self.scene.items(detection_rect)

        # Find the closest node in the detection area
        min_distance = float("inf")
        for item in items_in_area:
            if isinstance(item, NodeView):
                # Calculate distance to node center
                node_center = item.pos() + QtCore.QPointF(
                    item.boundingRect().width() / 2,
                    item.boundingRect().height() / 2,
                )
                distance = (node_center - position).manhattanLength()

                if distance < min_distance:
                    min_distance = distance
                    hovered_node_view = item
                    hovered_node = self.graph_model.nodes.get(item.model.name)

        # If we found a hovered node, gray out all incompatible slots on it
        if hovered_node and hovered_node_view:
            # Gray out all slots of the same type as the source
            for item in self.scene.items():
                # Skip items that aren't slots or aren't on the hovered node
                if not isinstance(item, (PlugView, SocketView)):
                    continue

                try:
                    parent_node = item.parent_node_view()
                    if parent_node != hovered_node_view:
                        continue
                except (AttributeError, TypeError):
                    continue

                # Gray out slots of the same type as the source (plug/plug or
                # socket/socket)
                if (source_is_plug and isinstance(item, PlugView)) or (
                    not source_is_plug and isinstance(item, SocketView)
                ):
                    item.brush.setColor(self.non_connectable_color)
                    item.update()
                    continue

                # For slots of the opposite type, check data type
                # compatibility - PlugView and SocketView should always have
                # model and attribute
                if not hasattr(item.model, "attribute"):
                    continue

                attr_name = item.model.attribute
                if attr_name not in hovered_node.attributes:
                    continue

                target_attr = hovered_node.attributes[attr_name]
                target_type = target_attr.data_type

                # Check data type compatibility
                if source_is_plug:
                    is_compatible = AttrModel.is_compatible_type(
                        source_type, target_type
                    )
                else:
                    is_compatible = AttrModel.is_compatible_type(
                        target_type, source_type
                    )

                # Gray out incompatible slots
                if not is_compatible:
                    item.brush.setColor(self.non_connectable_color)
                    item.update()

    def _reset_all_slots_appearance(self) -> None:
        """Reset all slots to their original appearance."""
        for item in self.scene.items():
            if isinstance(item, (PlugView, SocketView)):
                item._create_style()  # Reset to original style
                item.update()

    def _find_closest_compatible_slot(
        self, position: QtCore.QPoint
    ) -> Optional[Union[PlugView, SocketView]]:
        """Find the closest compatible slot to the given position."""
        if not self.temp_connection or not isinstance(
            self.temp_connection, ConnectionView
        ):
            return None

        # Get the source slot type (plug or socket)
        source_is_plug = self.temp_connection.model.plug_attr != ""

        # Get all items at the position with some tolerance
        tolerance = 20  # pixels
        rect = QtCore.QRect(
            position.x() - tolerance,
            position.y() - tolerance,
            tolerance * 2,
            tolerance * 2,
        )
        items = self.scene.items(rect)

        # Filter for compatible slots
        compatible_slots = []
        for item in items:
            # Check if it's a slot view
            if not isinstance(item, (PlugView, SocketView)):
                continue

            # Check if it's the opposite type of the source slot
            if (source_is_plug and not isinstance(item, SocketView)) or (
                not source_is_plug and not isinstance(item, PlugView)
            ):
                continue

            # Check if it's not on the same node
            try:
                parent_node = item.parent_node_view()
                if not isinstance(parent_node, NodeView):
                    continue
            except (AttributeError, TypeError):
                continue

            source_node = (
                self.temp_connection.model.plug_node
                if source_is_plug
                else self.temp_connection.model.socket_node
            )
            if parent_node.model.name == source_node:
                continue

            # Add to compatible slots
            compatible_slots.append(item)

        if not compatible_slots:
            return None

        # Find the closest slot
        closest_slot = None
        min_distance = float("inf")
        for slot in compatible_slots:
            distance = (slot.center() - position).manhattanLength()

            if distance < min_distance:
                min_distance = distance
                closest_slot = slot

        return closest_slot

    def on_connection_created(
        self,
        source_node: str,
        source_attr: str,
        target_node: str,
        target_attr: str,
    ) -> None:
        """Handle connection created signal."""
        # Import SlotView to access the static variable
        from .views import SlotView

        # Reset all slots to their original appearance
        self._reset_all_slots_appearance()

        # Clear snapped target slot
        SlotView.snapped_target_slot = None

        # Remove temporary connection
        if self.temp_connection:
            self.scene.removeItem(self.temp_connection)
            self.temp_connection = None

        # If target_node or target_attr is empty, it means the connection
        # is invalid. In this case, we just remove the temporary connection
        # and don't create a new one.
        if not target_node or not target_attr:
            return

        # Create the actual connection
        try:
            self.create_connection(
                source_node, source_attr, target_node, target_attr
            )
        except NodzError as e:
            # Handle error (could show a message to the user)
            nlog.error(f"Error creating connection: {e}")

    def on_connection_deleted(
        self,
        source_node: str,
        source_attr: str,
        target_node: str,
        target_attr: str,
    ) -> None:
        """Handle connection deleted signal."""
        # Reset all slots to their original appearance
        self._reset_all_slots_appearance()

        self.delete_connection(
            source_node, source_attr, target_node, target_attr
        )

    def on_node_moved(self, node_name: str, position: QtCore.QPointF) -> None:
        """Update connections when a node is moved."""
        # Find all connections that involve this node
        connections_to_update = []
        for connection in self.graph_model.connections:
            if (
                connection.plug_node == node_name
                or connection.socket_node == node_name
            ):
                connections_to_update.append(connection)

        # Update all affected connections
        for connection in connections_to_update:
            connection_view = self._find_connection_view(connection)
            if connection_view:
                # Update source and target points
                source_view = self._find_plug_view(
                    connection.plug_node, connection.plug_attr
                )
                target_view = self._find_socket_view(
                    connection.socket_node, connection.socket_attr
                )

                if source_view and target_view:
                    connection_view.source_point = source_view.center()
                    connection_view.target_point = target_view.center()
                    connection_view.update_path()

    def on_node_deleted(self, node_name: str) -> None:
        """Handle node deleted signal."""
        # Find all connections that involve this node
        connections_to_remove = []
        for conn in self.graph_model.connections:
            if conn.plug_node == node_name or conn.socket_node == node_name:
                connections_to_remove.append(conn)

        # Remove each connection properly (both model and view)
        for conn in connections_to_remove:
            # Find the connection view
            connection_view = self._find_connection_view(conn)
            if connection_view:
                # Remove from scene
                self.scene.removeItem(connection_view)

            # Remove from model
            self.graph_model.remove_connection(conn)

    def _find_plug_view(
        self, node_name: str, attr_name: str
    ) -> Optional[PlugView]:
        """Find a plug view by node and attribute name."""
        node_view = self._find_node_view(node_name)
        if isinstance(node_view, NodeView) and attr_name in node_view.plugs:
            return node_view.plugs[attr_name]
        return None

    def _find_socket_view(
        self, node_name: str, attr_name: str
    ) -> Optional[SocketView]:
        """Find a socket view by node and attribute name."""
        node_view = self._find_node_view(node_name)
        if isinstance(node_view, NodeView) and attr_name in node_view.sockets:
            return node_view.sockets[attr_name]
        return None

    def _find_node_view(self, node_name: str) -> Optional[NodeView]:
        """Find a node view by name."""
        for item in self.scene.items():
            if isinstance(item, NodeView) and item.model.name == node_name:
                return item
        return None

    def _find_connection_view(
        self, connection_model: ConnectionModel
    ) -> Optional[ConnectionView]:
        """Find a connection view by model."""
        for item in self.scene.items():
            # Check if it's a connection view by checking its class name
            if (
                isinstance(item, ConnectionView)
                and item.model.plug_node == connection_model.plug_node
                and item.model.plug_attr == connection_model.plug_attr
                and item.model.socket_node == connection_model.socket_node
                and item.model.socket_attr == connection_model.socket_attr
            ):
                return item
        return None


class GraphController(BaseController):
    """Controller for graph operations."""

    def __init__(
        self,
        graph_model: GraphModel,
        scene: QtWidgets.QGraphicsScene,
        config: Dict[str, Any],
        signals: ViewSignals,
    ):
        """Initialize the graph controller."""
        super().__init__(graph_model, scene, config, signals)

    def save_graph(self, file_path: str) -> None:
        """Save the graph to a file."""
        # Convert graph model to dictionary
        graph_dict = self.graph_model.to_dict()

        # Save to file
        with open(file_path, "w") as f:
            json.dump(graph_dict, f, indent=4, default=json_encoder)

    def load_graph(self, file_path: str) -> None:
        """Load a graph from a file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Load from file
        with open(file_path, "r") as f:
            graph_dict = json.load(f, object_hook=json_decoder)

        # Clear current graph
        self.clear_graph()

        # Create nodes
        for node_name, node_data in graph_dict["nodes"].items():
            # Create node model
            node_model = NodeModel(
                node_name,
                node_data["preset"],
                node_data["alternate"],
                QtCore.QPointF(
                    node_data["position"][0], node_data["position"][1]
                ),
                **node_data["kwargs"],
            )

            # Add attributes
            for attr_name, attr_data in node_data["attributes"].items():
                attr_model = AttrModel(
                    attr_name,
                    attr_data["index"],
                    attr_data["preset"],
                    attr_data["plug"],
                    attr_data["socket"],
                    attr_data["data_type"],
                    attr_data["plug_max_connections"],
                    attr_data["socket_max_connections"],
                    **attr_data["kwargs"],
                )
                node_model.attributes[attr_name] = attr_model

            # Add to graph model
            self.graph_model.add_node(node_model)

            # Create view
            node_view = NodeView(node_model, self.config, self.signals)
            self.scene.addItem(node_view)
            node_view.setPos(node_model.position)

        # Create connections
        for conn_data in graph_dict["connections"]:
            # Create connection model
            connection_model = ConnectionModel(
                conn_data["plug_node"],
                conn_data["plug_attr"],
                conn_data["socket_node"],
                conn_data["socket_attr"],
                **conn_data["kwargs"],
            )

            # Add to graph model
            self.graph_model.add_connection(connection_model)

            # Create connection view
            source_view = self._find_plug_view(
                connection_model.plug_node, connection_model.plug_attr
            )
            target_view = self._find_socket_view(
                connection_model.socket_node, connection_model.socket_attr
            )

            if source_view and target_view:
                connection_view = ConnectionView(
                    connection_model,
                    source_view.center(),
                    target_view.center(),
                    self.config,
                    self.signals,
                )
                self.scene.addItem(connection_view)

    def clear_graph(self) -> None:
        """Clear the graph."""
        # Clear scene
        self.scene.clear()

        # Clear model data while keeping the same instance
        self.graph_model.nodes.clear()
        self.graph_model.connections.clear()

    def evaluate_graph(self) -> List[Tuple[str, str]]:
        """Evaluate the graph and return a list of connections."""
        result = []
        for conn in self.graph_model.connections:
            source = f"{conn.plug_node}.{conn.plug_attr}"
            target = f"{conn.socket_node}.{conn.socket_attr}"
            result.append((source, target))
        return result

    def _find_connection_view(
        self, connection_model: ConnectionModel
    ) -> Optional[QtWidgets.QGraphicsItem]:
        """Find a connection view by model."""
        for item in self.scene.items():
            # Check if it's a connection view by checking its class name
            if (
                isinstance(item, ConnectionView)
                and item.model.plug_node == connection_model.plug_node
                and item.model.plug_attr == connection_model.plug_attr
                and item.model.socket_node == connection_model.socket_node
                and item.model.socket_attr == connection_model.socket_attr
            ):
                return item
        return None

    def _find_plug_view(
        self, node_name: str, attr_name: str
    ) -> Optional[PlugView]:
        """Find a plug view by node and attribute name."""
        node_view = self._find_node_view(node_name)
        if isinstance(node_view, NodeView) and attr_name in node_view.plugs:
            return node_view.plugs[attr_name]
        return None

    def _find_socket_view(
        self, node_name: str, attr_name: str
    ) -> Optional[SocketView]:
        """Find a socket view by node and attribute name."""
        node_view = self._find_node_view(node_name)
        if isinstance(node_view, NodeView) and attr_name in node_view.sockets:
            return node_view.sockets[attr_name]
        return None

    def _find_node_view(self, node_name: str) -> Optional[NodeView]:
        """Find a node view by name."""
        for item in self.scene.items():
            if isinstance(item, NodeView) and item.model.name == node_name:
                return item
        return None


class NodzAPI:
    """
    Unified API facade for Nodz.

    This class provides a single, consistent interface for all Nodz operations,
    hiding the complexity of the underlying MVC architecture from the user.
    It delegates operations to the appropriate controllers while maintaining
    a clean and intuitive API.
    """

    def __init__(
        self, scene: QtWidgets.QGraphicsScene, config: Dict[str, Any]
    ):
        """
        Initialize the API.

        Args:
            scene: The QGraphicsScene to operate on
            config: Configuration dictionary containing styling and behavior
                    settings.
        """
        # Create models
        self.graph_model = GraphModel()

        # Create signals
        self.signals = ViewSignals()

        # Create controllers
        self.node_controller = NodeController(
            self.graph_model, scene, config, self.signals
        )
        self.connection_controller = ConnectionController(
            self.graph_model, scene, config, self.signals
        )
        self.graph_controller = GraphController(
            self.graph_model, scene, config, self.signals
        )

    # Node operations
    def create_node(
        self,
        name: str,
        preset: str = "node_default",
        position: Optional[QtCore.QPointF] = None,
        alternate: bool = True,
        **kwargs,
    ) -> str:
        """
        Create a new node in the graph.

        Args:
            name: Unique name for the node
            preset: Visual preset to use (must exist in config)
            position: Position in scene coordinates, or None for
                      auto-positioning.
            alternate: Whether to use alternating row colors for attributes
            **kwargs: Additional properties to store with the node

        Returns:
            The name of the created node

        Raises:
            NodeExistsError: If a node with the same name already exists
        """
        node_model = self.node_controller.create_node(
            name, preset, position, alternate, **kwargs
        )
        return node_model.name

    def delete_node(self, node_name: str) -> None:
        """
        Delete a node from the graph.

        Args:
            node_name: Name of the node to delete

        Raises:
            NodeNotFoundError: If the node doesn't exist
        """
        self.node_controller.delete_node(node_name)

    def rename_node(self, node_name: str, new_name: str) -> str:
        """
        Rename an existing node.

        Args:
            node_name: Current name of the node
            new_name: New name for the node

        Returns:
            The new name of the node

        Raises:
            NodeNotFoundError: If the node doesn't exist
            NodeExistsError: If a node with the new name already exists
        """
        return self.node_controller.rename_node(node_name, new_name)

    def edit_node(self, node_name: str, new_name: str) -> str:
        """
        Edit a node (alias for rename_node for backward compatibility).

        Args:
            node_name: Current name of the node
            new_name: New name for the node

        Returns:
            The new name of the node
        """
        return self.rename_node(node_name, new_name)

    def get_node_names(self) -> List[str]:
        """
        Get a list of all node names in the graph.

        Returns:
            List of node names
        """
        return list(self.graph_model.nodes.keys())

    def node_exists(self, node_name: str) -> bool:
        """
        Check if a node exists in the graph.

        Args:
            node_name: Name of the node to check

        Returns:
            True if the node exists, False otherwise
        """
        return node_name in self.graph_model.nodes

    def get_node_position(self, node_name: str) -> QtCore.QPointF:
        """
        Get the position of a node.

        Args:
            node_name: Name of the node

        Returns:
            Position of the node in scene coordinates

        Raises:
            NodeNotFoundError: If the node doesn't exist
        """
        if node_name not in self.graph_model.nodes:
            raise NodeNotFoundError(node_name)
        return self.graph_model.nodes[node_name].position

    def set_node_position(
        self, node_name: str, position: QtCore.QPointF
    ) -> None:
        """
        Set the position of a node.

        Args:
            node_name: Name of the node
            position: New position in scene coordinates

        Raises:
            NodeNotFoundError: If the node doesn't exist
        """
        if node_name not in self.graph_model.nodes:
            raise NodeNotFoundError(node_name)
        self.graph_model.nodes[node_name].position = position

    # Attribute operations
    def create_attribute(
        self,
        node_name: str,
        name: str,
        index: int = -1,
        preset: str = "attr_default",
        plug: bool = True,
        socket: bool = True,
        data_type: Any = None,
        plug_max_connections: int = -1,
        socket_max_connections: int = 1,
        **kwargs,
    ) -> None:
        """
        Create an attribute on a node.

        Args:
            node_name: Name of the node to add the attribute to
            name: Name of the attribute
            index: Position index (-1 for end)
            preset: Visual preset to use
            plug: Whether this attribute can output connections
            socket: Whether this attribute can receive connections
            data_type: Data type for type checking connections
            plug_max_connections: Maximum outgoing connections
                                  (-1 for unlimited)
            socket_max_connections: Maximum incoming connections
                                    (-1 for unlimited)
            **kwargs: Additional properties to store with the attribute

        Raises:
            NodeNotFoundError: If the node doesn't exist
            ValueError: If an attribute with the same name already exists
        """
        self.node_controller.create_attribute(
            node_name,
            name,
            index,
            preset,
            plug,
            socket,
            data_type,
            plug_max_connections,
            socket_max_connections,
            **kwargs,
        )

    def delete_attribute(self, node_name: str, attr_name: str) -> None:
        """
        Delete an attribute from a node.

        Args:
            node_name: Name of the node
            attr_name: Name of the attribute to delete

        Raises:
            NodeNotFoundError: If the node doesn't exist
            AttributeNotFoundError: If the attribute doesn't exist
        """
        self.node_controller.delete_attribute(node_name, attr_name)

    def edit_attribute(
        self,
        node_name: str,
        attr_name: str,
        new_name: Optional[str] = None,
        new_index: Optional[int] = None,
    ) -> None:
        """
        Edit an attribute.

        Args:
            node_name: Name of the node
            attr_name: Current name of the attribute
            new_name: New name for the attribute (optional)
            new_index: New index position for the attribute (optional)

        Raises:
            NodeNotFoundError: If the node doesn't exist
            AttributeNotFoundError: If the attribute doesn't exist
            ValueError: If the new name already exists
        """
        self.node_controller.edit_attribute(
            node_name, attr_name, new_name, new_index
        )

    def get_node_attributes(self, node_name: str) -> List[str]:
        """
        Get a list of attribute names for a node.

        Args:
            node_name: Name of the node

        Returns:
            List of attribute names

        Raises:
            NodeNotFoundError: If the node doesn't exist
        """
        if node_name not in self.graph_model.nodes:
            raise NodeNotFoundError(node_name)
        return list(self.graph_model.nodes[node_name].attributes.keys())

    def attribute_exists(self, node_name: str, attr_name: str) -> bool:
        """
        Check if an attribute exists on a node.

        Args:
            node_name: Name of the node
            attr_name: Name of the attribute

        Returns:
            True if the attribute exists, False otherwise
        """
        if node_name not in self.graph_model.nodes:
            return False
        return attr_name in self.graph_model.nodes[node_name].attributes

    # Connection operations
    def create_connection(
        self,
        source_node: str,
        source_attr: str,
        target_node: str,
        target_attr: str,
    ) -> None:
        """
        Create a connection between two node attributes.

        Args:
            source_node: Name of the source node (must have a plug attribute)
            source_attr: Name of the source attribute (must be a plug)
            target_node: Name of the target node (must have a socket attribute)
            target_attr: Name of the target attribute (must be a socket)

        Raises:
            NodeNotFoundError: If either node doesn't exist
            AttributeNotFoundError: If either attribute doesn't exist
            ConnectionError: If the attributes are not compatible for
                             connection
            IncompatibleTypesError: If the data types are not compatible
        """
        self.connection_controller.create_connection(
            source_node, source_attr, target_node, target_attr
        )

    def delete_connection(
        self,
        source_node: str,
        source_attr: str,
        target_node: str,
        target_attr: str,
    ) -> None:
        """
        Delete a connection between two node attributes.

        Args:
            source_node: Name of the source node
            source_attr: Name of the source attribute
            target_node: Name of the target node
            target_attr: Name of the target attribute
        """
        self.connection_controller.delete_connection(
            source_node, source_attr, target_node, target_attr
        )

    def get_connections(self) -> List[Tuple[str, str, str, str]]:
        """
        Get all connections in the graph.

        Returns:
            List of tuples (source_node, source_attr, target_node, target_attr)
        """
        return [
            (
                conn.plug_node,
                conn.plug_attr,
                conn.socket_node,
                conn.socket_attr,
            )
            for conn in self.graph_model.connections
        ]

    def connection_exists(
        self,
        source_node: str,
        source_attr: str,
        target_node: str,
        target_attr: str,
    ) -> bool:
        """
        Check if a connection exists between two attributes.

        Args:
            source_node: Name of the source node
            source_attr: Name of the source attribute
            target_node: Name of the target node
            target_attr: Name of the target attribute

        Returns:
            True if the connection exists, False otherwise
        """
        for conn in self.graph_model.connections:
            if (
                conn.plug_node == source_node
                and conn.plug_attr == source_attr
                and conn.socket_node == target_node
                and conn.socket_attr == target_attr
            ):
                return True
        return False

    def get_node_connections(
        self, node_name: str
    ) -> List[Tuple[str, str, str, str]]:
        """
        Get all connections involving a specific node.

        Args:
            node_name: Name of the node

        Returns:
            List of tuples (source_node, source_attr, target_node, target_attr)
        """
        connections = []
        for conn in self.graph_model.connections:
            if conn.plug_node == node_name or conn.socket_node == node_name:
                connections.append(
                    (
                        conn.plug_node,
                        conn.plug_attr,
                        conn.socket_node,
                        conn.socket_attr,
                    )
                )
        return connections

    # Graph operations
    def save_graph(self, file_path: str) -> None:
        """
        Save the graph to a JSON file.

        Args:
            file_path: Path to save the file to

        Raises:
            IOError: If the file cannot be written
        """
        self.graph_controller.save_graph(file_path)

    def load_graph(self, file_path: str) -> None:
        """
        Load a graph from a JSON file.

        Args:
            file_path: Path to load the file from

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file format is invalid
        """
        self.graph_controller.load_graph(file_path)

    def clear_graph(self) -> None:
        """
        Clear all nodes and connections from the graph.
        """
        self.graph_controller.clear_graph()

    def evaluate_graph(self) -> List[Tuple[str, str]]:
        """
        Evaluate the graph and return connection information.

        Returns:
            List of tuples (source, target) where each is "node.attribute"
        """
        return self.graph_controller.evaluate_graph()

    def get_graph_stats(self) -> Dict[str, int]:
        """
        Get statistics about the current graph.

        Returns:
            Dictionary with 'nodes', 'connections', and 'attributes' counts
        """
        total_attributes = sum(
            len(node.attributes) for node in self.graph_model.nodes.values()
        )
        return {
            "nodes": len(self.graph_model.nodes),
            "connections": len(self.graph_model.connections),
            "attributes": total_attributes,
        }

    def validate_graph(self) -> List[str]:
        """
        Validate the graph and return any issues found.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check for orphaned connections
        for conn in self.graph_model.connections:
            if conn.plug_node not in self.graph_model.nodes:
                errors.append(
                    "Connection references non-existent plug node: "
                    f"{conn.plug_node}"
                )
            elif (
                conn.plug_attr
                not in self.graph_model.nodes[conn.plug_node].attributes
            ):
                errors.append(
                    "Connection references non-existent plug attribute: "
                    f"{conn.plug_node}.{conn.plug_attr}"
                )

            if conn.socket_node not in self.graph_model.nodes:
                errors.append(
                    "Connection references non-existent socket node: "
                    f"{conn.socket_node}"
                )
            elif (
                conn.socket_attr
                not in self.graph_model.nodes[conn.socket_node].attributes
            ):
                errors.append(
                    "Connection references non-existent socket attribute: "
                    f"{conn.socket_node}.{conn.socket_attr}"
                )

        return errors

    # Utility methods
    def get_upstream_nodes(self, node_name: str) -> List[str]:
        """
        Get all nodes that connect to the specified node
        (upstream dependencies).

        Args:
            node_name: Name of the node

        Returns:
            List of upstream node names
        """
        upstream = set()
        for conn in self.graph_model.connections:
            if conn.socket_node == node_name:
                upstream.add(conn.plug_node)
        return list(upstream)

    def get_downstream_nodes(self, node_name: str) -> List[str]:
        """
        Get all nodes that the specified node connects to
        (downstream dependencies).

        Args:
            node_name: Name of the node

        Returns:
            List of downstream node names
        """
        downstream = set()
        for conn in self.graph_model.connections:
            if conn.plug_node == node_name:
                downstream.add(conn.socket_node)
        return list(downstream)

    def find_cycles(self) -> List[List[str]]:
        """
        Find cycles in the graph.

        Returns:
            List of cycles, where each cycle is a list of node names
        """
        # Simple cycle detection using DFS
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node, path):
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)

            # Visit downstream nodes
            for downstream in self.get_downstream_nodes(node):
                dfs(downstream, path + [node])

            rec_stack.remove(node)

        # Start DFS from all nodes
        for node_name in self.graph_model.nodes:
            if node_name not in visited:
                dfs(node_name, [])

        return cycles

    def get_execution_order(self) -> List[str]:
        """
        Get a topological ordering of nodes for execution.

        Returns:
            List of node names in execution order

        Raises:
            ValueError: If the graph contains cycles
        """
        # Check for cycles first
        cycles = self.find_cycles()
        if cycles:
            raise ValueError(f"Graph contains cycles: {cycles}")

        # Kahn's algorithm for topological sorting
        in_degree = {node: 0 for node in self.graph_model.nodes}

        # Calculate in-degrees
        for conn in self.graph_model.connections:
            in_degree[conn.socket_node] += 1

        # Start with nodes that have no incoming edges
        queue = [node for node, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            # Remove this node and update in-degrees
            for downstream in self.get_downstream_nodes(node):
                in_degree[downstream] -= 1
                if in_degree[downstream] == 0:
                    queue.append(downstream)

        return result

    # Logging methods
    def set_logging_level(self, level):
        """
        Set the logging level for Nodz.

        Args:
            level: Logging level (logging.DEBUG, logging.INFO, logging.WARNING,
                   logging.ERROR, logging.CRITICAL) or string ('DEBUG', 'INFO',
                   'WARNING', 'ERROR', 'CRITICAL')

        Example:
            api.set_logging_level('DEBUG')
            api.set_logging_level(logging.WARNING)
        """
        set_logging_level(level)

    def get_logging_level(self):
        """
        Get the current logging level for Nodz.

        Returns:
            int: Current logging level
        """
        return get_logging_level()

    # Viewport/Framing methods
    def get_viewport_framing(self) -> Dict[str, Any]:
        """
        Get the current viewport framing settings.

        This captures the currently visible scene rectangle, allowing the exact
        same view to be restored later using QGraphicsView.fitInView().

        Returns:
            Dictionary containing:
            - 'visible_rect': The currently visible scene rectangle as [x, y, width, height]

        Example:
            # Save current viewport state
            framing = api.get_viewport_framing()

            # Later restore it
            api.set_viewport_framing(framing)
        """
        # Get the view from the scene via the graph controller
        views = self.graph_controller.scene.views()
        if not views:
            raise RuntimeError("No views available for the scene")

        view = views[0]  # Get the first (and typically only) view

        # Check if it's a NodzView with our viewport methods
        if hasattr(view, "get_viewport_framing"):
            return view.get_viewport_framing()
        else:
            raise RuntimeError(
                "View does not support viewport framing operations"
            )

    def set_viewport_framing(self, framing_data: Dict[str, Any]) -> None:
        """
        Restore the viewport framing settings.

        This restores a previously saved view state by using QGraphicsView.fitInView()
        with the stored visible rectangle.

        Args:
            framing_data: Dictionary containing viewport settings as returned by
                         get_viewport_framing()

        Raises:
            ValueError: If framing_data is invalid or missing required fields
            RuntimeError: If no views are available or view doesn't support framing

        Example:
            # Save viewport state before loading a new graph
            saved_framing = api.get_viewport_framing()

            # Load new graph
            api.load_graph("new_graph.json")

            # Restore previous viewport state
            api.set_viewport_framing(saved_framing)
        """
        # Get the view from the scene via the graph controller
        views = self.graph_controller.scene.views()
        if not views:
            raise RuntimeError("No views available for the scene")

        view = views[0]  # Get the first (and typically only) view

        # Check if it's a NodzView with our viewport methods
        if hasattr(view, "set_viewport_framing"):
            view.set_viewport_framing(framing_data)
        else:
            raise RuntimeError(
                "View does not support viewport framing operations"
            )
