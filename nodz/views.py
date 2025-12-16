"""
Views module for Nodz.

This module contains the view classes for the Nodz graph editor.
Views are responsible only for rendering and user interaction,
with no data manipulation logic.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from enum import Enum
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Signal  # type: ignore

from .models import (
    NodeModel,
    AttrModel,
    ConnectionModel,
    NodeGroupModel,
)

from .slot_drawer import SlotDrawer

NODE_Z = 0.0
NODE_Z_UP = 0.5
CNCT_Z = -0.25
CNCT_Z_UP = 0.25
GROUP_Z = -0.5  # Groups render behind nodes
GROUP_Z_UP = 0.4  # Selected groups above normal nodes


class SlotType(Enum):
    """Types of slots."""

    SLOT = 0
    PLUG = 1
    SOCKET = 2


class ViewSignals(QtCore.QObject):
    """Signals emitted by view components."""

    # Node signals
    node_moved = Signal(str, QtCore.QPointF)  # node_name, position
    node_selected = Signal(str, bool)  # node_name, selected
    node_double_clicked = Signal(str)  # node_name
    node_deleted = Signal(str)  # node_name

    # Selection signals
    selection_cleared = Signal()  # emitted when all selection is cleared

    # Attribute signals
    attr_connection_started = Signal(
        str, str, QtCore.QPoint
    )  # node_name, attr_name, position
    attr_connection_dragged = Signal(QtCore.QPoint)  # position

    # Connection signals
    connection_created = Signal(
        str, str, str, str
    )  # source_node, source_attr, target_node, target_attr
    connection_deleted = Signal(
        str, str, str, str
    )  # source_node, source_attr, target_node, target_attr

    # Group signals
    group_created = Signal(str, tuple, list, QtCore.QRect)
    group_membership_changed = Signal(str, list)
    group_selected = Signal(str, bool)  # group_name, selected
    group_moved = Signal(str, QtCore.QPointF)  # group_name, delta
    group_resized = Signal(str, QtCore.QRectF)  # group_name, new_rect
    group_drop_node = Signal(str, str)  # node_name, group_name


class SlotView(QtWidgets.QGraphicsItem):
    """Base view class for attribute connection points (plugs and sockets)."""

    # Static variables for connection drawing
    drawing_connection = False
    current_hovered_node: Optional["NodeView"] = None
    source_slot: Optional["SlotView"] = None
    snapped_target_slot: Optional["SlotView"] = None

    def __init__(
        self,
        parent: "NodeView",
        model: AttrModel,
        config: Dict[str, Any],
        signals: ViewSignals,
    ) -> None:
        """Initialize the slot view."""
        super().__init__(parent)
        self.model = model
        self.config = config
        self.signals = signals
        self.slot_drawer = SlotDrawer()
        self.slot_drawer_enabled = self.config[self.model.preset].get(
            "slot_data_type", False
        )

        # Setup
        self.setAcceptHoverEvents(True)
        self.slot_type = SlotType.SLOT

        # Style
        if self.slot_drawer_enabled:
            self.pen, self.brush = self.slot_drawer.pen_and_brush(self.model.data_type)
        else:
            self.brush = QtGui.QBrush()
            self.pen = QtGui.QPen()

        self.brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self.pen.setStyle(QtCore.Qt.PenStyle.SolidLine)

        # Connection state
        self.new_connection = None

    def parent_node_view(self) -> "NodeView":
        """Get the parent node view."""
        parent = self.parentItem()
        if isinstance(parent, NodeView):
            return parent
        raise TypeError(f"Unexpected parent type: {parent}")

    def can_connect_to(self, other_slot: "SlotView") -> bool:
        """Check if this slot can connect to another slot."""
        # No plug on plug or socket on socket
        has_plug = isinstance(self, PlugView) or isinstance(other_slot, PlugView)
        has_socket = isinstance(self, SocketView) or isinstance(other_slot, SocketView)
        if not (has_plug and has_socket):
            return False

        # No self connection
        if self.parentItem() == other_slot.parentItem():
            return False

        # Check max connections
        max_connections = (
            self.model.plug_max_connections
            if isinstance(self, PlugView)
            else self.model.socket_max_connections
        )
        if max_connections > 0:
            # Get connections for this slot
            connections = []
            if self.scene():
                connections = self.scene().get_slot_connections(self)  # type: ignore
            if len(connections) >= max_connections:
                return False

        # Check type compatibility
        if not AttrModel.is_compatible_type(
            other_slot.model.data_type, self.model.data_type
        ):
            return False

        return True

    @staticmethod
    def is_compatible_slot(slot1: "SlotView", slot2: "SlotView") -> bool:
        """Check if two slots are compatible for connection."""
        if slot1.slot_type == slot2.slot_type:
            return False

        plug = slot1 if isinstance(slot1, PlugView) else slot2
        socket = slot2 if isinstance(slot1, PlugView) else slot1

        return AttrModel.is_compatible_type(
            plug.model.data_type, socket.model.data_type
        )

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """Start connection drawing on left click."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # Signal that connection drawing has started
            SlotView.drawing_connection = True
            SlotView.source_slot = self

            # Emit signal for controller to handle
            self.signals.attr_connection_started.emit(
                self.parent_node_view().model.name,
                self.model.attribute,
                self.mapToScene(event.pos()).toPoint(),
            )
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """Update connection position during drag."""
        if SlotView.drawing_connection:
            # Create bounding box for hit detection
            pointer_pos = event.scenePos().toPoint()

            # Emit signal for controller to handle
            self.signals.attr_connection_dragged.emit(pointer_pos)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """Finish connection on mouse release."""
        if (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and SlotView.drawing_connection
        ):
            SlotView.drawing_connection = False

            # Check if we have a valid source slot
            if not SlotView.source_slot:
                SlotView.current_hovered_node = None
                SlotView.source_slot = None
                SlotView.snapped_target_slot = None
                super().mouseReleaseEvent(event)
                return

            # Use snapped target slot if available, otherwise find item at
            # release position
            target = SlotView.snapped_target_slot
            if not target:
                target = self.scene().itemAt(
                    event.scenePos().toPoint(), QtGui.QTransform()
                )

            # If target is a compatible slot, create connection
            if isinstance(target, SlotView) and target.can_connect_to(
                SlotView.source_slot
            ):
                # Determine source and target based on slot types
                source_is_plug = isinstance(SlotView.source_slot, PlugView)
                target_is_socket = isinstance(target, SocketView)

                if source_is_plug and target_is_socket:
                    # Connection from plug to socket
                    source_node = SlotView.source_slot.parent_node_view().model.name
                    source_attr = SlotView.source_slot.model.attribute
                    target_node = target.parent_node_view().model.name
                    target_attr = target.model.attribute
                elif not source_is_plug and not target_is_socket:
                    # Connection from socket to plug
                    source_node = target.parent_node_view().model.name
                    source_attr = target.model.attribute
                    target_node = SlotView.source_slot.parent_node_view().model.name
                    target_attr = SlotView.source_slot.model.attribute
                else:
                    # Invalid connection (plug to plug or socket to socket)
                    SlotView.current_hovered_node = None
                    SlotView.source_slot = None
                    SlotView.snapped_target_slot = None
                    super().mouseReleaseEvent(event)
                    return

                # Emit signal for controller to handle
                self.signals.connection_created.emit(
                    source_node, source_attr, target_node, target_attr
                )
            else:
                # If target is not a compatible slot, emit a signal to delete
                # the temporary connection.
                # We use empty strings for target_node and target_attr to
                # indicate an invalid connection.
                try:
                    source_node = SlotView.source_slot.parent_node_view().model.name
                    source_attr = SlotView.source_slot.model.attribute

                    # Emit signal for controller to handle
                    self.signals.connection_created.emit(
                        source_node, source_attr, "", ""
                    )
                except Exception:
                    # Handle any errors that might occur
                    pass

        SlotView.current_hovered_node = None
        SlotView.source_slot = None
        SlotView.snapped_target_slot = None
        super().mouseReleaseEvent(event)

    def shape(self) -> QtGui.QPainterPath:
        """Define the shape for hit detection."""
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect().adjusted(-2, -2, 2, 2))
        return path

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionGraphicsItem,
        widget: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Paint the slot."""
        painter.setBrush(self.brush)
        painter.setPen(self.pen)
        if self.slot_drawer_enabled:
            SlotDrawer().paint(self.model.data_type, painter, self.boundingRect())
        else:
            painter.drawEllipse(self.boundingRect())

    def center(self) -> QtCore.QPointF:
        """Get the center point of the slot in scene coordinates."""
        return self.mapToScene(self.boundingRect().center())


class PlugView(SlotView):
    """View for a plug (output connection point)."""

    def __init__(
        self,
        parent: "NodeView",
        model: AttrModel,
        config: Dict[str, Any],
        signals: ViewSignals,
    ) -> None:
        """Initialize the plug view."""
        super().__init__(parent, model, config, signals)
        self.slot_type = SlotType.PLUG
        self._create_style()

    def _create_style(self) -> None:
        """Set up the visual style."""
        if self.slot_drawer_enabled:
            _, self.brush = self.slot_drawer.pen_and_brush(self.model.data_type)
        else:
            self.brush.setColor(QtGui.QColor(*self.config[self.model.preset]["plug"]))

    def boundingRect(self) -> QtCore.QRectF:
        """Define the bounding rectangle."""
        width = height = self.parent_node_view().attr_height / 2.0

        x = self.parent_node_view().base_width - (width / 2.0)
        y = (
            self.parent_node_view().base_height
            - self.config["node_radius"]
            + self.parent_node_view().attr_height / 4
            + list(self.parent_node_view().model.attributes.keys()).index(
                self.model.attribute
            )
            * self.parent_node_view().attr_height
        )

        return QtCore.QRect(x, y, width, height).toRectF()


class SocketView(SlotView):
    """View for a socket (input connection point)."""

    def __init__(
        self,
        parent: "NodeView",
        model: AttrModel,
        config: Dict[str, Any],
        signals: ViewSignals,
    ) -> None:
        """Initialize the socket view."""
        super().__init__(parent, model, config, signals)
        self.slot_type = SlotType.SOCKET
        self._create_style()

    def _create_style(self) -> None:
        """Set up the visual style."""
        if self.slot_drawer_enabled:
            _, self.brush = self.slot_drawer.pen_and_brush(self.model.data_type)
        else:
            self.brush.setColor(QtGui.QColor(*self.config[self.model.preset]["socket"]))

    def boundingRect(self) -> QtCore.QRectF:
        """Define the bounding rectangle."""
        width = height = self.parent_node_view().attr_height / 2.0

        x = -width / 2.0
        y = (
            self.parent_node_view().base_height
            - self.config["node_radius"]
            + (self.parent_node_view().attr_height / 4)
            + list(self.parent_node_view().model.attributes.keys()).index(
                self.model.attribute
            )
            * self.parent_node_view().attr_height
        )

        return QtCore.QRect(x, y, width, height).toRectF()


class ConnectionView(QtWidgets.QGraphicsPathItem):
    """View for a connection between slots."""

    def __init__(
        self,
        model: ConnectionModel,
        source_point: QtCore.QPointF,
        target_point: QtCore.QPointF,
        config: Dict[str, Any],
        signals: ViewSignals,
    ) -> None:
        """Initialize the connection view."""
        super().__init__()
        self.model = model
        self.config = config
        self.signals = signals

        # Connection points
        self.source_point = source_point
        self.target_point = target_point

        # Connection end grab zones (for disconnecting by dragging ends)
        self._grab_radius = config.get("connection_grab_radius", 15.0)
        self._is_dragging_end = False
        self._dragging_source = (
            False  # True if dragging source end, False if target end
        )
        self._drag_start_pos = QtCore.QPointF()

        # Setup
        self.setZValue(CNCT_Z)
        self._create_style()
        self.update_path()

    def _create_style(self) -> None:
        """Set up the visual style."""
        self.setAcceptHoverEvents(True)

        self._pen = QtGui.QPen(QtGui.QColor(*self.config["connection_color"]))
        self._pen.setWidth(self.config["connection_width"])
        self.setPen(self._pen)

    def set_data_type(self, data_type: Any) -> None:
        self._pen = SlotDrawer().connection_pen(data_type)
        self.setPen(self._pen)
        self.update()

    def update_path(self) -> None:
        """Update the connection path."""
        path = QtGui.QPainterPath()
        path.moveTo(self.source_point)

        # Calculate control points for a cubic bezier curve
        dx = (self.target_point.x() - self.source_point.x()) * 0.5
        dy = self.target_point.y() - self.source_point.y()
        ctrl1 = QtCore.QPointF(
            self.source_point.x() + dx, self.source_point.y() + dy * 0
        )
        ctrl2 = QtCore.QPointF(
            self.source_point.x() + dx, self.source_point.y() + dy * 1
        )

        path.cubicTo(ctrl1, ctrl2, self.target_point)
        self.setPath(path)

    def _restore_original_endpoints(self) -> None:
        """Restore connection endpoints to their original slot positions."""
        # Find the source and target slots to get their current positions
        if not self.scene():
            return

        # Find source slot (plug)
        for item in self.scene().node_items():
            if item.model.name == self.model.plug_node:
                if self.model.plug_attr in item.plugs:
                    plug = item.plugs[self.model.plug_attr]
                    self.source_point = plug.center()
                break

        # Find target slot (socket)
        for item in self.scene().node_items():
            if item.model.name == self.model.socket_node:
                if self.model.socket_attr in item.sockets:
                    socket = item.sockets[self.model.socket_attr]
                    self.target_point = socket.center()
                break

        # Update the path with restored endpoints
        self.update_path()

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """Handle mouse press events."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # Check if clicking near connection ends for disconnection
            click_pos = event.pos()

            # Check if clicking near source end
            source_distance = (
                click_pos - self.mapFromScene(self.source_point)
            ).manhattanLength()
            target_distance = (
                click_pos - self.mapFromScene(self.target_point)
            ).manhattanLength()

            if source_distance <= self._grab_radius:
                # Start dragging source end
                self._is_dragging_end = True
                self._dragging_source = True
                self._drag_start_pos = click_pos
                self.setZValue(CNCT_Z_UP)  # Bring to front during drag
                event.accept()
                return
            elif target_distance <= self._grab_radius:
                # Start dragging target end
                self._is_dragging_end = True
                self._dragging_source = False
                self._drag_start_pos = click_pos
                self.setZValue(CNCT_Z_UP)  # Bring to front during drag
                event.accept()
                return
            else:
                # Normal connection click - bring to front
                self.setZValue(CNCT_Z)

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """Handle mouse move events."""
        if self._is_dragging_end:
            # Update the dragged end position
            new_pos = self.mapToScene(event.pos())

            if self._dragging_source:
                self.source_point = new_pos
            else:
                self.target_point = new_pos

            # Update the connection path
            self.update_path()
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """Handle mouse release events."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self._is_dragging_end:
            # Check if we dragged far enough to disconnect
            drag_distance = (event.pos() - self._drag_start_pos).manhattanLength()
            disconnect_threshold = (
                self._grab_radius * 2
            )  # Must drag at least 2x grab radius

            if drag_distance >= disconnect_threshold:
                # Disconnect the connection
                self.signals.connection_deleted.emit(
                    self.model.plug_node,
                    self.model.plug_attr,
                    self.model.socket_node,
                    self.model.socket_attr,
                )
            else:
                # Snap back to original position if not dragged far enough
                self._restore_original_endpoints()

            # Reset drag state
            self._is_dragging_end = False
            self._dragging_source = False
            self.setZValue(CNCT_Z)  # Return to normal Z level
            event.accept()
            return

        super().mouseReleaseEvent(event)


class NodeView(QtWidgets.QGraphicsItem):
    """View for a node."""

    def __init__(
        self, model: NodeModel, config: Dict[str, Any], signals: ViewSignals
    ) -> None:
        """Initialize the node view."""
        super().__init__()
        self.model = model
        self.config = config
        self.signals = signals

        # Setup
        self.setZValue(NODE_Z)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        # Dimensions from config
        self.base_width = config["node_width"]
        self.base_height = config["node_height"]
        self.attr_height = config["node_attr_height"]
        self.border = config["node_border"]
        self.radius = config["node_radius"]

        # Center point
        self.node_center = QtCore.QPointF()
        self.node_center.setX(self.base_width / 2.0)
        self.node_center.setY(self.height / 2.0)

        # Attribute views
        self.plugs: Dict[str, PlugView] = {}
        self.sockets: Dict[str, SocketView] = {}

        # State
        self._moving = False

        # Style
        self._create_style()

        # Create attribute views for existing attributes
        for attr_name, attr_model in self.model.attributes.items():
            self._create_attribute_view(attr_model)

    def itemChange(
        self, change: QtWidgets.QGraphicsItem.GraphicsItemChange, value: Any
    ) -> Any:
        if change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            if value:
                self.setZValue(NODE_Z_UP)
            else:
                self.setZValue(NODE_Z)
        return super().itemChange(change, value)

    def _create_style(self) -> None:
        """Set up the visual style."""
        # Background brush
        self._brush = QtGui.QBrush()
        self._brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self._brush.setColor(QtGui.QColor(*self.config[self.model.preset]["bg"]))

        # Border pen
        self._pen = QtGui.QPen()
        self._pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
        self._pen.setWidth(self.border)
        self._pen.setColor(QtGui.QColor(*self.config[self.model.preset]["border"]))

        # Selected border pen
        self._pen_sel = QtGui.QPen()
        self._pen_sel.setStyle(QtCore.Qt.PenStyle.SolidLine)
        self._pen_sel.setWidth(self.border)
        self._pen_sel.setColor(
            QtGui.QColor(*self.config[self.model.preset]["border_sel"])
        )

        # Text pen
        self._text_pen = QtGui.QPen()
        self._text_pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
        self._text_pen.setColor(QtGui.QColor(*self.config[self.model.preset]["text"]))

        # Fonts
        self._node_text_font = QtGui.QFont(
            self.config["node_font"],
            self.config["node_font_size"],
            QtGui.QFont.Weight.Bold,
        )
        self._attr_text_font = QtGui.QFont(
            self.config["attr_font"],
            self.config["attr_font_size"],
            QtGui.QFont.Weight.Normal,
        )

        # Attribute brushes
        self._attr_brush = QtGui.QBrush()
        self._attr_brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)

        self._attr_brush_alt = QtGui.QBrush()
        self._attr_brush_alt.setStyle(QtCore.Qt.BrushStyle.SolidPattern)

        self._attr_pen = QtGui.QPen()
        self._attr_pen.setStyle(QtCore.Qt.PenStyle.SolidLine)

    def _create_attribute_view(self, attr_model: AttrModel) -> None:
        """Create views for an attribute."""
        # Create a plug if needed
        if attr_model.plug:
            plug_view = PlugView(self, attr_model, self.config, self.signals)
            self.plugs[attr_model.attribute] = plug_view

        # Create a socket if needed
        if attr_model.socket:
            socket_view = SocketView(self, attr_model, self.config, self.signals)
            self.sockets[attr_model.attribute] = socket_view

    def _remove_attribute_view(self, attr_name: str) -> None:
        """Remove views for an attribute."""
        # Remove plug if it exists
        if attr_name in self.plugs:
            self.scene().removeItem(self.plugs[attr_name])
            self.plugs.pop(attr_name)

        # Remove socket if it exists
        if attr_name in self.sockets:
            self.scene().removeItem(self.sockets[attr_name])
            self.sockets.pop(attr_name)

    @property
    def height(self) -> int:
        """Calculate the height of the node based on attributes."""
        if len(self.model.attributes) > 0:
            return (
                self.base_height
                + self.attr_height * len(self.model.attributes)
                + self.border
                + 0.5 * self.radius
            )
        else:
            return self.base_height

    @property
    def pen(self) -> QtGui.QPen:
        """Get the appropriate pen based on selection state."""
        return self._pen_sel if self.isSelected() else self._pen

    def boundingRect(self) -> QtCore.QRectF:
        """Define the bounding rectangle."""
        return QtCore.QRect(0, 0, self.base_width, self.height).toRectF()

    def shape(self) -> QtGui.QPainterPath:
        """Define the shape for hit detection."""
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint_node_base(self, painter: QtGui.QPainter) -> None:
        """Paint the node background."""
        painter.setBrush(self._brush)
        painter.setPen(self.pen)
        painter.drawRoundedRect(
            0, 0, self.base_width, self.height, self.radius, self.radius
        )

    def paint_node_label(
        self,
        painter: QtGui.QPainter,
        align_flag: QtCore.Qt.AlignmentFlag = QtCore.Qt.AlignmentFlag.AlignCenter,
    ) -> None:
        """Paint the node label."""
        painter.setPen(self._text_pen)
        painter.setFont(self._node_text_font)

        metrics = painter.fontMetrics()
        text_width = metrics.boundingRect(self.model.name).width() + 14
        text_height = metrics.boundingRect(self.model.name).height() + 14
        margin = (text_width - self.base_width) * 0.5
        text_rect = QtCore.QRect(-margin, -text_height, text_width, text_height)

        painter.drawText(text_rect, align_flag, self.model.name)

    def paint_attr_base(
        self,
        attr: str,
        offset: int,
        painter: QtGui.QPainter,
        rect: QtCore.QRect,
    ) -> None:
        """Paint the attribute background."""
        attr_data = self.model.attributes[attr]
        preset = attr_data.preset

        # Set attribute background color
        self._attr_brush.setColor(QtGui.QColor(*self.config[preset]["bg"]))
        if self.model.alternate:
            self._attr_brush_alt.setColor(
                QtGui.QColor(
                    self.config[preset]["bg_alt"]
                    if "bg_alt" in self.config[preset]
                    else self._adjust_color(
                        self.config[preset]["bg"],
                        self.config["alternate_value"],
                    )
                )
            )

        self._attr_pen.setColor(QtGui.QColor(0, 0, 0, 0))
        painter.setPen(self._attr_pen)
        painter.setBrush(
            self._attr_brush_alt
            if self.model.alternate and (offset / self.attr_height) % 2
            else self._attr_brush
        )

        painter.drawRect(rect)

    def paint_attr_label(
        self,
        attr: str,
        painter: QtGui.QPainter,
        rect: QtCore.QRect,
        align_flag: QtCore.Qt.AlignmentFlag = QtCore.Qt.AlignmentFlag.AlignVCenter,
    ) -> None:
        """Paint the attribute label."""
        attr_data = self.model.attributes[attr]
        preset = attr_data.preset

        # Set text color
        painter.setPen(QtGui.QColor(*self.config[preset]["text"]))
        painter.setFont(self._attr_text_font)

        # Determine alignment based on plug/socket status
        if attr_data.socket and not attr_data.plug:
            align_flag |= QtCore.Qt.AlignmentFlag.AlignLeft
        elif attr_data.plug and not attr_data.socket:
            align_flag |= QtCore.Qt.AlignmentFlag.AlignRight
        else:
            align_flag |= QtCore.Qt.AlignmentFlag.AlignCenter

        # Draw text
        text_rect = QtCore.QRect(
            rect.left() + self.radius,
            rect.top(),
            rect.width() - 2 * self.radius,
            rect.height(),
        )
        painter.drawText(text_rect, align_flag, attr)

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionGraphicsItem,
        widget: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Paint the node and its attributes."""
        # Node base
        self.paint_node_base(painter)

        # Node label
        self.paint_node_label(painter)

        # Attributes
        offset = 0
        for attr in self.model.attributes.keys():
            rect = QtCore.QRect(
                self.border / 2,
                self.base_height - self.radius + offset,
                self.base_width - self.border,
                self.attr_height,
            )
            # Attribute background
            self.paint_attr_base(attr, offset, painter, rect)
            # Attribute label
            self.paint_attr_label(attr, painter, rect)
            # Update offset for next attribute
            offset += self.attr_height

    def _adjust_color(self, color_str: str, factor: float) -> str:
        """Adjust a color by a factor."""
        color = QtGui.QColor(*color_str)
        mult = color.lightness() / 255.0
        color.setRed(max(0, int(color.red() - factor * mult)))
        color.setGreen(max(0, int(color.green() - factor * mult)))
        color.setBlue(max(0, int(color.blue() - factor * mult)))
        return color.name()

    def mouseDoubleClickEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """Handle double click events."""
        super().mouseDoubleClickEvent(event)
        # Emit signal for controller to handle
        self.signals.node_double_clicked.emit(self.model.name)

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """Handle mouse press events."""
        # Only handle left mouse button events
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            # Emit signal for controller to handle
            self.signals.node_selected.emit(self.model.name, True)
        else:
            # Pass other mouse buttons (like middle) to the parent view
            event.ignore()

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """Handle mouse move events."""
        # Only handle left mouse button events
        if event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self._moving = True
            super().mouseMoveEvent(event)
            # Connection updates will be handled by ConnectionController via
            # node_moved signal
        else:
            # Pass other mouse buttons (like middle) to the parent view
            event.ignore()

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        """Handle mouse release events."""
        # Only handle left mouse button events
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self._moving:
                self._moving = False
                # Directly update the model's internal position attribute
                # without triggering notifications
                self.model._position = self.pos()

                # Emit node_moved signal - ConnectionController will handle
                # connection updates
                self.signals.node_moved.emit(self.model.name, self.pos())

                # Check if node was dropped on a group
                self._check_drop_on_group()
            super().mouseReleaseEvent(event)
        else:
            # Pass other mouse buttons (like middle) to the parent view
            event.ignore()

    def _check_drop_on_group(self) -> None:
        """Check if this node was dropped on a group and emit signal.

        Checks if the node's bounding rect intersects with any group's
        bounding rect. If so, and the node is not already a member of
        that group, emits group_drop_node.
        """
        if not self.scene():
            return

        node_rect = self.sceneBoundingRect()

        # Find all groups in the scene
        for item in self.scene().items():
            if not isinstance(item, NodeGroupView):
                continue

            # Check if node overlaps with group
            group_rect = item.sceneBoundingRect()
            if not group_rect.intersects(node_rect):
                continue

            # Check if node is already a member of this group
            if self.model.name in item.model.members:
                continue

            # Emit signal: (node_name, group_name)
            self.signals.group_drop_node.emit(
                self.model.name,
                item.model.name,
            )
            # Only add to one group at a time
            break

    def _update_connected_paths(self) -> None:
        """Update all connection paths connected to this node."""
        if not self.scene():
            return

        # Find all connection views in the scene
        for item in self.scene().connection_items():
            if (
                item.model.plug_node != self.model.name
                and item.model.socket_node != self.model.name
            ):
                continue

            # Update connection endpoints
            if item.model.plug_node == self.model.name:
                plug = self.plugs.get(item.model.plug_attr)
                if plug:
                    item.source_point = plug.center()

            if item.model.socket_node == self.model.name:
                socket = self.sockets.get(item.model.socket_attr)
                if socket:
                    item.target_point = socket.center()

            # Update the path
            item.update_path()


