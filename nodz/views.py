"""
Views module for Nodz.

This module contains the view classes for the Nodz graph editor.
Views are responsible only for rendering and user interaction,
with no data manipulation logic.
"""

from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast
from enum import Enum
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Signal # type: ignore

from .models import (
    BaseModel,
    NodeModel,
    AttrModel,
    ConnectionModel,
    ModelObserver,
)


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


class SlotView(QtWidgets.QGraphicsItem, ModelObserver):
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

        # Register as observer
        self.model.add_observer(self)

        # Setup
        self.setAcceptHoverEvents(True)
        self.slot_type = SlotType.SLOT

        # Style
        self.brush = QtGui.QBrush()
        self.brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)

        self.pen = QtGui.QPen()
        self.pen.setStyle(QtCore.Qt.PenStyle.SolidLine)

        # Connection state
        self.new_connection = None

    def on_model_changed(
        self,
        model: BaseModel,
        property_name: str,
        old_value: Any,
        new_value: Any,
    ) -> None:
        """Handle model changes."""
        self.update()

    def parent_node_view(self) -> "NodeView":
        """Get the parent node view."""
        parent = self.parentItem()
        if isinstance(parent, NodeView):
            return parent
        raise TypeError(f"Unexpected parent type: {parent}")

    def can_connect_to(self, other_slot: "SlotView") -> bool:
        """Check if this slot can connect to another slot."""
        # No plug on plug or socket on socket
        has_plug = isinstance(self, PlugView) or isinstance(
            other_slot, PlugView
        )
        has_socket = isinstance(self, SocketView) or isinstance(
            other_slot, SocketView
        )
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
                connections = self.scene().get_slot_connections(self)
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

    def mousePressEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
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

    def mouseMoveEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """Update connection position during drag."""
        if SlotView.drawing_connection:
            # Create bounding box for hit detection
            pointer_pos = event.scenePos().toPoint()

            # Emit signal for controller to handle
            self.signals.attr_connection_dragged.emit(pointer_pos)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
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

            # Use snapped target slot if available, otherwise find item at release position
            target = SlotView.snapped_target_slot
            if not target:
                target = self.scene().itemAt(
                    event.scenePos().toPoint(), QtGui.QTransform()
                )

            # If target is a compatible slot, create connection
            if isinstance(target, SlotView) and target.can_connect_to(SlotView.source_slot):
                # Determine source and target based on slot types
                source_is_plug = isinstance(SlotView.source_slot, PlugView)
                target_is_socket = isinstance(target, SocketView)

                if source_is_plug and target_is_socket:
                    # Connection from plug to socket
                    source_node = (
                        SlotView.source_slot.parent_node_view().model.name
                    )
                    source_attr = SlotView.source_slot.model.attribute
                    target_node = target.parent_node_view().model.name
                    target_attr = target.model.attribute
                elif not source_is_plug and not target_is_socket:
                    # Connection from socket to plug
                    source_node = target.parent_node_view().model.name
                    source_attr = target.model.attribute
                    target_node = (
                        SlotView.source_slot.parent_node_view().model.name
                    )
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
                # If target is not a compatible slot, emit a signal to delete the temporary connection
                # We use empty strings for target_node and target_attr to indicate an invalid connection
                try:
                    source_node = (
                        SlotView.source_slot.parent_node_view().model.name
                    )
                    source_attr = SlotView.source_slot.model.attribute

                    # Emit signal for controller to handle
                    self.signals.connection_created.emit(
                        source_node, source_attr, "", ""
                    )
                except:
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
        self.brush.setColor(
            QtGui.QColor(*self.config[self.model.preset]["plug"])
        )

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
        self.brush.setColor(
            QtGui.QColor(*self.config[self.model.preset]["socket"])
        )

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


