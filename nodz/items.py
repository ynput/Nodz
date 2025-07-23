from __future__ import annotations
from enum import Enum
from typing import Any, Tuple, Optional, Union
from qtpy import QtGui, QtCore, QtWidgets
from .utils import _convert_data_to_color, _create_pointer_bounding_box
from .data_types import NodeModel, AttrModel, ConnectionModel


def is_compatible_type(source_type: Any, target_type: Any) -> bool:
    """
    Check if the source type is compatible with the target type.

    Args:
        source_type (Any): The source data type.
        target_type (Any): The target data type.
    Returns:
        bool: True if compatible, False otherwise.
    """
    if isinstance(source_type, type) and isinstance(target_type, type):
        return issubclass(source_type, target_type)
    return False


class NodeItem(QtWidgets.QGraphicsItem):
    """
    A graphic representation of a node containing attributes.
    """

    def __init__(self, model: NodeModel, config: dict) -> None:
        """
        Initialize the class.

        Args:
            name (str): The name of the node. The name has to be unique as it
                is used as a key to store the node object.
            model (NodeModel): Serializable description of the node.
            config (dict): Configuration dictionary for the node.
        """
        super(NodeItem, self).__init__()

        self.setZValue(1)

        # Storage
        self.model = model
        self.config = config

        # Attributes storage.
        self.plugs = dict()
        self.sockets = dict()
        self.unconnectables = dict()

        self._moving = False  # True while node is moved in scene.

        # Methods.
        self._create_style()

    @property
    def attr_names(self) -> list[str]:
        """Returns a list of attribute names, based on the node's model."""
        return list(self.model.attributes.keys())

    @property
    def attr_count(self) -> int:
        """Returns the number of attributes, based on the node's model."""
        return len(self.model.attributes)

    @property
    def existing_attrs(self) -> list:
        return (
            list(self.plugs.keys())
            + list(self.sockets.keys())
            + list(self.unconnectables.keys())
        )

    def to_dict(self) -> dict:
        """
        Serialize the NodeItem's model to a dict.
        """
        return self.model.to_dict()

    @property
    def height(self) -> int:
        """
        Increment the final height of the node every time an attribute
        is created.
        """
        if self.attr_count > 0:
            return (
                self.base_height
                + self.attr_height * self.attr_count
                + self.border
                + 0.5 * self.radius
            )
        else:
            return self.base_height

    @property
    def pen(self) -> QtGui.QPen:
        """
        Return the pen based on the selection state of the node.
        """
        if self.isSelected():
            return self._pen_sel
        else:
            return self._pen

    def _create_style(self) -> None:
        """
        Read the node style from the configuration file.

        Args:
            config (dict): The configuration dictionary containing the style.
        """
        self.setAcceptHoverEvents(True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

        # Dimensions.
        config = self.config
        self.base_width = config["node_width"]
        self.base_height = config["node_height"]
        self.attr_height = config["node_attr_height"]
        self.border = config["node_border"]
        self.radius = config["node_radius"]

        self.node_center = QtCore.QPointF()
        self.node_center.setX(self.base_width / 2.0)
        self.node_center.setY(self.height / 2.0)

        self._brush = QtGui.QBrush()
        self._brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self._brush.setColor(
            _convert_data_to_color(config[self.model.preset]["bg"])
        )

        self._pen = QtGui.QPen()
        self._pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
        self._pen.setWidth(self.border)
        self._pen.setColor(
            _convert_data_to_color(config[self.model.preset]["border"])
        )

        self._pen_sel = QtGui.QPen()
        self._pen_sel.setStyle(QtCore.Qt.PenStyle.SolidLine)
        self._pen_sel.setWidth(self.border)
        self._pen_sel.setColor(
            _convert_data_to_color(config[self.model.preset]["border_sel"])
        )

        self._text_pen = QtGui.QPen()
        self._text_pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
        self._text_pen.setColor(
            _convert_data_to_color(config[self.model.preset]["text"])
        )

        self._node_text_font = QtGui.QFont(
            config["node_font"],
            config["node_font_size"],
            QtGui.QFont.Weight.Bold,
        )
        self._attr_text_font = QtGui.QFont(
            config["attr_font"],
            config["attr_font_size"],
            QtGui.QFont.Weight.Normal,
        )

        self._attr_brush = QtGui.QBrush()
        self._attr_brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)

        self._attr_brush_alt = QtGui.QBrush()
        self._attr_brush_alt.setStyle(QtCore.Qt.BrushStyle.SolidPattern)

        self._attr_pen = QtGui.QPen()
        self._attr_pen.setStyle(QtCore.Qt.PenStyle.SolidLine)

    def _create_attribute(
        self,
        name: str,
        index: int,
        preset: str,
        plug: bool,
        socket: bool,
        data_type: Any,
        plug_max_connections: int,
        socket_max_connections: int,
        **kwargs,
    ) -> None:
        """
        Create an attribute by expanding the node, adding a label and
        connection items.

        Args:
            name (str): The attribute name.
            index (int): The attribute index.
            preset (str): The attribute preset name.
            plug (bool): True if the attribute is a plug, False otherwise.
            socket (bool): True if the attribute is a socket, False otherwise.
            data_type (Any): The data type of the attribute.
            plug_max_connections(int): The plug's maximum number of connections.
            socket_max_connections(int): The socket's maximum number of connections.
            kwargs: Additional keyword arguments.
        Returns:
            int: The actual attribute index.
        """
        if name in self.existing_attrs:
            raise NameError(
                "An attribute with the same name already exists on this "
                f"node : {name}"
            )

        factory = scene_factory(self)

        attr_model = AttrModel(
            name,
            index,
            preset,
            plug,
            socket,
            data_type,
            plug_max_connections,
            socket_max_connections,
            kwargs=kwargs,
        )

        # Create a plug connection item.
        if plug:
            plug_inst = factory.create_plug_item(self, attr_model, self.config)
            self.plugs[name] = plug_inst

        # Create a socket connection item.
        if socket:
            socket_inst = factory.create_socket_item(
                self, attr_model, self.config
            )
            self.sockets[name] = socket_inst

        # Unconnectable slot that still needs to be serialized.
        if not plug and not socket:
            unconnectable_inst = factory.create_slot_item(
                None, attr_model, self.config
            )
            self.unconnectables[name] = unconnectable_inst

        # Add the attribute based on its index and update model index.
        if index == -1 or index > self.attr_count:
            attr_model.index = len(self.model.attributes)
            if attr_model.attribute not in self.attr_names:
                self.model.attributes[attr_model.attribute] = attr_model
        else:
            attr_model.index = index
            if attr_model.attribute not in self.attr_names:
                self.model.attributes[attr_model.attribute] = attr_model
                self.model.sort_attributes()

        # Update node height.
        self.update()

    def _delete_attribute(self, name: str) -> None:
        """
        Remove an attribute by reducing the node's height, removing the label
        and the connection items.

        Args:
            index (int): Index of the attribute to remove.
        """
        # Remove socket and its connections.
        if name in self.sockets.keys():
            for connection in self.sockets[name].connections:
                connection._remove()

            self.scene().removeItem(self.sockets[name])
            self.sockets.pop(name)

        # Remove plug and its connections.
        if name in self.plugs.keys():
            for connection in self.plugs[name].connections:
                connection._remove()

            self.scene().removeItem(self.plugs[name])
            self.plugs.pop(name)

        # Remove attribute from node.
        self.model.attributes.pop(name)

        self.update()

    def _remove_connections(self) -> None:
        """
        Remove this node instance from the scene.

        Make sure that all the connections to this node are also removed
        in the process
        """
        # Remove all sockets connections.
        for socket in self.sockets.values():
            while len(socket.connections) > 0:
                socket.connections[0]._remove()

        # Remove all plugs connections.
        for plug in self.plugs.values():
            while len(plug.connections) > 0:
                plug.connections[0]._remove()

    def boundingRect(self) -> QtCore.QRectF:
        """
        The bounding rect based on the width and height variables.
        """
        rect = QtCore.QRect(0, 0, self.base_width, self.height).toRectF()
        return rect

    def shape(self) -> QtGui.QPainterPath:
        """
        The shape of the item.
        """
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint_node_base(self, painter: QtGui.QPainter):
        painter.setBrush(self._brush)
        painter.setPen(self.pen)

        painter.drawRoundedRect(
            0, 0, self.base_width, self.height, self.radius, self.radius
        )

    def paint_node_label(
        self,
        painter: QtGui.QPainter,
        align_flag: QtCore.Qt.AlignmentFlag = QtCore.Qt.AlignmentFlag.AlignCenter,
    ):
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
    ):
        config = self.config
        attr_data = self.model.attributes[attr]
        preset = attr_data.preset

        # Attribute base.
        self._attr_brush.setColor(_convert_data_to_color(config[preset]["bg"]))
        if self.model.alternate:
            self._attr_brush_alt.setColor(
                _convert_data_to_color(
                    config[preset]["bg"], True, config["alternate_value"]
                )
            )

        self._attr_pen.setColor(_convert_data_to_color([0, 0, 0, 0]))
        painter.setPen(self._attr_pen)
        painter.setBrush(self._attr_brush)
        if self.model.alternate and (offset / self.attr_height) % 2:
            painter.setBrush(self._attr_brush_alt)

        painter.drawRect(rect)

    def paint_attr_label(
        self,
        attr: str,
        painter: QtGui.QPainter,
        rect: QtCore.QRect,
        align_flag: QtCore.Qt.AlignmentFlag = QtCore.Qt.AlignmentFlag.AlignVCenter,
    ):
        config = self.config
        attr_data = self.model.attributes[attr]
        preset = attr_data.preset

        painter.setPen(_convert_data_to_color(config[preset]["text"]))
        painter.setFont(self._attr_text_font)

        # Search non-connectable attributes.
        if SlotItem.drawing_connection:
            if self == SlotItem.current_hovered_node:
                if not SlotItem.source_slot:
                    raise TypeError("Invalid source_slot")
                if is_compatible_type(
                    attr_data.data_type, SlotItem.source_slot.model.data_type
                ) or (
                    SlotItem.source_slot.slot_type == SlotItem.Type.Plug
                    and attr_data.socket is False
                    or SlotItem.source_slot.slot_type == SlotItem.Type.Socket
                    and attr_data.plug is False
                ):
                    # Set non-connectable attributes color.
                    painter.setPen(
                        _convert_data_to_color(config["non_connectable_color"])
                    )

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
        widget: QtWidgets.QWidget | None = None,
    ) -> None:
        """
        Paint the node and attributes.

        Args:
            painter (QtGui.QPainter): The painter object to draw with.
            option (QtWidgets.QStyleOptionGraphicsItem): The style option object
                for the item.
            widget (QtWidgets.QWidget | None): The widget to paint on, defaults
                to None.
        """
        # Node base.
        self.paint_node_base(painter)

        # Node label.
        self.paint_node_label(painter)

        # Attributes.
        offset = 0

        for attr in self.attr_names:
            rect = QtCore.QRect(
                self.border / 2,
                self.base_height - self.radius + offset,
                self.base_width - self.border,
                self.attr_height,
            )
            # Attribute rect.
            self.paint_attr_base(attr, offset, painter, rect)
            # Attribute label.
            self.paint_attr_label(attr, painter, rect)
            # update offset for next attribute
            offset += self.attr_height

    def mouseDoubleClickEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Emit a signal when the node is double-clicked.
        """
        super(NodeItem, self).mouseDoubleClickEvent(event)
        self.scene().signals.NodeDoubleClicked.emit(self.model)  # type: ignore

    def mouseMoveEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """Mark node as moving."""
        self._moving = True
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Emit a node moved signal when the node is released.
        """
        # Emit node moved signal.
        if self._moving:
            self._moving = False
            self.scene().signals.NodeMoved.emit(self.model, self.pos())  # type: ignore
        super(NodeItem, self).mouseReleaseEvent(event)

    def hoverLeaveEvent(
        self, event: QtWidgets.QGraphicsSceneHoverEvent
    ) -> None:
        """
        Foreground the node on hover and emit a signal.
        """
        for item in self.scene().items():
            if isinstance(item, ConnectionItem):
                item.setZValue(0)

        super(NodeItem, self).hoverLeaveEvent(event)