class ResizeHandle(Enum):
    """Enum for resize handle positions."""

    NONE = 0
    TOP_LEFT = 1
    TOP_RIGHT = 2
    BOTTOM_LEFT = 3
    BOTTOM_RIGHT = 4


class NodeGroupView(QtWidgets.QGraphicsRectItem):
    """View for a node group - a visual container for organizing nodes.

    Groups render as semi-transparent rounded rectangles behind nodes,
    with a title bar displaying the group name. Groups can be selected,
    moved, and resized via corner handles.

    Attributes:
        model: The NodeGroupModel containing group data.
        config: Configuration dictionary for styling.
        signals: ViewSignals instance for emitting interaction signals.
    """

    # Constants for group styling
    TITLE_HEIGHT = 24  # pixels
    BORDER_WIDTH = 2  # pixels
    CORNER_RADIUS = 8  # pixels
    PADDING = 20  # pixels around member nodes
    HANDLE_SIZE = 10  # pixels for resize handles
    FILL_OPACITY = 51  # ~20% opacity (255 * 0.2)

    def __init__(
        self,
        model: NodeGroupModel,
        config: Dict[str, Any],
        signals: ViewSignals,
    ) -> None:
        """Initialize the node group view.

        Args:
            model: The NodeGroupModel containing group data.
            config: Configuration dictionary for styling.
            signals: ViewSignals instance for emitting signals.
        """
        super().__init__()
        self.model = model
        self.config = config
        self.signals = signals

        # Setup flags
        self.setZValue(GROUP_Z)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

        # Get dimensions from config or use defaults
        grp_cfg = config.get("groups", {})
        self._padding = grp_cfg.get("padding", self.PADDING)
        self._title_height = grp_cfg.get("title_height", self.TITLE_HEIGHT)
        self._corner_radius = grp_cfg.get("corner_radius", self.CORNER_RADIUS)
        self._handle_size = grp_cfg.get("handle_size", self.HANDLE_SIZE)
        self._fill_opacity = grp_cfg.get("fill_opacity", self.FILL_OPACITY)

        # State
        self._moving = False
        self._resizing = False
        self._resize_handle = ResizeHandle.NONE
        self._resize_start_rect = QtCore.QRectF()
        self._resize_start_pos = QtCore.QPointF()
        self._drop_highlight = False
        self._last_pos = QtCore.QPointF()

        # Initialize rect from model or use default
        if model.rect is not None:
            self.setRect(model.rect)
        else:
            self.setRect(QtCore.QRectF(0, 0, 200, 150))

        # Style
        self._create_style()

    def _create_style(self) -> None:
        """Set up the visual style from model color."""
        r, g, b, a = self.model.color

        # Background brush (semi-transparent with ~20% opacity)
        fill_alpha = min(a, self._fill_opacity)
        self._brush = QtGui.QBrush(QtGui.QColor(r, g, b, fill_alpha))

        # Border pen (solid, using group color)
        self._pen = QtGui.QPen(QtGui.QColor(r, g, b, min(255, a + 100)))
        self._pen.setWidth(self.BORDER_WIDTH)
        self._pen.setStyle(QtCore.Qt.PenStyle.SolidLine)

        # Selected border (dashed white)
        self._pen_sel = QtGui.QPen(QtGui.QColor(200, 200, 200, 128))
        self._pen_sel.setWidth(self.BORDER_WIDTH + 1)
        self._pen_sel.setStyle(QtCore.Qt.PenStyle.DashLine)

        # Drop zone highlight pen
        self._pen_drop = QtGui.QPen(QtGui.QColor(100, 200, 100))
        self._pen_drop.setWidth(self.BORDER_WIDTH + 2)
        self._pen_drop.setStyle(QtCore.Qt.PenStyle.DashDotLine)

        # Title bar brush (slightly more opaque)
        title_alpha = min(255, a + 50)
        self._title_brush = QtGui.QBrush(QtGui.QColor(r, g, b, title_alpha))

        # Title text color (white for contrast)
        self._text_color = QtGui.QColor(255, 255, 255)
        self._title_font = QtGui.QFont(
            self.config.get("group_font", "Arial"),
            self.config.get("group_font_size", 11),
            QtGui.QFont.Weight.Bold,
        )

        # Handle brush
        self._handle_brush = QtGui.QBrush(QtGui.QColor(255, 255, 255, 180))
        self._handle_pen = QtGui.QPen(QtGui.QColor(100, 100, 100))
        self._handle_pen.setWidth(1)

    def update_from_model(self) -> None:
        """Update the view from the model data.

        Refreshes the visual style and rect based on current model state.
        """
        self._create_style()
        if self.model.rect is not None:
            self.setRect(self.model.rect)
        self.update()

    def get_bounding_rect_for_members(
        self,
        node_views: Dict[str, NodeView],
    ) -> Optional[QtCore.QRectF]:
        """Calculate the bounding rect that fits all member nodes.

        Args:
            node_views: Dictionary mapping node names to NodeView instances.

        Returns:
            QRectF containing all member nodes with padding, or None if
            no members exist.
        """
        if not self.model.members:
            return None

        union_rect: Optional[QtCore.QRectF] = None
        for node_name in self.model.members:
            if node_name not in node_views:
                continue
            node_view = node_views[node_name]
            node_rect = node_view.sceneBoundingRect()
            if union_rect is None:
                union_rect = QtCore.QRectF(node_rect)
            else:
                union_rect = union_rect.united(node_rect)

        if union_rect is None:
            return None

        # Add padding and title height
        padded_rect = QtCore.QRectF(
            union_rect.x() - self._padding,
            union_rect.y() - self._padding - self._title_height - 5,
            union_rect.width() + 2 * self._padding,
            union_rect.height() + 2 * self._padding + self._title_height,
        )
        return padded_rect

    def update_rect_from_members(
        self,
        node_views: Dict[str, NodeView],
    ) -> None:
        """Update the group rect to fit all member nodes.

        Args:
            node_views: Dictionary mapping node names to NodeView instances.
        """
        bounding_rect = self.get_bounding_rect_for_members(node_views)
        if bounding_rect is not None:
            self.prepareGeometryChange()
            self.setPos(bounding_rect.topLeft())
            self.setRect(
                QtCore.QRectF(0, 0, bounding_rect.width(), bounding_rect.height())
            )
            # Update model rect
            self.model.rect = QtCore.QRectF(
                self.pos().x(),
                self.pos().y(),
                bounding_rect.width(),
                bounding_rect.height(),
            )
            self.update()

    def highlight_drop_zone(self, highlight: bool) -> None:
        """Enable or disable drop zone highlighting.

        Args:
            highlight: True to show drop zone highlight, False to hide.
        """
        self._drop_highlight = highlight
        self.update()

    def _get_handle_rects(self) -> Dict[ResizeHandle, QtCore.QRectF]:
        """Get the rectangles for all resize handles.

        Returns:
            Dictionary mapping ResizeHandle enum to QRectF positions.
        """
        rect = self.rect()
        size = self._handle_size
        half = size / 2.0

        return {
            ResizeHandle.TOP_LEFT: QtCore.QRectF(
                rect.left() - half,
                rect.top() - half,
                size,
                size,
            ),
            ResizeHandle.TOP_RIGHT: QtCore.QRectF(
                rect.right() - half,
                rect.top() - half,
                size,
                size,
            ),
            ResizeHandle.BOTTOM_LEFT: QtCore.QRectF(
                rect.left() - half,
                rect.bottom() - half,
                size,
                size,
            ),
            ResizeHandle.BOTTOM_RIGHT: QtCore.QRectF(
                rect.right() - half,
                rect.bottom() - half,
                size,
                size,
            ),
        }

    def _handle_at_pos(
        self,
        pos: QtCore.QPointF,
    ) -> ResizeHandle:
        """Determine which resize handle (if any) is at the given position.

        Args:
            pos: Position to check in item coordinates.

        Returns:
            ResizeHandle enum value, or ResizeHandle.NONE if no handle.
        """
        handles = self._get_handle_rects()
        for handle, rect in handles.items():
            if rect.contains(pos):
                return handle
        return ResizeHandle.NONE

    def boundingRect(self) -> QtCore.QRectF:
        """Return the bounding rect including resize handles.

        Returns:
            QRectF that encompasses the group and its handles.
        """
        rect = self.rect()
        # Expand to include handle areas
        margin = self._handle_size
        return rect.adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QtGui.QPainterPath:
        """Define shape for hit detection.

        Returns:
            QPainterPath representing the interactive shape.
        """
        path = QtGui.QPainterPath()
        path.addRoundedRect(
            self.rect(),
            self._corner_radius,
            self._corner_radius,
        )
        # Add handle shapes when selected
        if self.isSelected():
            for handle_rect in self._get_handle_rects().values():
                path.addRect(handle_rect)
        return path

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionGraphicsItem,
        widget: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """Paint the group background, title bar, and handles.

        Args:
            painter: QPainter to use for drawing.
            option: Style options.
            widget: Optional widget being painted on.
        """
        rect = self.rect()

        # Determine which pen to use
        if self._drop_highlight:
            pen = self._pen_drop
        elif self.isSelected():
            pen = self._pen_sel
        else:
            pen = self._pen

        # Draw main background
        painter.setBrush(self._brush)
        painter.setPen(pen)
        painter.drawRoundedRect(
            rect,
            self._corner_radius,
            self._corner_radius,
        )

        # Draw title bar area
        title_rect = QtCore.QRectF(
            rect.left(),
            rect.top(),
            rect.width(),
            self._title_height,
        )

        # Create a clipped path for the title bar (rounded top corners)
        title_path = QtGui.QPainterPath()
        title_path.addRoundedRect(
            QtCore.QRectF(
                rect.left(),
                rect.top(),
                rect.width(),
                self._title_height + self._corner_radius,
            ),
            self._corner_radius,
            self._corner_radius,
        )
        # Clip off the bottom rounded part
        clip_rect = QtCore.QRectF(
            rect.left(),
            rect.top() + self._title_height,
            rect.width(),
            self._corner_radius,
        )
        title_path.addRect(clip_rect)

        painter.setBrush(self._title_brush)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setClipRect(title_rect)
        painter.drawRoundedRect(
            QtCore.QRectF(
                rect.left(),
                rect.top(),
                rect.width(),
                self._title_height + self._corner_radius,
            ),
            self._corner_radius,
            self._corner_radius,
        )
        painter.setClipping(False)

        # Draw title text
        painter.setPen(self._text_color)
        painter.setFont(self._title_font)
        text_rect = QtCore.QRectF(
            rect.left() + 10,
            rect.top() + 2,
            rect.width() - 20,
            self._title_height - 4,
        )
        painter.drawText(
            text_rect,
            int(
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            ),
            self.model.name,
        )

        # Draw resize handles when selected
        if self.isSelected():
            painter.setBrush(self._handle_brush)
            painter.setPen(self._handle_pen)
            for handle_rect in self._get_handle_rects().values():
                painter.drawRect(handle_rect)

    def itemChange(
        self,
        change: QtWidgets.QGraphicsItem.GraphicsItemChange,
        value: Any,
    ) -> Any:
        """Handle item change notifications.

        Args:
            change: The type of change.
            value: The new value.

        Returns:
            The value to use (possibly modified).
        """
        if change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            # Update Z-value based on selection
            if value:
                self.setZValue(GROUP_Z_UP)
            else:
                self.setZValue(GROUP_Z)
            # Emit selection signal
            self.signals.group_selected.emit(self.model.name, bool(value))

        return super().itemChange(change, value)

    def hoverMoveEvent(
        self,
        event: QtWidgets.QGraphicsSceneHoverEvent,
    ) -> None:
        """Handle hover move to update cursor for resize handles.

        Args:
            event: The hover event.
        """
        if self.isSelected():
            handle = self._handle_at_pos(event.pos())
            if handle in (ResizeHandle.TOP_LEFT, ResizeHandle.BOTTOM_RIGHT):
                self.setCursor(QtCore.Qt.CursorShape.SizeFDiagCursor)
            elif handle in (ResizeHandle.TOP_RIGHT, ResizeHandle.BOTTOM_LEFT):
                self.setCursor(QtCore.Qt.CursorShape.SizeBDiagCursor)
            else:
                self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(
        self,
        event: QtWidgets.QGraphicsSceneHoverEvent,
    ) -> None:
        """Reset cursor when leaving the item.

        Args:
            event: The hover event.
        """
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        super().hoverLeaveEvent(event)

    def mousePressEvent(
        self,
        event: QtWidgets.QGraphicsSceneMouseEvent,
    ) -> None:
        """Handle mouse press for movement and resizing.

        Args:
            event: The mouse event.
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # Check for resize handle first (only when selected)
            if self.isSelected():
                handle = self._handle_at_pos(event.pos())
                if handle != ResizeHandle.NONE:
                    self._resizing = True
                    self._resize_handle = handle
                    self._resize_start_rect = QtCore.QRectF(self.rect())
                    self._resize_start_pos = event.scenePos()
                    event.accept()
                    return

            # Start moving
            self._moving = True
            self._last_pos = self.pos()
            self.setZValue(GROUP_Z_UP)

        super().mousePressEvent(event)

    def mouseMoveEvent(
        self,
        event: QtWidgets.QGraphicsSceneMouseEvent,
    ) -> None:
        """Handle mouse move for dragging and resizing.

        Args:
            event: The mouse event.
        """
        if self._resizing:
            # Handle resize
            delta = event.scenePos() - self._resize_start_pos
            new_rect = QtCore.QRectF(self._resize_start_rect)

            # Minimum size constraints
            min_width = 100.0
            min_height = self._title_height + 50.0

            if self._resize_handle == ResizeHandle.TOP_LEFT:
                new_rect.setLeft(
                    min(
                        new_rect.left() + delta.x(),
                        new_rect.right() - min_width,
                    )
                )
                new_rect.setTop(
                    min(
                        new_rect.top() + delta.y(),
                        new_rect.bottom() - min_height,
                    )
                )
            elif self._resize_handle == ResizeHandle.TOP_RIGHT:
                new_rect.setRight(
                    max(
                        new_rect.right() + delta.x(),
                        new_rect.left() + min_width,
                    )
                )
                new_rect.setTop(
                    min(
                        new_rect.top() + delta.y(),
                        new_rect.bottom() - min_height,
                    )
                )
            elif self._resize_handle == ResizeHandle.BOTTOM_LEFT:
                new_rect.setLeft(
                    min(
                        new_rect.left() + delta.x(),
                        new_rect.right() - min_width,
                    )
                )
                new_rect.setBottom(
                    max(
                        new_rect.bottom() + delta.y(),
                        new_rect.top() + min_height,
                    )
                )
            elif self._resize_handle == ResizeHandle.BOTTOM_RIGHT:
                new_rect.setRight(
                    max(
                        new_rect.right() + delta.x(),
                        new_rect.left() + min_width,
                    )
                )
                new_rect.setBottom(
                    max(
                        new_rect.bottom() + delta.y(),
                        new_rect.top() + min_height,
                    )
                )

            self.prepareGeometryChange()
            self.setRect(new_rect)
            self.update()
            event.accept()
            return

        if self._moving:
            # Calculate movement delta
            super().mouseMoveEvent(event)
            delta = self.pos() - self._last_pos
            self._last_pos = self.pos()

            # Emit signal for controller to move member nodes
            if delta.x() != 0 or delta.y() != 0:
                self.signals.group_moved.emit(self.model.name, delta)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(
        self,
        event: QtWidgets.QGraphicsSceneMouseEvent,
    ) -> None:
        """Handle mouse release after movement or resizing.

        Args:
            event: The mouse event.
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self._resizing:
                self._resizing = False
                self._resize_handle = ResizeHandle.NONE
                # Update model rect
                scene_rect = QtCore.QRectF(
                    self.pos().x() + self.rect().x(),
                    self.pos().y() + self.rect().y(),
                    self.rect().width(),
                    self.rect().height(),
                )
                self.model.rect = scene_rect
                # Emit resize signal
                self.signals.group_resized.emit(
                    self.model.name,
                    scene_rect,
                )
                event.accept()
                return

            if self._moving:
                self._moving = False
                self.setZValue(GROUP_Z)
                # Update model rect
                self.model.rect = QtCore.QRectF(
                    self.pos().x(),
                    self.pos().y(),
                    self.rect().width(),
                    self.rect().height(),
                )

        super().mouseReleaseEvent(event)
