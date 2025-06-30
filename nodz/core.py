from __future__ import annotations
import os
from typing import Any
from enum import Enum
from qtpy import QtGui, QtCore, QtWidgets
import nodz.utils as utils
from nodz.utils import nlog


DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "default_config.json"
)


def _nodz_instance(cls) -> Nodz:
    try:
        view = cls.scene().views()[0]
    except BaseException as err:
        raise RuntimeError(f"Could not get first scene view: {err} ")
    else:
        if isinstance(view, Nodz):
            return view
        else:
            raise TypeError(f"Unexpected view type: {view}")


def _nodz_scene(cls) -> NodeScene:
    scene = cls.scene()
    if isinstance(scene, NodeScene):
        return scene
    else:
        raise TypeError(f"Unexpected scene type: {scene}")


class ViewState(Enum):
    DEFAULT = 0
    SELECTION = 1
    ADD_SELECTION = 2
    SUBTRACT_SELECTION = 3
    TOGGLE_SELECTION = 4
    ZOOM_VIEW = 5
    DRAG_VIEW = 6
    DRAG_ITEM = 7


class Nodz(QtWidgets.QGraphicsView):
    """
    The main view for the node graph representation.

    The node view implements a state pattern to control all the
    different user interactions.

    """

    # FIXME: Somehow QtCore.Signal is flagged by pylance as
    # not exported by qtpy.QtCore...

    signal_NodeCreated = QtCore.Signal(object)  # type: ignore (qtpy)
    signal_NodeDeleted = QtCore.Signal(object)  # type: ignore (qtpy)
    signal_NodeEdited = QtCore.Signal(object, object)  # type: ignore (qtpy)
    signal_NodeSelected = QtCore.Signal(object)  # type: ignore (qtpy)
    signal_NodeMoved = QtCore.Signal(str, object)  # type: ignore (qtpy)
    signal_NodeDoubleClicked = QtCore.Signal(str)  # type: ignore (qtpy)

    signal_AttrCreated = QtCore.Signal(object, object)  # type: ignore (qtpy)
    signal_AttrDeleted = QtCore.Signal(object, object)  # type: ignore (qtpy)
    signal_AttrEdited = QtCore.Signal(object, object, object)  # type: ignore (qtpy)

    signal_PlugConnected = QtCore.Signal(object, object, object, object)  # type: ignore (qtpy)
    signal_PlugDisconnected = QtCore.Signal(object, object, object, object)  # type: ignore (qtpy)
    signal_SocketConnected = QtCore.Signal(object, object, object, object)  # type: ignore (qtpy)
    signal_SocketDisconnected = QtCore.Signal(object, object, object, object)  # type: ignore (qtpy)

    signal_GraphSaved = QtCore.Signal()  # type: ignore (qtpy)
    signal_GraphLoaded = QtCore.Signal()  # type: ignore (qtpy)
    signal_GraphCleared = QtCore.Signal()  # type: ignore (qtpy)
    signal_GraphEvaluated = QtCore.Signal()  # type: ignore (qtpy)

    signal_KeyPressed = QtCore.Signal(object)  # type: ignore (qtpy)
    signal_Dropped = QtCore.Signal()  # type: ignore (qtpy)

    def __init__(
        self,
        parent: Any,
        config_path: str = DEFAULT_CONFIG_PATH,
    ):
        """
        Initialize the graphics view.

        """
        super(Nodz, self).__init__(parent)

        # Load nodz configuration.
        self.load_config(config_path)

        # General data.
        self.grid_vis_toggle = True
        self.grid_snap_toggle = False
        self._node_snap = False

        # Connections data.
        self.drawing_connection = False
        self.current_hovered_node: NodeItem | None = None
        self.source_slot: SlotItem | None = None

        # Display options.
        self.current_state = ViewState.DEFAULT
        self.pressed_keys = list()

    @property
    def nodz_scene(self) -> NodeScene:
        return _nodz_scene(self)

    @property
    def scene_nodes(self) -> dict:
        try:
            return self.nodz_scene.nodes
        except AttributeError:
            raise RuntimeError(
                "Scene hasn't been setup yet ! Run Nodz.Initialize() first."
            )

    @scene_nodes.setter
    def scene_nodes(self, value):
        try:
            self.nodz_scene.nodes = value
        except AttributeError:
            raise RuntimeError(
                "Scene hasn't been setup yet ! Run Nodz.Initialize() first."
            )

    def drawForeground(
        self, painter: QtGui.QPainter, rect: QtCore.QRectF | QtCore.QRect
    ) -> None:
        """
        draw help with available keyboard shortcuts.
        """
        h_str = (
            "Keyboard Shortcuts:   "
            "L: organize graph    A: Frame graph    F: Frame selection    "
            "S-down: Snap to grid"
        )
        vp_bottom_left = self.viewport().rect().bottomLeft()
        painter.resetTransform()
        h_pen = QtGui.QPen()
        h_pen.setColor(QtGui.QColor(255, 255, 255, 96))
        painter.setPen(h_pen)
        h_rect = painter.fontMetrics().boundingRect(h_str)
        painter.drawText(
            QtCore.QPointF(
                vp_bottom_left.x() + 20, vp_bottom_left.y() - h_rect.height()
            ),
            h_str,
        )

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """
        Zoom in the view with the mouse wheel.

        """
        self.current_state = ViewState.ZOOM_VIEW
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )

        in_factor = 1.15
        out_factor = 1 / in_factor

        delta = event.angleDelta().y()

        if delta > 0:
            zoom_factor = in_factor
        else:
            zoom_factor = out_factor

        self.scale(zoom_factor, zoom_factor)
        self.current_state = ViewState.DEFAULT

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Initialize tablet zoom, drag canvas and the selection.

        """
        # Tablet zoom
        if (
            event.button() == QtCore.Qt.MouseButton.RightButton
            and event.modifiers() == QtCore.Qt.KeyboardModifier.AltModifier
        ):
            self.current_state = ViewState.ZOOM_VIEW
            self.init_mouse_pos = event.pos()
            self.zoom_initial_pos = event.pos()
            self.init_mouse = QtGui.QCursor.pos()  # FIXME: unused ?
            self.setInteractive(False)

        # Drag view
        elif (
            event.button() == QtCore.Qt.MouseButton.MiddleButton
            and event.modifiers() == QtCore.Qt.KeyboardModifier.AltModifier
        ):
            self.current_state = ViewState.DRAG_VIEW
            self.prev_pos = event.pos()
            self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
            self.setInteractive(False)

        # Rubber band selection
        elif (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and event.modifiers() == QtCore.Qt.KeyboardModifier.NoModifier
            and self.scene().itemAt(
                self.mapToScene(event.pos()), QtGui.QTransform()
            )
            is None
        ):
            self.current_state = ViewState.SELECTION
            self._init_rubberband(event.pos().toPointF())
            self.setInteractive(False)

        # Drag Item
        elif (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and event.modifiers() == QtCore.Qt.KeyboardModifier.NoModifier
            and self.scene().itemAt(
                self.mapToScene(event.pos()), QtGui.QTransform()
            )
            is not None
        ):
            self.current_state = ViewState.DRAG_ITEM
            self.setInteractive(True)

        # Add selection
        elif (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and QtCore.Qt.Key.Key_Shift in self.pressed_keys
            and QtCore.Qt.Key.Key_Control in self.pressed_keys
        ):
            self.current_state = ViewState.ADD_SELECTION
            self._init_rubberband(event.pos().toPointF())
            self.setInteractive(False)

        # Subtract selection
        elif (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            self.current_state = ViewState.SUBTRACT_SELECTION
            self._init_rubberband(event.pos().toPointF())
            self.setInteractive(False)

        # Toggle selection
        elif (
            event.button() == QtCore.Qt.MouseButton.LeftButton
            and event.modifiers() == QtCore.Qt.KeyboardModifier.ShiftModifier
        ):
            self.current_state = ViewState.TOGGLE_SELECTION
            self._init_rubberband(event.pos().toPointF())
            self.setInteractive(False)

        else:
            self.current_state = ViewState.DEFAULT

        super(Nodz, self).mousePressEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Update tablet zoom, canvas dragging and selection.

        """
        # Zoom.
        if self.current_state == ViewState.ZOOM_VIEW:
            offset = self.zoom_initial_pos.x() - event.pos().x()

            if offset > self.previous_mouse_offset:
                self.previous_mouse_offset = offset
                self.zoom_direction = -1
                self.zoom_incr -= 1

            elif offset == self.previous_mouse_offset:
                self.previous_mouse_offset = offset
                if self.zoom_direction == -1:
                    self.zoom_direction = -1
                else:
                    self.zoom_direction = 1

            else:
                self.previous_mouse_offset = offset
                self.zoom_direction = 1
                self.zoom_incr += 1

            if self.zoom_direction == 1:
                zoom_factor = 1.03
            else:
                zoom_factor = 1 / 1.03

            # Perform zoom and re-center on initial click position.
            p_before = self.mapToScene(self.init_mouse_pos)
            self.setTransformationAnchor(
                QtWidgets.QGraphicsView.ViewportAnchor.AnchorViewCenter
            )
            self.scale(zoom_factor, zoom_factor)
            p_after = self.mapToScene(self.init_mouse_pos)
            diff = p_after - p_before

            self.setTransformationAnchor(
                QtWidgets.QGraphicsView.ViewportAnchor.NoAnchor
            )
            self.translate(diff.x(), diff.y())

        # Drag canvas.
        elif self.current_state == ViewState.DRAG_VIEW:
            offset = self.prev_pos - event.pos()
            self.prev_pos = event.pos()
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() + offset.y()
            )
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() + offset.x()
            )

        # RuberBand selection.
        elif (
            self.current_state == ViewState.SELECTION
            or self.current_state == ViewState.ADD_SELECTION
            or self.current_state == ViewState.SUBTRACT_SELECTION
            or self.current_state == ViewState.TOGGLE_SELECTION
        ):
            self.rubberband.setGeometry(
                QtCore.QRect(self.origin.toPoint(), event.pos()).normalized()
            )

        super(Nodz, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Apply tablet zoom, dragging and selection.

        """
        # Zoom the View.
        if self.current_state == ViewState.ZOOM_VIEW:
            self.offset = 0
            self.zoom_direction = 0
            self.zoom_incr = 0
            self.setInteractive(True)

        # Drag View.
        elif self.current_state == ViewState.DRAG_VIEW:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            self.setInteractive(True)

        # Selection.
        elif self.current_state == ViewState.SELECTION:
            self.rubberband.setGeometry(
                QtCore.QRect(self.origin.toPoint(), event.pos()).normalized()
            )
            painter_path = self._releaseRubberband()
            self.setInteractive(True)
            self.scene().setSelectionArea(painter_path)

        # Add Selection.
        elif self.current_state == ViewState.ADD_SELECTION:
            self.rubberband.setGeometry(
                QtCore.QRect(self.origin.toPoint(), event.pos()).normalized()
            )
            painter_path = self._releaseRubberband()
            self.setInteractive(True)
            for item in self.scene().items(painter_path):
                item.setSelected(True)

        # Subtract Selection.
        elif self.current_state == ViewState.SUBTRACT_SELECTION:
            self.rubberband.setGeometry(
                QtCore.QRect(self.origin.toPoint(), event.pos()).normalized()
            )
            painter_path = self._releaseRubberband()
            self.setInteractive(True)
            for item in self.scene().items(painter_path):
                item.setSelected(False)

        # Toggle Selection
        elif self.current_state == ViewState.TOGGLE_SELECTION:
            self.rubberband.setGeometry(
                QtCore.QRect(self.origin.toPoint(), event.pos()).normalized()
            )
            painter_path = self._releaseRubberband()
            self.setInteractive(True)
            for item in self.scene().items(painter_path):
                if item.isSelected():
                    item.setSelected(False)
                else:
                    item.setSelected(True)

        self.current_state = ViewState.DEFAULT

        super(Nodz, self).mouseReleaseEvent(event)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """
        Save pressed key and apply shortcuts.

        Shortcuts are:
        DEL - Delete the selected nodes
        F - Focus view on the selection

        """
        if event.key() not in self.pressed_keys:
            self.pressed_keys.append(event.key())

        if event.key() in (
            QtCore.Qt.Key.Key_Delete,
            QtCore.Qt.Key.Key_Backspace,
        ):
            self._delete_selected_nodes()

        if event.key() == QtCore.Qt.Key.Key_F:
            self._focus()

        if event.key() == QtCore.Qt.Key.Key_A:
            self._frame_all()

        if event.key() == QtCore.Qt.Key.Key_L:
            self._layout_graph()

        if event.key() == QtCore.Qt.Key.Key_S:
            self._node_snap = True

        # Emit signal.
        self.signal_KeyPressed.emit(event.key())

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
        """
        Clear the key from the pressed key list.

        """
        if event.key() == QtCore.Qt.Key.Key_S:
            self._node_snap = False

        if event.key() in self.pressed_keys:
            self.pressed_keys.remove(event.key())

    def _init_rubberband(self, position: QtCore.QPointF) -> None:
        """
        Initialize the rubber band at the given position.

        """
        self.rubberband_start = position  # FIXME: unused ?
        self.origin = position
        self.rubberband.setGeometry(
            QtCore.QRect(self.origin.toPoint(), QtCore.QSize())
        )
        self.rubberband.show()

    def _releaseRubberband(self) -> QtGui.QPainterPath:
        """
        Hide the rubber band and return the path.

        """
        painter_path = QtGui.QPainterPath()
        rect = self.mapToScene(self.rubberband.geometry())
        painter_path.addPolygon(rect)
        self.rubberband.hide()
        return painter_path

    def _focus(self) -> None:
        """
        Center on selected nodes or all of them if no active selection.

        """
        if self.scene().selectedItems():
            items_area = self._get_selection_boundingbox()
        else:
            items_area = self.scene().itemsBoundingRect()
        vp_margins = self.config["viewport_margins"]
        items_area.adjust(
            -vp_margins, -vp_margins - 10, vp_margins, vp_margins
        )
        self.fitInView(items_area, QtCore.Qt.AspectRatioMode.KeepAspectRatio)

    def _frame_all(self) -> None:
        """
        Frame the whole scene, irrespective of the current selection.

        """
        items_area = self.scene().itemsBoundingRect()
        vp_margins = self.config["viewport_margins"]
        items_area.adjust(
            -vp_margins, -vp_margins - 10, vp_margins, vp_margins
        )
        self.fitInView(items_area, QtCore.Qt.AspectRatioMode.KeepAspectRatio)

    def _center_graph_in_scene(self):
        # Center the graph in the scene
        scene_center = self.scene().sceneRect().center()
        graph_center = self.scene().itemsBoundingRect().center()
        offset = scene_center - graph_center
        for node in self.scene_nodes.values():
            node.setPos(node.pos() + offset)
        self.nodz_scene.update_scene()

    def _layout_graph(self):
        """Organize nodes in the graph according to their connections."""
        # Configuration
        h_spacing = self.config["horizontal_node_spacing"]
        v_spacing = self.config["vertical_node_spacing"]

        node_names = list(self.scene_nodes.keys())

        # Find root nodes (nodes without incoming connections)
        root_nodes = [
            node
            for node_name in node_names
            for node in (self.scene_nodes[node_name],)
            if all(len(plug.connections) == 0 for plug in node.plugs.values())
        ]
        nlog.debug(
            f"_layout_graph: root_nodes: {[n.name for n in root_nodes]}"
        )

        # Initialize graph layout data
        graph_depth = [
            [(root_nodes[0], root_nodes[0].base_width, root_nodes[0].height)]
        ]
        scene_height = graph_depth[0][0][
            2
        ]  # Initial height is the root node's height

        level = 0
        while level >= 0:
            has_connections = False
            lheight = 0

            for node, _, hgt in graph_depth[level]:
                lheight += hgt + v_spacing

                for attr, socket in node.sockets.items():
                    if attr not in node.attrs:
                        continue

                    for connection in socket.connections:
                        has_connections = True
                        src_node = connection.plug_item.parentItem()
                        if len(graph_depth) <= level + 1:
                            graph_depth.append([])
                        graph_depth[level + 1].append(
                            (src_node, src_node.base_width, src_node.height)
                        )

            scene_height = max(scene_height, lheight)
            level = level + 1 if has_connections else -1

        nlog.debug(f"_layout_graph: graph_depth = {graph_depth}")

        # Position nodes from bottom to top
        start_pos = h_spacing
        ymax = 0
        positioned_nodes = []

        for i, lst in enumerate(reversed(graph_depth)):
            xpos = start_pos + i * (root_nodes[0].base_width + h_spacing)
            ypos = v_spacing

            for node, _, hgt in lst:
                if node not in positioned_nodes:
                    pos = QtCore.QPointF(xpos, ypos)
                    ypos += hgt + v_spacing
                    node.setPos(pos)
                    positioned_nodes.append(node)
            ymax = max(ymax, ypos)

        for i, node in enumerate(root_nodes[1:]):
            xpos = start_pos + i * (root_nodes[0].base_width + h_spacing)
            node.setPos(xpos, ymax)

        self.nodz_scene.update_scene()
        self._center_graph_in_scene()

    def _get_selection_boundingbox(self) -> QtCore.QRectF:
        """
        Return the bounding box of the selection.

        """
        rect: QtCore.QRectF | None = None
        for item in self.scene().selectedItems():
            if not rect:
                rect = item.sceneBoundingRect()
            else:
                rect = rect.united(item.sceneBoundingRect())
        return rect if rect else QtCore.QRectF()

    def _delete_selected_nodes(self) -> None:
        """
        Delete selected nodes.

        """
        selected_nodes = list()
        for node in self.scene().selectedItems():
            if not isinstance(node, NodeItem):
                raise TypeError(f"Unexpected node type in graph: {node}")
            selected_nodes.append(node.name)
            node._remove()

        # Emit signal.
        self.signal_NodeDeleted.emit(selected_nodes)

    def _return_selection(self) -> None:
        """
        Wrapper to return selected items.

        """
        selected_nodes = list()
        if self.scene().selectedItems():
            for node in self.scene().selectedItems():
                if not isinstance(node, NodeItem):
                    raise TypeError(f"Unexpected node type in graph: {node}")
                selected_nodes.append(node.name)

        # Emit signal.
        self.signal_NodeSelected.emit(selected_nodes)

    ##################################################################
    # API
    ##################################################################

    def load_config(self, file_path: str) -> None:
        """
        Set a specific configuration for this instance of Nodz.

        :type  file_path: str.
        :param file_path: The path to the config file that you want to
                         use.

        """
        self.config = utils._load_config(file_path)

    def initialize(self) -> None:
        """
        Setup the view's behavior.

        """
        # Setup view.
        config = self.config
        self.setRenderHint(
            QtGui.QPainter.RenderHint.Antialiasing, config["antialiasing"]
        )
        self.setRenderHint(
            QtGui.QPainter.RenderHint.TextAntialiasing, config["antialiasing"]
        )
        self.setRenderHint(
            QtGui.QPainter.RenderHint.SmoothPixmapTransform,
            config["smooth_pixmap"],
        )
        self.setViewportUpdateMode(
            QtWidgets.QGraphicsView.ViewportUpdateMode.FullViewportUpdate
        )
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.rubberband = QtWidgets.QRubberBand(
            QtWidgets.QRubberBand.Shape.Rectangle, self
        )

        # Setup scene.
        scene = NodeScene(self)
        scene_width = config["scene_width"]
        scene_height = config["scene_height"]
        scene.setSceneRect(0, 0, scene_width, scene_height)
        self.setScene(scene)
        # Connect scene node moved signal
        scene.signal_NodeMoved.connect(self.signal_NodeMoved)

        # Tablet zoom.
        self.previous_mouse_offset = 0
        self.zoom_direction = 0
        self.zoom_incr = 0

        # Connect signals.
        self.scene().selectionChanged.connect(self._return_selection)

    # NODES
    def create_node(
        self,
        name: str = "default",
        preset: str = "node_default",
        position: QtCore.QPointF | None = None,
        alternate: bool = True,
    ) -> NodeItem:
        """
        Create a new node with a given name, position and color.

        :type  name: str.
        :param name: The name of the node. The name has to be unique
                     as it is used as a key to store the node object.

        :type  preset: str.
        :param preset: The name of graphical preset in the config file.

        :type  position: QtCore.QPoint.
        :param position: The position of the node once created. If None,
                         it will be created at the center of the scene.

        :type  alternate: bool.
        :param alternate: The attribute color alternate state, if True,
                          every 2 attribute the color will be slightly
                          darker.

        :return : The created node

        """
        # Check for name clashes
        if name in self.scene_nodes.keys():
            raise NameError(
                f"A node with the same name already exists : {name}"
            )

        node_item = NodeItem(
            name=name,
            alternate=alternate,
            preset=preset,
            config=self.config,
        )

        # Store node in scene.
        self.scene_nodes[name] = node_item

        if not position:
            # Get the center of the view.
            position = self.mapToScene(self.viewport().rect().center())

        # Set node position.
        self.scene().addItem(node_item)
        node_item.setPos(position - node_item.node_center)

        # Emit signal.
        self.signal_NodeCreated.emit(name)

        return node_item

    def delete_node(self, node: NodeItem) -> None:
        """
        Delete the specified node from the view.

        :type  node: class.
        :param node: The node instance that you want to delete.

        """
        if node not in self.scene_nodes.values():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Node deletion aborted !")
            return

        if node in self.scene_nodes.values():
            node_name = node.name
            node._remove()

            # Emit signal.
            self.signal_NodeDeleted.emit([node_name])

    def edit_node(self, node, new_name: str | None = None) -> None:
        """
        Rename an existing node.

        :type  node: class.
        :param node: The node instance that you want to delete.

        :type  new_name: str.
        :param new_name: The new name for the given node.

        """
        if node not in self.scene_nodes.values():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Node edition aborted !")
            return

        old_name = node.name

        if new_name is not None:
            # Check for name clashes
            if new_name in self.scene_nodes.keys():
                nlog.error(
                    f"A node with the same name already exists : {new_name}"
                )
                nlog.error("Node edition aborted !")
                return
            else:
                node.name = new_name

        # Replace node data.
        self.scene_nodes[new_name] = self.scene_nodes[old_name]
        self.scene_nodes.pop(old_name)

        # Store new node name in the connections
        if node.sockets:
            for socket in node.sockets.values():
                for connection in socket.connections:
                    connection.socketNode = new_name

        if node.plugs:
            for plug in node.plugs.values():
                for connection in plug.connections:
                    connection.plugNode = new_name

        node.update()

        # Emit signal.
        self.signal_NodeEdited.emit(old_name, new_name)

    # ATTRS
    def create_attribute(
        self,
        node: NodeItem,
        name: str = "default",
        index: int = -1,
        preset: str = "attr_default",
        plug: bool = True,
        socket: bool = True,
        data_type: Any = None,
        plug_max_connections: int = -1,
        socket_max_connections: int = 1,
    ) -> None:
        """
        Create a new attribute with a given name.

        :type  node: class.
        :param node: The node instance that you want to delete.

        :type  name: str.
        :param name: The name of the attribute. The name has to be
                     unique as it is used as a key to store the node
                     object.

        :type  index: int.
        :param index: The index of the attribute in the node.

        :type  preset: str.
        :param preset: The name of graphical preset in the config file.

        :type  plug: bool.
        :param plug: Whether or not this attribute can emit connections.

        :type  socket: bool.
        :param socket: Whether or not this attribute can receive
                       connections.

        :type  data_type: type.
        :param data_type: Type of the data represented by this attribute
                         in order to highlight attributes of the same
                         type while performing a connection.

        :type  plug_max_connections: int.
        :param plug_max_connections: The maximum connections that the plug can have (-1 for infinite).

        :type  socket_max_connections: int.
        :param socket_max_connections: The maximum connections that the socket can have (-1 for infinite).

        """
        if node not in self.scene_nodes.values():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Attribute creation aborted !")
            return

        if name in node.attrs:
            nlog.error(
                f"An attribute with the same name already exists : {name}"
            )
            nlog.error("Attribute creation aborted !")
            return

        node._create_attribute(
            name=name,
            index=index,
            preset=preset,
            plug=plug,
            socket=socket,
            data_type=data_type,
            plug_max_connections=plug_max_connections,
            socket_max_connections=socket_max_connections,
        )

        # Emit signal.
        self.signal_AttrCreated.emit(node.name, index)

    def delete_attribute(self, node: NodeItem, index: int) -> None:
        """
        Delete the specified attribute.

        :type  node: class.
        :param node: The node instance that you want to delete.

        :type  index: int.
        :param index: The index of the attribute in the node.

        """
        if node not in self.scene_nodes.values():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Attribute deletion aborted !")
            return

        node._delete_attribute(index)

        # Emit signal.
        self.signal_AttrDeleted.emit(node.name, index)

    def edit_attribute(
        self,
        node: NodeItem,
        index: int,
        new_name: str | None = None,
        new_index: int | None = None,
    ) -> None:
        """
        Edit the specified attribute.

        :type  node: class.
        :param node: The node instance that you want to delete.

        :type  index: int.
        :param index: The index of the attribute in the node.

        :type  new_name: str.
        :param new_name: The new name for the given attribute.

        :type  new_index: int.
        :param new_index: The index for the given attribute.

        """
        if node not in self.scene_nodes.values():
            nlog.error(f"Node object {node} does not exist !")
            nlog.error("Attribute creation aborted !")
            return

        if new_name is not None:
            if new_name in node.attrs:
                nlog.error(
                    f"An attribute with the same name already exists : {new_name}"
                )
                nlog.error("Attribute edition aborted !")
                return
            else:
                old_name = node.attrs[index]

            # Rename in the slot item(s).
            if node.attrs_data[old_name]["plug"]:
                node.plugs[old_name].attribute = new_name
                node.plugs[new_name] = node.plugs[old_name]
                node.plugs.pop(old_name)
                for connection in node.plugs[new_name].connections:
                    connection.plugAttr = new_name

            if node.attrs_data[old_name]["socket"]:
                node.sockets[old_name].attribute = new_name
                node.sockets[new_name] = node.sockets[old_name]
                node.sockets.pop(old_name)
                for connection in node.sockets[new_name].connections:
                    connection.socketAttr = new_name

            # Replace attribute data.
            node.attrs_data[old_name]["name"] = new_name
            node.attrs_data[new_name] = node.attrs_data[old_name]
            node.attrs_data.pop(old_name)
            node.attrs[index] = new_name

        if isinstance(new_index, int):
            utils._swap_list_indices(node.attrs, index, new_index)

            # Refresh connections.
            for plug in node.plugs.values():
                plug.update()
                if plug.connections:
                    for connection in plug.connections:
                        if isinstance(connection.source, PlugItem):
                            connection.source = plug
                            connection.source_point = plug.center()
                        else:
                            connection.target = plug
                            connection.target_point = plug.center()
                        if new_name:
                            connection.plugAttr = new_name
                        connection.updatePath()

            for socket in node.sockets.values():
                socket.update()
                if socket.connections:
                    for connection in socket.connections:
                        if isinstance(connection.source, SocketItem):
                            connection.source = socket
                            connection.source_point = socket.center()
                        else:
                            connection.target = socket
                            connection.target_point = socket.center()
                        if new_name:
                            connection.socketAttr = new_name
                        connection.updatePath()

            self.scene().update()

        node.update()

        # Emit signal.
        if new_index:
            self.signal_AttrEdited.emit(node.name, index, new_index)
        else:
            self.signal_AttrEdited.emit(node.name, index, index)

    # GRAPH
    def save_graph(self, file_path: str = "path") -> None:
        """
        Get all the current graph infos and store them in a .json file
        at the given location.

        :type  file_path: str.
        :param file_path: The path where you want to save your graph at.

        """
        data = dict()

        # Store nodes data.
        data["NODES"] = dict()

        nodes = self.scene_nodes.keys()
        for node in nodes:
            node_inst = self.scene_nodes[node]
            preset = node_inst.node_preset
            node_alternate = node_inst.alternate

            data["NODES"][node] = {
                "preset": preset,
                "position": [node_inst.pos().x(), node_inst.pos().y()],
                "alternate": node_alternate,
                "attributes": [],
            }

            attrs = node_inst.attrs
            for attr in attrs:
                attr_data = node_inst.attrs_data[attr]

                # serialize data_type if needed.
                if isinstance(attr_data["dataType"], type):
                    attr_data["dataType"] = str(attr_data["dataType"])

                data["NODES"][node]["attributes"].append(attr_data)

        # Store connections data.
        data["CONNECTIONS"] = self.evaluate_graph()

        # Save data.
        try:
            utils._save_data(file_path=file_path, data=data)
        except BaseException:
            raise FileNotFoundError(f"Invalid path : {file_path}")

        # Emit signal.
        self.signal_GraphSaved.emit()

    def load_graph(self, file_path: str = "path") -> None:
        """
        Get all the stored info from the .json file at the given location
        and recreate the graph as saved.

        :type  file_path: str.
        :param file_path: The path where you want to load your graph from.

        """
        # Load data.
        if os.path.exists(file_path):
            data = utils._load_data(file_path=file_path)
        else:
            raise FileNotFoundError(f"Invalid path : {file_path}")

        # Apply nodes data.
        nodes_data = data["NODES"]
        nodes_name = nodes_data.keys()

        for name in nodes_name:
            preset = nodes_data[name]["preset"]
            position = nodes_data[name]["position"]
            position = QtCore.QPointF(position[0], position[1])
            alternate = nodes_data[name]["alternate"]

            node = self.create_node(
                name=name,
                preset=preset,
                position=position,
                alternate=alternate,
            )

            if node is None:
                nlog.warning(f"Not loading node {name}.")
                continue

            # Apply attributes data.
            attrs_data = nodes_data[name]["attributes"]

            for attr_data in attrs_data:
                index = attrs_data.index(attr_data)
                name = attr_data["name"]
                plug = attr_data["plug"]
                socket = attr_data["socket"]
                preset = attr_data["preset"]
                data_type = attr_data["dataType"]
                plug_max_connections = attr_data["plugMaxConnections"]
                socket_max_connections = attr_data["socketMaxConnections"]

                # un-serialize data type if needed
                if isinstance(data_type, str) and data_type.find("<") == 0:
                    data_type = eval(str(data_type.split("'")[1]))

                self.create_attribute(
                    node=node,
                    name=name,
                    index=index,
                    preset=preset,
                    plug=plug,
                    socket=socket,
                    data_type=data_type,
                    plug_max_connections=plug_max_connections,
                    socket_max_connections=socket_max_connections,
                )

        # Apply connections data.
        connections_data = data["CONNECTIONS"]

        for connection in connections_data:
            source = connection[0]
            source_node = source.split(".")[0]
            source_attr = source.split(".")[1]

            target = connection[1]
            target_node = target.split(".")[0]
            target_attr = target.split(".")[1]

            self.create_connection(
                source_node, source_attr, target_node, target_attr
            )

        self.scene().update()

        # Emit signal.
        self.signal_GraphLoaded.emit()

    def create_connection(
        self,
        source_node: str,
        source_attr: str,
        target_node: str,
        target_attr: str,
    ) -> ConnectionItem:
        """
        Create a manual connection.

        :type  source_node: str.
        :param source_node: Node that emits the connection.

        :type  source_attr: str.
        :param source_attr: Attribute that emits the connection.

        :type  target_node: str.
        :param target_node: Node that receives the connection.

        :type  target_attr: str.
        :param target_attr: Attribute that receives the connection.

        """
        plug = self.scene_nodes[source_node].plugs[source_attr]
        socket = self.scene_nodes[target_node].sockets[target_attr]

        connection = ConnectionItem(
            plug.center(), socket.center(), plug, socket
        )

        connection.plug_node = plug.parentItem().name
        connection.plug_attr = plug.attribute
        connection.socket_node = socket.parentItem().name
        connection.socket_attr = socket.attribute

        plug.connect(socket, connection)
        socket.connect(plug, connection)

        connection.update_path()

        self.scene().addItem(connection)

        return connection

    def evaluate_graph(self) -> list:
        """
        Create a list of connection tuples.
        [("sourceNode.attribute", "TargetNode.attribute"), ...]

        """
        scene = self.scene()

        data = list()

        for item in scene.items():
            if isinstance(item, ConnectionItem):
                connection = item

                data.append(connection._output_connection_data())

        # Emit Signal
        self.signal_GraphEvaluated.emit()

        return data

    def clear_graph(self) -> None:
        """
        Clear the graph.

        """
        self.scene().clear()
        self.scene_nodes = dict()

        # Emit signal.
        self.signal_GraphCleared.emit()

    ##################################################################
    # END API
    ##################################################################


class NodeScene(QtWidgets.QGraphicsScene):
    """
    The scene displaying all the nodes.

    """

    signal_NodeMoved = QtCore.Signal(str, object)  # type: ignore (qtpy)

    def __init__(self, parent) -> None:
        """
        Initialize the class.

        """
        super(NodeScene, self).__init__(parent)

        # General.
        self.grid_size = parent.config["grid_size"]

        # Nodes storage.
        self.nodes = dict()

    @property
    def nodz_instance(self) -> Nodz:
        try:
            view = self.views()[0]
        except BaseException as err:
            raise RuntimeError(f"Could not get first scene view: {err} ")
        else:
            if isinstance(view, Nodz):
                return view
            else:
                raise TypeError(f"Unexpected view type: {view}")

    def dragEnterEvent(
        self,
        event: QtWidgets.QGraphicsSceneDragDropEvent,
    ) -> None:
        """
        Make the dragging of nodes into the scene possible.

        """
        event.setDropAction(QtCore.Qt.DropAction.MoveAction)
        event.accept()

    def dragMoveEvent(
        self,
        event: QtWidgets.QGraphicsSceneDragDropEvent,
    ) -> None:
        """
        Make the dragging of nodes into the scene possible.

        """
        event.setDropAction(QtCore.Qt.DropAction.MoveAction)
        event.accept()

    def dropEvent(
        self,
        event: QtWidgets.QGraphicsSceneDragDropEvent,
    ) -> None:
        """
        Create a node from the dropped item.

        """
        # Emit signal.
        if self.views():
            self.nodz_instance.signal_Dropped.emit(event.scenePos())

        event.accept()

    def drawBackground(
        self,
        painter: QtGui.QPainter,
        rect: QtCore.QRect | QtCore.QRectF,
    ) -> None:
        """
        Draw a grid in the background.

        """
        config = self.nodz_instance.config

        self._brush = QtGui.QBrush()
        self._brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self._brush.setColor(utils._convert_data_to_color(config["bg_color"]))

        painter.fillRect(rect, self._brush)

        if self.nodz_instance.grid_vis_toggle:
            left_line = rect.left() - rect.left() % self.grid_size
            top_line = rect.top() - rect.top() % self.grid_size
            lines = list()

            i = int(left_line)
            while i < int(rect.right()):
                lines.append(QtCore.QLineF(i, rect.top(), i, rect.bottom()))
                i += self.grid_size

            u = int(top_line)
            while u < int(rect.bottom()):
                lines.append(QtCore.QLineF(rect.left(), u, rect.right(), u))
                u += self.grid_size

            self.pen = QtGui.QPen()
            self.pen.setColor(
                utils._convert_data_to_color(config["grid_color"])
            )
            self.pen.setWidth(0)
            painter.setPen(self.pen)
            painter.drawLines(lines)

    def update_scene(self) -> None:
        """
        Update the connections position.

        """
        for connection in [
            i for i in self.items() if isinstance(i, ConnectionItem)
        ]:
            if not connection.target:
                raise RuntimeError("connection.target is invalid")
            connection.target_point = connection.target.center()
            if not connection.source:
                raise RuntimeError("connection.source is invalid")
            connection.source_point = connection.source.center()
            connection.update_path()


class NodeItem(QtWidgets.QGraphicsItem):
    """
    A graphic representation of a node containing attributes.

    """

    def __init__(
        self, name: str, alternate: bool, preset: str, config: dict
    ) -> None:
        """
        Initialize the class.

        :type  name: str.
        :param name: The name of the node. The name has to be unique
                     as it is used as a key to store the node object.

        :type  alternate: bool.
        :param alternate: The attribute color alternate state, if True,
                          every 2 attribute the color will be slightly
                          darker.

        :type  preset: str.
        :param preset: The name of graphical preset in the config file.

        """
        super(NodeItem, self).__init__()

        self.setZValue(1)

        # Storage
        self.name = name
        self.alternate = alternate
        self.node_preset = preset
        self.attr_preset = None

        # Attributes storage.
        self.attrs = list()
        self.attrs_data = dict()
        self.attr_count = 0

        self.plugs = dict()
        self.sockets = dict()

        # Methods.
        self._create_style(config)

    @property
    def nodz_instance(self) -> Nodz:
        return _nodz_instance(self)

    @property
    def nodz_scene(self) -> NodeScene:
        return _nodz_scene(self)

    @property
    def scene_nodes(self):
        return self.nodz_scene.nodes

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

    def _create_style(self, config: dict) -> None:
        """
        Read the node style from the configuration file.

        """
        self.setAcceptHoverEvents(True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

        # Dimensions.
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
            utils._convert_data_to_color(config[self.node_preset]["bg"])
        )

        self._pen = QtGui.QPen()
        self._pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
        self._pen.setWidth(self.border)
        self._pen.setColor(
            utils._convert_data_to_color(config[self.node_preset]["border"])
        )

        self._pen_sel = QtGui.QPen()
        self._pen_sel.setStyle(QtCore.Qt.PenStyle.SolidLine)
        self._pen_sel.setWidth(self.border)
        self._pen_sel.setColor(
            utils._convert_data_to_color(
                config[self.node_preset]["border_sel"]
            )
        )

        self._text_pen = QtGui.QPen()
        self._text_pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
        self._text_pen.setColor(
            utils._convert_data_to_color(config[self.node_preset]["text"])
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
    ) -> None:
        """
        Create an attribute by expanding the node, adding a label and
        connection items.

        :type  name: str.
        :param name: The name of the attribute. The name has to be
                     unique as it is used as a key to store the node
                     object.

        :type  index: int.
        :param index: The index of the attribute in the node.

        :type  preset: str.
        :param preset: The name of graphical preset in the config file.

        :type  plug: bool.
        :param plug: Whether or not this attribute can emit connections.

        :type  socket: bool.
        :param socket: Whether or not this attribute can receive
                       connections.

        :type  data_type: type.
        :param data_type: Type of the data represented by this attribute
                         in order to highlight attributes of the same
                         type while performing a connection.

        """
        if name in self.attrs:
            nlog.error(
                "An attribute with the same name already exists on this "
                f"node : {name}"
            )
            nlog.error("Attribute creation aborted !")
            return

        self.attr_preset = preset

        # Create a plug connection item.
        if plug:
            plug_inst = PlugItem(
                parent=self,
                attribute=name,
                index=self.attr_count,
                preset=preset,
                data_type=data_type,
                max_connections=plug_max_connections,
            )

            self.plugs[name] = plug_inst

        # Create a socket connection item.
        if socket:
            socket_inst = SocketItem(
                parent=self,
                attribute=name,
                index=self.attr_count,
                preset=preset,
                data_type=data_type,
                max_connections=socket_max_connections,
            )

            self.sockets[name] = socket_inst

        self.attr_count += 1

        # Add the attribute based on its index.
        if index == -1 or index > self.attr_count:
            self.attrs.append(name)
        else:
            self.attrs.insert(index, name)

        # Store attr data.
        self.attrs_data[name] = {
            "name": name,
            "socket": socket,
            "plug": plug,
            "preset": preset,
            "dataType": data_type,
            "plugMaxConnections": plug_max_connections,
            "socketMaxConnections": socket_max_connections,
        }

        # Update node height.
        self.update()

    def _delete_attribute(self, index: int) -> None:
        """
        Remove an attribute by reducing the node, removing the label
        and the connection items.

        :type  index: int.
        :param index: The index of the attribute in the node.

        """
        name = self.attrs[index]

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

        # Reduce node height.
        if self.attr_count > 0:
            self.attr_count -= 1

        # Remove attribute from node.
        if name in self.attrs:
            self.attrs.remove(name)

        self.update()

    def _remove(self) -> None:
        """
        Remove this node instance from the scene.

        Make sure that all the connections to this node are also removed
        in the process

        """
        self.scene_nodes.pop(self.name)

        # Remove all sockets connections.
        for socket in self.sockets.values():
            while len(socket.connections) > 0:
                socket.connections[0]._remove()

        # Remove all plugs connections.
        for plug in self.plugs.values():
            while len(plug.connections) > 0:
                plug.connections[0]._remove()

        # Remove node.
        scene = self.scene()
        scene.removeItem(self)
        scene.update()

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

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionGraphicsItem,
        widget: QtWidgets.QWidget | None = None,
    ) -> None:
        """
        Paint the node and attributes.

        """
        # Node base.
        painter.setBrush(self._brush)
        painter.setPen(self.pen)

        painter.drawRoundedRect(
            0, 0, self.base_width, self.height, self.radius, self.radius
        )

        # Node label.
        painter.setPen(self._text_pen)
        painter.setFont(self._node_text_font)

        metrics = QtGui.QFontMetrics(painter.font())
        text_width = metrics.boundingRect(self.name).width() + 14
        text_height = metrics.boundingRect(self.name).height() + 14
        margin = (text_width - self.base_width) * 0.5
        text_rect = QtCore.QRect(
            -margin, -text_height, text_width, text_height
        )

        painter.drawText(
            text_rect, QtCore.Qt.AlignmentFlag.AlignCenter, self.name
        )

        # Attributes.
        offset = 0
        nodz_inst = self.nodz_instance
        config = self.nodz_instance.config

        for attr in self.attrs:
            # Attribute rect.
            rect = QtCore.QRect(
                self.border / 2,
                self.base_height - self.radius + offset,
                self.base_width - self.border,
                self.attr_height,
            )

            attr_data = self.attrs_data[attr]
            name = attr

            preset = attr_data["preset"]

            # Attribute base.
            self._attr_brush.setColor(
                utils._convert_data_to_color(config[preset]["bg"])
            )
            if self.alternate:
                self._attr_brush_alt.setColor(
                    utils._convert_data_to_color(
                        config[preset]["bg"], True, config["alternate_value"]
                    )
                )

            self._attr_pen.setColor(utils._convert_data_to_color([0, 0, 0, 0]))
            painter.setPen(self._attr_pen)
            painter.setBrush(self._attr_brush)
            if (offset / self.attr_height) % 2:
                painter.setBrush(self._attr_brush_alt)

            painter.drawRect(rect)

            # Attribute label.
            painter.setPen(
                utils._convert_data_to_color(config[preset]["text"])
            )
            painter.setFont(self._attr_text_font)

            # Search non-connectable attributes.
            if nodz_inst.drawing_connection:
                if self == nodz_inst.current_hovered_node:
                    if not nodz_inst.source_slot:
                        raise TypeError("Invalid source_slot")
                    if attr_data[
                        "dataType"
                    ] != nodz_inst.source_slot.data_type or (
                        nodz_inst.source_slot.slot_type == "plug"
                        and attr_data["socket"] is False
                        or nodz_inst.source_slot.slot_type == "socket"
                        and attr_data["plug"] is False
                    ):
                        # Set non-connectable attributes color.
                        painter.setPen(
                            utils._convert_data_to_color(
                                config["non_connectable_color"]
                            )
                        )

            text_rect = QtCore.QRect(
                rect.left() + self.radius,
                rect.top(),
                rect.width() - 2 * self.radius,
                rect.height(),
            )
            painter.drawText(
                text_rect, QtCore.Qt.AlignmentFlag.AlignVCenter, name
            )

            offset += self.attr_height

    def mousePressEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Keep the selected node on top of the others.

        """
        nodes = self.scene_nodes
        for node in nodes.values():
            node.setZValue(1)

        for item in self.scene().items():
            if isinstance(item, ConnectionItem):
                item.setZValue(1)

        self.setZValue(2)

        super(NodeItem, self).mousePressEvent(event)

    def mouseDoubleClickEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Emit a signal.

        """
        super(NodeItem, self).mouseDoubleClickEvent(event)
        self.nodz_instance.signal_NodeDoubleClicked.emit(self.name)

    def mouseMoveEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        .

        """
        nodz_inst = self.nodz_instance
        if nodz_inst.grid_vis_toggle:
            if nodz_inst.grid_snap_toggle or nodz_inst._node_snap:
                grid_size = self.nodz_scene.grid_size

                current_pos = self.mapToScene(
                    event.pos().x() - self.base_width / 2,
                    event.pos().y() - self.height / 2,
                )

                snap_x = (
                    round(current_pos.x() / grid_size) * grid_size
                ) - grid_size / 4
                snap_y = (
                    round(current_pos.y() / grid_size) * grid_size
                ) - grid_size / 4
                snap_pos = QtCore.QPointF(snap_x, snap_y)
                self.setPos(snap_pos)

                self.nodz_scene.update_scene()
            else:
                self.nodz_scene.update_scene()
                super(NodeItem, self).mouseMoveEvent(event)

    def mouseReleaseEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        .

        """
        # Emit node moved signal.
        self.nodz_scene.signal_NodeMoved.emit(self.name, self.pos())
        super(NodeItem, self).mouseReleaseEvent(event)

    def hoverLeaveEvent(
        self, event: QtWidgets.QGraphicsSceneHoverEvent
    ) -> None:
        """
        .

        """
        for item in self.nodz_instance.scene().items():
            if isinstance(item, ConnectionItem):
                item.setZValue(0)

        super(NodeItem, self).hoverLeaveEvent(event)


class SlotItem(QtWidgets.QGraphicsItem):
    """
    The base class for graphics item representing attributes hook.

    """

    def __init__(
        self,
        parent: QtWidgets.QGraphicsItem,
        attribute: str,
        preset: str,
        index: int,
        data_type: Any,
        max_connections: int,
    ) -> None:
        """
        Initialize the class.

        :param parent: The parent item of the slot.
        :type  parent: QtWidgets.QGraphicsItem instance.

        :param attribute: The attribute associated to the slot.
        :type  attribute: String.

        :param index: int.
        :type  index: The index of the attribute in the node.

        :type  preset: str.
        :param preset: The name of graphical preset in the config file.

        :param data_type: The data type associated to the attribute.
        :type  data_type: Type.

        """
        super(SlotItem, self).__init__(parent)

        # Status.
        self.setAcceptHoverEvents(True)

        # Storage.
        self.slot_type = None
        self.attribute = attribute
        self.preset = preset
        self.index = index
        self.data_type = data_type

        # Style.
        self.brush = QtGui.QBrush()
        self.brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)

        self.pen = QtGui.QPen()
        self.pen.setStyle(QtCore.Qt.PenStyle.SolidLine)

        # Connections storage.
        self.connected_slots = list()
        self.new_connection = None
        self.connections = list()
        self.max_connections = max_connections

    @property
    def nodz_instance(self) -> Nodz:
        return _nodz_instance(self)

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
        if slot_item.data_type != self.data_type:
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
            self.new_connection = ConnectionItem(
                self.center().toPoint(),
                self.mapToScene(event.pos()).toPoint(),
                self,
                None,
            )

            self.connections.append(self.new_connection)
            self.scene().addItem(self.new_connection)

            nodz_inst = self.nodz_instance
            nodz_inst.drawing_connection = True
            nodz_inst.source_slot = self
        else:
            super(SlotItem, self).mousePressEvent(event)

    def mouseMoveEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Update the new connection's end point position.

        """
        nodz_inst = self.nodz_instance
        config = nodz_inst.config
        if nodz_inst.drawing_connection:
            mbb = utils._create_pointer_bounding_box(
                pointer_pos=event.scenePos().toPoint(),
                bb_size=config["mouse_bounding_box"],
            )

            # Get nodes in pointer's bounding box.
            targets = self.scene().items(mbb)

            if any(isinstance(target, NodeItem) for target in targets):
                if self.parentItem() not in targets:
                    for target in targets:
                        if isinstance(target, NodeItem):
                            nodz_inst.current_hovered_node = target
            else:
                nodz_inst.current_hovered_node = None

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
        nodz_inst = self.nodz_instance
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            nodz_inst.drawing_connection = False

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

        nodz_inst.current_hovered_node = None

    def shape(self) -> QtGui.QPainterPath:
        """
        The shape of the Slot is a circle.

        """
        path = QtGui.QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionGraphicsItem,
        widget: QtWidgets.QWidget | None = None,
    ) -> None:
        """
        Paint the Slot.

        """
        painter.setBrush(self.brush)
        painter.setPen(self.pen)

        nodz_inst = self.nodz_instance
        config = nodz_inst.config
        if nodz_inst.drawing_connection:
            if self.parentItem() == nodz_inst.current_hovered_node:
                painter.setBrush(
                    utils._convert_data_to_color(
                        config["non_connectable_color"]
                    )
                )
                if not nodz_inst.source_slot:
                    raise TypeError("Invalid source_slot")
                if self.slot_type == nodz_inst.source_slot.slot_type or (
                    self.slot_type != nodz_inst.source_slot.slot_type
                    and self.data_type != nodz_inst.source_slot.data_type
                ):
                    painter.setBrush(
                        utils._convert_data_to_color(
                            config["non_connectable_color"]
                        )
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
        rect = self.boundingRect()
        center = QtCore.QPointF(
            rect.x() + rect.width() * 0.5, rect.y() + rect.height() * 0.5
        )

        return self.mapToScene(center)


class PlugItem(SlotItem):
    """
    A graphics item representing an attribute out hook.

    """

    def __init__(
        self,
        parent: QtWidgets.QGraphicsItem,
        attribute: str,
        index: int,
        preset: str,
        data_type: Any,
        max_connections: int,
    ) -> None:
        """
        Initialize the class.

        :param parent: The parent item of the slot.
        :type  parent: QtWidgets.QGraphicsItem instance.

        :param attribute: The attribute associated to the slot.
        :type  attribute: String.

        :param index: int.
        :type  index: The index of the attribute in the node.

        :type  preset: str.
        :param preset: The name of graphical preset in the config file.

        :param data_type: The data type associated to the attribute.
        :type  data_type: Type.

        """
        super(PlugItem, self).__init__(
            parent, attribute, preset, index, data_type, max_connections
        )

        # Storage.
        self.attributte = attribute
        self.preset = preset
        self.slot_type = "plug"

        # Methods.
        self._create_style(parent)

    def _create_style(self, parent: QtWidgets.QGraphicsItem) -> None:
        """
        Read the attribute style from the configuration file.

        """
        config = self.nodz_instance.config
        self.brush = QtGui.QBrush()
        self.brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self.brush.setColor(
            utils._convert_data_to_color(config[self.preset]["plug"])
        )

    def boundingRect(self) -> QtCore.QRectF:
        """
        The bounding rect based on the width and height variables.

        """
        width = height = self.parent_node_item().attr_height / 2.0
        config = self.nodz_instance.config

        x = self.parent_node_item().base_width - (width / 2.0)
        y = (
            self.parent_node_item().base_height
            - config["node_radius"]
            + self.parent_node_item().attr_height / 4
            + self.parent_node_item().attrs.index(self.attribute)
            * self.parent_node_item().attr_height
        )

        rect = QtCore.QRect(x, y, width, height).toRectF()
        return rect

    def connect(self, item: SocketItem, connection: ConnectionItem) -> None:
        """
        Connect to the given socket_item.

        """
        if (
            self.max_connections > 0
            and len(self.connected_slots) >= self.max_connections
        ):
            # Already connected.
            self.connections[self.max_connections - 1]._remove()

        # Populate connection.
        connection.socket_item = item
        connection.plug_node = self.parent_node_item().name
        connection.plug_attr = self.attribute

        # Add socket to connected slots.
        if item in self.connected_slots:
            self.connected_slots.remove(item)
        self.connected_slots.append(item)

        # Add connection.
        if connection not in self.connections:
            self.connections.append(connection)

        # Emit signal.
        self.nodz_instance.signal_PlugConnected.emit(
            connection.plug_node,
            connection.plug_attr,
            connection.socket_node,
            connection.socket_attr,
        )

    def disconnect(self, connection: ConnectionItem) -> None:
        """
        Disconnect the given connection from this plug item.

        """
        # Emit signal.
        self.nodz_instance.signal_PlugDisconnected.emit(
            connection.plug_node,
            connection.plug_attr,
            connection.socket_node,
            connection.socket_attr,
        )

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
        attribute: str,
        index: int,
        preset: str,
        data_type: Any,
        max_connections: int,
    ) -> None:
        """
        Initialize the socket.

        :param parent: The parent item of the slot.
        :type  parent: QtWidgets.QGraphicsItem instance.

        :param attribute: The attribute associated to the slot.
        :type  attribute: String.

        :param index: int.
        :type  index: The index of the attribute in the node.

        :type  preset: str.
        :param preset: The name of graphical preset in the config file.

        :param data_type: The data type associated to the attribute.
        :type  data_type: Type.

        """
        super(SocketItem, self).__init__(
            parent, attribute, preset, index, data_type, max_connections
        )

        # Storage.
        self.attributte = attribute
        self.preset = preset
        self.slot_type = "socket"

        # Methods.
        self._create_style(parent)

    def _create_style(self, parent: QtWidgets.QGraphicsItem) -> None:
        """
        Read the attribute style from the configuration file.

        """
        config = self.nodz_instance.config
        self.brush = QtGui.QBrush()
        self.brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self.brush.setColor(
            utils._convert_data_to_color(config[self.preset]["socket"])
        )

    def boundingRect(self) -> QtCore.QRectF:
        """
        The bounding rect based on the width and height variables.

        """
        width = height = self.parent_node_item().attr_height / 2.0
        config = self.nodz_instance.config

        x = -width / 2.0
        y = (
            self.parent_node_item().base_height
            - config["node_radius"]
            + (self.parent_node_item().attr_height / 4)
            + self.parent_node_item().attrs.index(self.attribute)
            * self.parent_node_item().attr_height
        )

        rect = QtCore.QRect(x, y, width, height).toRectF()
        return rect

    def connect(self, item: PlugItem, connection: ConnectionItem) -> None:
        """
        Connect to the given plug item.

        """
        if (
            self.max_connections > 0
            and len(self.connected_slots) >= self.max_connections
        ):
            # Already connected.
            self.connections[self.max_connections - 1]._remove()

        # Populate connection.
        connection.plug_item = item
        connection.socket_node = self.parent_node_item().name
        connection.socket_attr = self.attribute

        # Add plug to connected slots.
        self.connected_slots.append(item)

        # Add connection.
        if connection not in self.connections:
            self.connections.append(connection)

        # Emit signal.
        self.nodz_instance.signal_SocketConnected.emit(
            connection.plug_node,
            connection.plug_attr,
            connection.socket_node,
            connection.socket_attr,
        )

    def disconnect(self, connection: ConnectionItem) -> None:
        """
        Disconnect the given connection from this socket item.

        """
        # Emit signal.
        self.nodz_instance.signal_SocketDisconnected.emit(
            connection.plug_node,
            connection.plug_attr,
            connection.socket_node,
            connection.socket_attr,
        )

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
        target: SlotItem | None,
    ) -> None:
        """
        Initialize the class.

        :param source_point: Source position of the connection.
        :type  source_point: QPoint.

        :param target_point: Target position of the connection
        :type  target_point: QPoint.

        :param source: Source item (plug or socket).
        :type  source: class.

        :param target: Target item (plug or socket).
        :type  target: class.

        """
        super(ConnectionItem, self).__init__()

        self.setZValue(1)

        # Storage.
        self.socket_node: str | None = None
        self.socket_attr: str | None = None
        self.plug_node: str | None = None
        self.plug_attr: str | None = None

        self.source_point = source_point
        self.target_point = target_point
        self.source = source
        self.target = target

        self.plug_item: PlugItem | None = None
        self.socket_item: SocketItem | None = None

        self.movable_point = None

        # Methods.
        self._create_style()

    @property
    def nodz_instance(self) -> Nodz:
        return _nodz_instance(self)

    def _create_style(self) -> None:
        """
        Read the connection style from the configuration file.

        """
        if not self.source:
            raise RuntimeError("source is invalid")
        config = self.source.nodz_instance.config
        self.setAcceptHoverEvents(True)
        self.setZValue(-1)

        self._pen = QtGui.QPen(
            utils._convert_data_to_color(config["connection_color"])
        )
        self._pen.setWidth(config["connection_width"])

    def _output_connection_data(self) -> tuple[str, str]:
        """
        .

        """
        return (
            "{0}.{1}".format(self.plug_node, self.plug_attr),
            "{0}.{1}".format(self.socket_node, self.socket_attr),
        )

    def mousePressEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Snap the Connection to the mouse.

        """
        nodz_inst = self.nodz_instance

        for item in nodz_inst.scene().items():
            if isinstance(item, ConnectionItem):
                item.setZValue(0)

        nodz_inst.drawing_connection = True

        d_to_target = (event.pos() - self.target_point).manhattanLength()
        d_to_source = (event.pos() - self.source_point).manhattanLength()
        if d_to_target < d_to_source:
            if not self.target:
                raise RuntimeError("Invalid target")
            self.target_point = event.pos()
            self.movable_point = "target_point"
            self.target.disconnect(self)
            self.target = None
            nodz_inst.source_slot = self.source
        else:
            if not self.source:
                raise RuntimeError("Invalid source")
            self.source_point = event.pos()
            self.movable_point = "source_point"
            self.source.disconnect(self)
            self.source = None
            nodz_inst.source_slot = self.target

        self.update_path()

    def mouseMoveEvent(
        self, event: QtWidgets.QGraphicsSceneMouseEvent
    ) -> None:
        """
        Move the Connection with the mouse.

        """
        nodz_inst = self.nodz_instance
        config = nodz_inst.config

        mbb = utils._create_pointer_bounding_box(
            pointer_pos=event.scenePos().toPoint(),
            bb_size=config["mouse_bounding_box"],
        )

        # Get nodes in pointer's bounding box.
        targets = self.scene().items(mbb)

        if any(isinstance(target, NodeItem) for target in targets):
            if not nodz_inst.source_slot:
                raise TypeError("Invalid source_slot")
            if nodz_inst.source_slot.parentItem() not in targets:
                for target in targets:
                    if isinstance(target, NodeItem):
                        nodz_inst.current_hovered_node = target
        else:
            nodz_inst.current_hovered_node = None

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
        self.nodz_instance.drawing_connection = False

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

        scene = self.scene()
        scene.removeItem(self)
        scene.update()

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