class SlotItem(QtWidgets.QGraphicsItem):
    """
    The base class for graphics item representing attributes hook.
    """

    # static members
    drawing_connection = False
    current_hovered_node: Optional[NodeItem] = None
    source_slot: Optional[SlotItem] = None

    class Type(Enum):
        Slot = 0
        Plug = 1
        Socket = 2

    def __init__(
        self,
        parent: QtWidgets.QGraphicsItem | None,
        model: AttrModel,
        config: dict,
    ) -> None:
        """
        Initialize the class.

        Args:
            parent (QtWidgets.QGraphicsItem): The parent item of the slot.
            attribute (str): The attribute name of the slot.
            preset (str): The preset value of the slot.
            index (int): The index of the slot in the parent node.
            data_type (Any): The data type of the slot.
            max_connections (int): The maximum number of connections allowed for
                the slot.
        """
        super(SlotItem, self).__init__(parent)
        self.model = model
        self.config = config

        # Status.
        self.setAcceptHoverEvents(True)

        # Storage.
        self.slot_type = SlotItem.Type.Slot

        # Style.
        self.brush = QtGui.QBrush()
        self.brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)

        self.pen = QtGui.QPen()
        self.pen.setStyle(QtCore.Qt.PenStyle.SolidLine)

        # Connections storage.
        self.connected_slots = list()
        self.new_connection = None
        self.connections = list()
        self.max_connections = (
            model.plug_max_connections
            if model.plug
            else model.socket_max_connections
            if model.socket
            else 0
        )

    def to_dict(self) -> dict:
        """
        Serialize the slot item to a dict.
        """
        return self.model.to_dict()

    def parent_node_item(self) -> NodeItem:
        item = self.parentItem()
        if isinstance(item, NodeItem):
            return item
        raise TypeError(f"Unexpected parent type: {item}")

    def connect(self, item: Any, connection: ConnectionItem) -> None:
        raise NotImplementedError("Sub-Classes MUST implement connect() !")

    def disconnect(self, connection: ConnectionItem) -> None:
        raise NotImplementedError("Sub-Classes MUST implement connect() !")

    def accepts(self, slot_item: SlotItem) -> bool:
        """
        Only accepts plug items that belong to other nodes, and only if
        the max connections count is not reached yet.

        Args:
            slot_item (SlotItem): The slot item to connect with.
        """
        # no plug on plug or socket on socket
        has_plug_item = isinstance(self, PlugItem) or isinstance(
            slot_item, PlugItem
        )
        has_socket_item = isinstance(self, SocketItem) or isinstance(
            slot_item, SocketItem
        )
        if not (has_plug_item and has_socket_item):
            return False

        # no self connection
        if self.parentItem() == slot_item.parentItem():
            return False

        # no more than max_connections
        if (
            self.max_connections > 0
            and len(self.connected_slots) >= self.max_connections
        ):
            return False

        # no connection with different types
        if not is_compatible_type(
            slot_item.model.data_type, self.model.data_type
        ):
            return False

        # otherwize, all fine.
        return True

    def mousePressEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Start the connection process.
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            factory = scene_factory(self)
            self.new_connection = factory.create_connection_item(
                self.center().toPoint(),
                self.mapToScene(event.pos()).toPoint(),
                self,
                None,
            )

            self.connections.append(self.new_connection)
            self.scene().addItem(self.new_connection)

            SlotItem.drawing_connection = True
            SlotItem.source_slot = self
        else:
            super(SlotItem, self).mousePressEvent(event)

    def mouseMoveEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Update the new connection's end point position.
        """
        config = self.config
        if SlotItem.drawing_connection:
            mbb = _create_pointer_bounding_box(
                pointer_pos=event.scenePos().toPoint(),
                bb_size=config["mouse_bounding_box"],
            )

            # Get nodes in pointer's bounding box.
            targets = self.scene().items(mbb)

            if any(isinstance(target, NodeItem) for target in targets):
                if self.parentItem() not in targets:
                    for target in targets:
                        if isinstance(target, NodeItem):
                            SlotItem.current_hovered_node = target
            else:
                SlotItem.current_hovered_node = None

            # Set connection's end point.
            if not self.new_connection:
                raise RuntimeError("newConnection is invalid.")
            self.new_connection.target_point = self.mapToScene(event.pos())
            self.new_connection.update_path()
        else:
            super(SlotItem, self).mouseMoveEvent(event)

    def mouseReleaseEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Apply the connection if target_slot is valid.
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            SlotItem.drawing_connection = False

            if not self.new_connection:
                raise RuntimeError("newConnection is invalid")

            target = self.scene().itemAt(
                event.scenePos().toPoint(), QtGui.QTransform()
            )

            if not isinstance(target, SlotItem):
                self.new_connection._remove()
                super(SlotItem, self).mouseReleaseEvent(event)
                return

            if target.accepts(self):
                self.new_connection.target = target
                self.new_connection.source = self
                self.new_connection.target_point = target.center()
                self.new_connection.source_point = self.center()

                # Perform the ConnectionItem.
                self.connect(target, self.new_connection)
                target.connect(self, self.new_connection)

                self.new_connection.update_path()
            else:
                self.new_connection._remove()
        else:
            super(SlotItem, self).mouseReleaseEvent(event)

        SlotItem.current_hovered_node = None

    def shape(self) -> QtGui.QPainterPath:
        """
        The shape of the Slot is a circle.
        """
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect().adjusted(-2, -2, 2, 2))
        return path

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionGraphicsItem,
        widget: QtWidgets.QWidget | None = None,
    ) -> None:
        """
        Paint the Slot.

        Args:
            painter (QtGui.QPainter): The painter to use for drawing.
            option (QtWidgets.QStyleOptionGraphicsItem): The style options for the item.
            widget (QtWidgets.QWidget | None): The widget to use for drawing.
        """
        painter.setBrush(self.brush)
        painter.setPen(self.pen)

        config = self.config
        if SlotItem.drawing_connection:
            if self.parentItem() == SlotItem.current_hovered_node:
                painter.setBrush(
                    _convert_data_to_color(config["non_connectable_color"])
                )
                if not SlotItem.source_slot:
                    raise TypeError("Invalid source_slot")
                if self.slot_type == SlotItem.source_slot.slot_type or (
                    self.slot_type != SlotItem.source_slot.slot_type
                    and is_compatible_type(
                        self.model.data_type,
                        SlotItem.source_slot.model.data_type,
                    )
                ):
                    painter.setBrush(
                        _convert_data_to_color(config["non_connectable_color"])
                    )
                else:
                    _pen_valid = QtGui.QPen()
                    _pen_valid.setStyle(QtCore.Qt.PenStyle.SolidLine)
                    _pen_valid.setWidth(2)
                    _pen_valid.setColor(QtGui.QColor(255, 255, 255, 255))
                    painter.setPen(_pen_valid)
                    painter.setBrush(self.brush)

        painter.drawEllipse(self.boundingRect())

    def center(self) -> QtCore.QPointF:
        """
        Return The center of the Slot.
        """
        return self.mapToScene(self.boundingRect().center())


class PlugItem(SlotItem):
    """
    A graphics item representing an attribute out hook.

    """

    def __init__(
        self,
        parent: QtWidgets.QGraphicsItem,
        model: AttrModel,
        config: dict,
    ) -> None:
        """
        Initialize the class.

        Args:
            parent (QtWidgets.QGraphicsItem): The parent item of the plug.
            model (AttrModel): The description of the attribute.
            config (dict): The configuration of the scene.
        """
        super(PlugItem, self).__init__(
            parent,
            model,
            config,
        )

        # Storage.
        self.slot_type = SlotItem.Type.Plug

        # Methods.
        self._create_style()

    def _create_style(self) -> None:
        """
        Read the attribute style from the configuration file.

        Args:
            parent (QtWidgets.QGraphicsItem): The parent item of the plug.
        """
        config = self.config
        self.brush = QtGui.QBrush()
        self.brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self.brush.setColor(
            _convert_data_to_color(config[self.model.preset]["plug"])
        )

    def boundingRect(self) -> QtCore.QRectF:
        """
        The bounding rect based on the width and height variables.

        Returns:
            QtCore.QRectF: The bounding rectangle of the plug.
        """
        width = height = self.parent_node_item().attr_height / 2.0
        config = self.config

        x = self.parent_node_item().base_width - (width / 2.0)
        y = (
            self.parent_node_item().base_height
            - config["node_radius"]
            + self.parent_node_item().attr_height / 4
            + self.parent_node_item().attr_names.index(self.model.attribute)
            * self.parent_node_item().attr_height
        )

        rect = QtCore.QRect(x, y, width, height).toRectF()
        return rect

    def connect(self, item: SocketItem, connection: ConnectionItem) -> None:
        """
        Connect to the given socket_item.

        Args:
            item (SocketItem): The socket item to connect to.
            connection (ConnectionItem): The connection item to connect to.
        """
        if (
            self.max_connections > 0
            and len(self.connected_slots) >= self.max_connections
        ):
            # Already connected.
            self.connections[self.max_connections - 1]._remove()

        # Populate connection.
        connection.socket_item = item
        connection.model.plug_node = self.parent_node_item().model.name
        connection.model.plug_attr = self.model.attribute
        connection.model.socket_node = item.parent_node_item().model.name
        connection.model.socket_attr = item.model.attribute

        # Add socket to connected slots.
        if item in self.connected_slots:
            self.connected_slots.remove(item)
        self.connected_slots.append(item)

        # Add connection.
        if connection not in self.connections:
            self.connections.append(connection)

        # Emit signal.
        self.scene().signals.PlugConnected.emit(connection.model)  # type: ignore

    def disconnect(self, connection: ConnectionItem) -> None:
        """
        Disconnect the given connection from this plug item.

        Args:
            connection (ConnectionItem): The connection to disconnect.
        """
        # Emit signal.
        self.scene().signals.PlugDisconnected.emit(connection.model)  # type: ignore

        # Remove connected socket from plug
        if connection.socket_item in self.connected_slots:
            self.connected_slots.remove(connection.socket_item)
        # Remove connection
        self.connections.remove(connection)


class SocketItem(SlotItem):
    """
    A graphics item representing an attribute in hook.

    """

    def __init__(
        self,
        parent: QtWidgets.QGraphicsItem,
        model: AttrModel,
        config: dict,
    ) -> None:
        """
        Initialize the socket.

        Args:
            parent (QtWidgets.QGraphicsItem): The parent item of the socket.
            mode (AttrModel): The attribute's description.
            config (dict): The Nodz configuration dict.
        """
        super(SocketItem, self).__init__(
            parent,
            model,
            config,
        )

        # Storage.
        self.slot_type = SlotItem.Type.Socket

        # Methods.
        self._create_style()

    def _create_style(self) -> None:
        """
        Read the attribute style from the configuration file.
        """
        config = self.config
        self.brush = QtGui.QBrush()
        self.brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self.brush.setColor(
            _convert_data_to_color(config[self.model.preset]["socket"])
        )

    def boundingRect(self) -> QtCore.QRectF:
        """
        The bounding rect based on the width and height variables.

        Returns:
            QtCore.QRectF: The bounding rectangle of the socket item.
        """
        width = height = self.parent_node_item().attr_height / 2.0
        config = self.config

        x = -width / 2.0
        y = (
            self.parent_node_item().base_height
            - config["node_radius"]
            + (self.parent_node_item().attr_height / 4)
            + self.parent_node_item().attr_names.index(self.model.attribute)
            * self.parent_node_item().attr_height
        )

        rect = QtCore.QRect(x, y, width, height).toRectF()
        return rect

    def connect(self, item: PlugItem, connection: ConnectionItem) -> None:
        """
        Connect to the given plug item.

        Args:
            item (PlugItem): The plug item to connect to.
            connection (ConnectionItem): The connection item to connect to.
        """
        if (
            self.max_connections > 0
            and len(self.connected_slots) >= self.max_connections
        ):
            # Already connected.
            self.connections[self.max_connections - 1]._remove()

        # Populate connection.
        connection.plug_item = item
        connection.model.socket_node = self.parent_node_item().model.name
        connection.model.socket_attr = self.model.attribute
        connection.model.plug_node = item.parent_node_item().model.name
        connection.model.plug_attr = item.model.attribute

        # Add plug to connected slots.
        self.connected_slots.append(item)

        # Add connection.
        if connection not in self.connections:
            self.connections.append(connection)

        # Emit signal.
        self.scene().signals.SocketConnected.emit(connection.model)  # type: ignore

    def disconnect(self, connection: ConnectionItem) -> None:
        """
        Disconnect the given connection from this socket item.

        Args:
            connection (ConnectionItem): The connection to disconnect.
        """
        # Emit signal.
        self.scene().signals.SocketDisconnected.emit(connection.model)  # type: ignore

        # Remove connected plugs
        if connection.plug_item in self.connected_slots:
            self.connected_slots.remove(connection.plug_item)
        # Remove connections
        self.connections.remove(connection)


class ConnectionItem(QtWidgets.QGraphicsPathItem):
    """
    A graphics path representing a connection between two attributes.

    """

    def __init__(
        self,
        source_point: QtCore.QPoint,
        target_point: QtCore.QPoint,
        source: SlotItem,
        target: Union[SlotItem, None],
    ) -> None:
        """
        Initialize the class.

        Args:
            source_point (QtCore.QPoint): The source point of the connection.
            target_point (QtCore.QPoint): The target point of the connection.
            source (SlotItem): The source slot item.
            target (SlotItem | None): The target slot item.
        """
        super(ConnectionItem, self).__init__()

        self.setZValue(1)

        # Storage.
        self.model = ConnectionModel(
            plug_node=source.parent_node_item().model.name,
            plug_attr=source.model.attribute,
            socket_node=target.parent_node_item().model.name if target else "",
            socket_attr=target.model.attribute if target else "",
        )
        self.source_point = source_point
        self.target_point = target_point
        self.source = source
        self.target = target

        self.plug_item: PlugItem | None = None
        self.socket_item: SocketItem | None = None

        self.movable_point = None

        # Methods.
        self._create_style()

    def _create_style(self) -> None:
        """
        Read the connection style from the configuration file.
        """
        if not self.source:
            raise RuntimeError("source is invalid")
        config = self.source.config
        self.setAcceptHoverEvents(True)
        self.setZValue(-1)

        self._pen = QtGui.QPen(
            _convert_data_to_color(config["connection_color"])
        )
        self._pen.setWidth(config["connection_width"])

    def mousePressEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Snap the Connection to the mouse.
        """
        for item in self.scene().items():
            if isinstance(item, ConnectionItem):
                item.setZValue(0)

        # SlotItem.drawing_connection = True

        d_to_target = (event.pos() - self.target_point).manhattanLength()
        d_to_source = (event.pos() - self.source_point).manhattanLength()
        if d_to_target < d_to_source:
            if not self.target:
                raise RuntimeError("Invalid target")
            self.target_point = event.pos()
            self.movable_point = "target_point"
            self.target.disconnect(self)
            self.target = None
            SlotItem.source_slot = self.source
        else:
            if not self.source:
                raise RuntimeError("Invalid source")
            self.source_point = event.pos()
            self.movable_point = "source_point"
            self.source.disconnect(self)
            self.source = None
            SlotItem.source_slot = self.target

        self.update_path()

    def mouseMoveEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Move the Connection with the mouse.
        """
        config = self.scene().config  # type: ignore

        mbb = _create_pointer_bounding_box(
            pointer_pos=event.scenePos().toPoint(),
            bb_size=config["mouse_bounding_box"],
        )

        # Get nodes in pointer's bounding box.
        targets = self.scene().items(mbb)

        if any(isinstance(target, NodeItem) for target in targets):
            if not SlotItem.source_slot:
                raise TypeError("Invalid source_slot")
            if SlotItem.source_slot.parentItem() not in targets:
                for target in targets:
                    if isinstance(target, NodeItem):
                        SlotItem.current_hovered_node = target
        else:
            SlotItem.current_hovered_node = None

        if self.movable_point == "target_point":
            self.target_point = event.pos()
        else:
            self.source_point = event.pos()

        self.update_path()

    def mouseReleaseEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Create a Connection if possible, otherwise delete it.
        """
        SlotItem.drawing_connection = False

        slot = self.scene().itemAt(
            event.scenePos().toPoint(), QtGui.QTransform()
        )

        if not isinstance(slot, SlotItem):
            self._remove()
            self.update_path()
            super(ConnectionItem, self).mouseReleaseEvent(event)
            return

        if self.movable_point == "target_point":
            if not self.source:
                raise RuntimeError("Invalid source")
            if slot.accepts(self.source):
                # Plug reconnection.
                self.target = slot
                self.target_point = slot.center()
                plug = self.source
                socket = self.target

                # Reconnect.
                socket.connect(plug, self)

                self.update_path()
            else:
                self._remove()

        else:
            if not self.target:
                raise RuntimeError("Invalid target")
            if slot.accepts(self.target):
                # Socket Reconnection
                self.source = slot
                self.source_point = slot.center()
                socket = self.target
                plug = self.source

                # Reconnect.
                plug.connect(socket, self)

                self.update_path()
            else:
                self._remove()

    def _remove(self) -> None:
        """
        Remove this Connection from the scene.
        """
        if self.source is not None:
            self.source.disconnect(self)
        if self.target is not None:
            self.target.disconnect(self)

        self.scene().removeItem(self)

    def update_path(self) -> None:
        """
        Update the path.
        """
        self.setPen(self._pen)

        path = QtGui.QPainterPath()
        path.moveTo(self.source_point)
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

    def to_tuple(self) -> Tuple[str, str]:
        """Serialze to a tuple."""
        return (
            f"{self.model.plug_node}.{self.model.plug_attr}",
            f"{self.model.socket_node}.{self.model.socket_attr}",
        )