class ConnectionView(QtWidgets.QGraphicsPathItem, ModelObserver):
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

        # Register as observer
        self.model.add_observer(self)

        # Connection points
        self.source_point = source_point
        self.target_point = target_point

        # Setup
        self.setZValue(0)
        self._create_style()
        self.update_path()

    def _create_style(self) -> None:
        """Set up the visual style."""
        self.setAcceptHoverEvents(True)

        self._pen = QtGui.QPen(QtGui.QColor(*self.config["connection_color"]))
        self._pen.setWidth(self.config["connection_width"])
        self.setPen(self._pen)

    def on_model_changed(
        self,
        model: BaseModel,
        property_name: str,
        old_value: Any,
        new_value: Any,
    ) -> None:
        """Handle model changes."""
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

    def mousePressEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """Handle mouse press events."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # Bring connection to front
            self.setZValue(1)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """Delete connection on double click."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # Emit signal for controller to handle
            self.signals.connection_deleted.emit(
                self.model.plug_node,
                self.model.plug_attr,
                self.model.socket_node,
                self.model.socket_attr,
            )
        super().mouseDoubleClickEvent(event)


class NodeView(QtWidgets.QGraphicsItem, ModelObserver):
    """View for a node."""

    def __init__(
        self, model: NodeModel, config: Dict[str, Any], signals: ViewSignals
    ) -> None:
        """Initialize the node view."""
        super().__init__()
        self.model = model
        self.config = config
        self.signals = signals

        # Register as observer
        self.model.add_observer(self)

        # Setup
        self.setZValue(1)
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

    def on_model_changed(
        self,
        model: BaseModel,
        property_name: str,
        old_value: Any,
        new_value: Any,
    ) -> None:
        """Handle model changes."""
        if property_name == "name":
            self.update()
        elif property_name == "position":
            self.setPos(new_value)
        elif property_name == "attributes":
            if old_value is None and new_value is not None:
                # Attribute added
                self._create_attribute_view(new_value)
            elif old_value is not None and new_value is None:
                # Attribute removed
                self._remove_attribute_view(old_value.attribute)
            self.update()
        elif property_name == "attributes_order":
            # Attributes reordered
            self.update()

    def _create_style(self) -> None:
        """Set up the visual style."""
        # Background brush
        self._brush = QtGui.QBrush()
        self._brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self._brush.setColor(
            QtGui.QColor(*self.config[self.model.preset]["bg"])
        )

        # Border pen
        self._pen = QtGui.QPen()
        self._pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
        self._pen.setWidth(self.border)
        self._pen.setColor(
            QtGui.QColor(*self.config[self.model.preset]["border"])
        )

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
        self._text_pen.setColor(
            QtGui.QColor(*self.config[self.model.preset]["text"])
        )

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
            socket_view = SocketView(
                self, attr_model, self.config, self.signals
            )
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
        text_rect = QtCore.QRect(
            -margin, -text_height, text_width, text_height
        )

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

    def mouseDoubleClickEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """Handle double click events."""
        super().mouseDoubleClickEvent(event)
        # Emit signal for controller to handle
        self.signals.node_double_clicked.emit(self.model.name)

    def mousePressEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """Handle mouse press events."""
        # Only handle left mouse button events
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            # Emit signal for controller to handle
            self.signals.node_selected.emit(self.model.name, True)
        else:
            # Pass other mouse buttons (like middle) to the parent view
            event.ignore()

    def mouseMoveEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """Handle mouse move events."""
        # Only handle left mouse button events
        if event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self._moving = True
            super().mouseMoveEvent(event)

            # Update connections during the move
            self._update_connected_paths()
        else:
            # Pass other mouse buttons (like middle) to the parent view
            event.ignore()

    def mouseReleaseEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """Handle mouse release events."""
        # Only handle left mouse button events
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self._moving:
                self._moving = False
                # Directly update the model's internal position attribute without triggering notifications
                if hasattr(self.model, "_position"):
                    self.model._position = self.pos()

                # Update connections attached to this node
                self._update_connected_paths()
            super().mouseReleaseEvent(event)
        else:
            # Pass other mouse buttons (like middle) to the parent view
            event.ignore()

    def _update_connected_paths(self) -> None:
        """Update all connection paths connected to this node."""
        if not self.scene():
            return

        # Find all connection views in the scene
        for item in self.scene().items():
            # Check if it's a connection view
            if not isinstance(item, ConnectionView):
                continue

            # Check if this connection is connected to this node
            if (
                not hasattr(item, "model")
                or not hasattr(item.model, "plug_node")
                or not hasattr(item.model, "socket_node")
            ):
                continue

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
            if hasattr(item, "update_path"):
                item.update_path()