class ItemFactory:
    """
    Allows for creation of (subclassed) items with custom instanciation logic.
    """

    def __init__(
        self,
        node_cls: type[NodeItem] = NodeItem,
        slot_cls: type[SlotItem] = SlotItem,
        plug_cls: type[PlugItem] = PlugItem,
        socket_cls: type[SocketItem] = SocketItem,
        connection_cls: type[ConnectionItem] = ConnectionItem,
    ) -> None:
        """
        Initialize the factory with classes for nodes, slots and connections.

        Args:
            node_cls (type[NodeItem]): Class for node items.
            slot_cls (type[SlotItem]): Class for slot items.
            plug_cls (type[PlugItem]): Class for plug items.
            socket_cls (type[SocketItem]): Class for socket items.
            connection_cls (type[ConnectionItem]): Class for connection items.
        """
        self.node_cls = node_cls
        self.slot_cls = slot_cls
        self.plug_cls = plug_cls
        self.socket_cls = socket_cls
        self.connection_cls = connection_cls

    def create_node_item(self, model: NodeModel, config: dict) -> NodeItem:
        """
        Create a new node item with the registered node item class.
        """
        return self.node_cls(model, config)

    def create_slot_item(
        self,
        parent: NodeItem | None,
        model: AttrModel,
        config: dict,
    ) -> SlotItem:
        """
        Create a new slot item with the registered slot item class.
        """
        return self.slot_cls(
            parent,
            model,
            config,
        )

    def create_plug_item(
        self,
        parent: NodeItem,
        model: AttrModel,
        config: dict,
    ) -> PlugItem:
        """
        Create a new plug item with the registered plug item class.
        """
        return self.plug_cls(
            parent,
            model,
            config,
        )

    def create_socket_item(
        self,
        parent: NodeItem,
        model: AttrModel,
        config: dict,
    ) -> SocketItem:
        """
        Create a new socket item with the registered socket item class.
        """
        return self.socket_cls(
            parent,
            model,
            config,
        )

    def create_connection_item(
        self,
        source_point: QtCore.QPoint,
        target_point: QtCore.QPoint,
        source: SlotItem,
        target: Union[SlotItem, None],
    ) -> ConnectionItem:
        """
        Create a new connection item with the registered connection item class.
        """
        return self.connection_cls(source_point, target_point, source, target)


def scene_factory(cls) -> ItemFactory:
    """Return the scene factory for the given node item class."""
    try:
        return cls.scene().factory
    except AttributeError:
        raise
