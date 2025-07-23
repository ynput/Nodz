from __future__ import annotations
import os
from typing import Any
from enum import Enum
from qtpy import QtGui, QtCore, QtWidgets

from nodz.scene import NodeScene
from nodz.utils import nlog, _load_config
from nodz.data_types import NodzAdapter, GraphModel
from .api import CoreAPI, ModelAPI


DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "default_config.json"
)


class ViewState(Enum):
    DEFAULT = 0
    SELECTION = 1
    ADD_SELECTION = 2
    SUBTRACT_SELECTION = 3
    TOGGLE_SELECTION = 4
    ZOOM_VIEW = 5
    DRAG_VIEW = 6
    DRAG_ITEM = 7


class NodzSignals(QtCore.QObject):
    NodeCreated = QtCore.Signal(object)  # type: ignore (qtpy)
    NodeDeleted = QtCore.Signal(str)  # type: ignore (qtpy)
    NodeRenamed = QtCore.Signal(str, str)  # type: ignore (qtpy)
    NodeSelected = QtCore.Signal(object)  # type: ignore (qtpy)
    NodeMoved = QtCore.Signal(object, object)  # type: ignore (qtpy)
    NodeDoubleClicked = QtCore.Signal(object)  # type: ignore (qtpy)

    AttrCreated = QtCore.Signal(object, str)  # type: ignore (qtpy)
    AttrDeleted = QtCore.Signal(object, str)  # type: ignore (qtpy)
    AttrEdited = QtCore.Signal(object, int, int)  # type: ignore (qtpy)

    PlugConnected = QtCore.Signal(object)  # type: ignore (qtpy)
    PlugDisconnected = QtCore.Signal(object)  # type: ignore (qtpy)
    SocketConnected = QtCore.Signal(object)  # type: ignore (qtpy)
    SocketDisconnected = QtCore.Signal(object)  # type: ignore (qtpy)

    RemoveConnections = QtCore.Signal(object)  # type: ignore (qtpy)

    Dropped = QtCore.Signal()  # type: ignore (qtpy)

    NodeLayoutChanged = QtCore.Signal(object)  # type: ignore (qtpy)

    GraphSaved = QtCore.Signal()  # type: ignore (qtpy)
    GraphLoaded = QtCore.Signal()  # type: ignore (qtpy)
    GraphCleared = QtCore.Signal()  # type: ignore (qtpy)
    GraphEvaluated = QtCore.Signal()  # type: ignore (qtpy)

    KeyPressed = QtCore.Signal(object)  # type: ignore (qtpy)


class Nodz(QtWidgets.QGraphicsView):
    """
    The main view for the node graph representation.

    The node view implements a state pattern to control all the
    different user interactions.

    """

    # NOTE: Somehow QtCore.Signal is flagged by pylance as
    # not exported by qtpy.QtCore...

    delete_selected_nodes = QtCore.Signal()  # type: ignore (qtpy)
    snap_node_to_grid = QtCore.Signal(bool)  # type: ignore (qtpy)
    selection_changed = QtCore.Signal(bool)  # type: ignore (qtpy)

    def __init__(self, parent: Any, config_path: str = DEFAULT_CONFIG_PATH):
        """
        Initializes a Nodz view.

        Args:
            parent: The parent widget in which the graphics view is embedded.
            config_path (optional): Path to a configuration file. Defaults
                to DEFAULT_CONFIG_PATH.
        """
        super(Nodz, self).__init__(parent)
        self.signals = NodzSignals()
        self.config = _load_config(config_path)

        # Display options.
        self.current_state = ViewState.DEFAULT

        self._help_document = None

    def drawForeground(
        self, painter: QtGui.QPainter, rect: QtCore.QRectF | QtCore.QRect
    ) -> None:
        """
        Draws the foreground elements of the viewdocstring such as available
        keyboard shortcuts.

        Args:
            painter (QtGui.QPainter): The QPainter instance used for drawing.
            rect (QtCore.QRectF | QtCore.QRect): The rectangle specifying
                the area of the view that needs to be updated.
        """
        vp_bottom_left = self.viewport().rect().bottomLeft()
        painter.resetTransform()
        if not self._help_document:
            h_str = (
                "*Keyboard Shortcuts:*   "
                "**L**: Layout graph    "
                "**A**: Frame all nodes    "
                "**F**: Frame selection    "
                "**S-down**: Snap to grid"
            )
            self._help_document = QtGui.QTextDocument()
            font_size = painter.fontInfo().pointSize()
            self._help_document.setDefaultFont(
                QtGui.QFont(painter.font().family(), max(10, font_size - 2))
            )
            self._help_document.setMarkdown(h_str)
        painter.translate(
            QtCore.QPoint(vp_bottom_left.x() + 20, vp_bottom_left.y() - 30)
        )
        painter.setOpacity(0.5)
        self._help_document.drawContents(painter)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """
        Handles the wheel events on the view.

        Args:
            event (QtGui.QWheelEvent): The wheel event to handle.
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
        Handles the mouse press events on the view.
        Initialize tablet zoom, drag canvas and the selection.

        Args:
            event (QtGui.QMouseEvent): The mouse press event to handle.
        """

        # Tablet zoom
        if (
            event.button() == QtCore.Qt.MouseButton.RightButton
            and event.modifiers() == QtCore.Qt.KeyboardModifier.AltModifier
        ):
            self.current_state = ViewState.ZOOM_VIEW
            self.init_mouse_pos = event.pos()
            self.zoom_initial_pos = event.pos()
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
            and event.modifiers()
            == QtCore.Qt.KeyboardModifier.ShiftModifier
            | QtCore.Qt.KeyboardModifier.ControlModifier
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

        Args:
            event (QtGui.QMouseEvent): The mouse press event to handle.
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

        Args:
            event (QtGui.QMouseEvent): The mouse press event to handle.
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
        A- Frame all nodes
        L - Layout the graph
        S-down - Snap to the grid

        Args:
            event (QtGui.QKeyEvent): The key press event to handle.
        """

        if event.key() in (
            QtCore.Qt.Key.Key_Delete,
            QtCore.Qt.Key.Key_Backspace,
        ):
            self.delete_selected_nodes.emit()

        if event.key() == QtCore.Qt.Key.Key_F:
            self._focus()

        if event.key() == QtCore.Qt.Key.Key_A:
            self._frame_all()

        if event.key() == QtCore.Qt.Key.Key_L:
            self._layout_graph()

        if event.key() == QtCore.Qt.Key.Key_S:
            self.snap_node_to_grid.emit(True)

        # Emit signal.
        self.signals.KeyPressed.emit(event.key())

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
        """
        Clear the key from the pressed key list.

        Args:
            event (QtGui.QKeyEvent): The released key event.
        """
        if event.key() == QtCore.Qt.Key.Key_S:
            self.snap_node_to_grid.emit(False)

    def _init_rubberband(self, position: QtCore.QPointF) -> None:
        """
        Initialize the rubber band at the given position.

        Args:
            position (QtCore.QPointF): position to start the rubber band at.
        """
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
        # make sure the scene is big enough to contain all nodes.
        self.scene().setSceneRect(self.scene().sceneRect().united(items_area))
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
        # make sure the scene is big enough to contain all nodes.
        self.scene().setSceneRect(self.scene().sceneRect().united(items_area))
        self.fitInView(items_area, QtCore.Qt.AspectRatioMode.KeepAspectRatio)

    def _center_graph_in_scene(self):
        """
        Move all nodes to the center of the scene.
        """
        # Center the graph in the scene
        scene_center = self.scene().sceneRect().center()
        graph_center = self.scene().itemsBoundingRect().center()
        offset = scene_center - graph_center
        for node in self._scene.node_items():
            node.setPos(node.pos() + offset)
        self._scene.update_scene()

    def _layout_graph(self):
        """
        Organize nodes in the graph according to their connections.
        """
        # Configuration
        h_spacing = self.config["horizontal_node_spacing"]
        v_spacing = self.config["vertical_node_spacing"]

        node_names = self._scene.node_names()

        # Find root nodes (nodes without incoming connections)
        root_nodes = [
            node
            for node_name in node_names
            for node in (self._scene.node_by_name(node_name),)
            if all(len(plug.connections) == 0 for plug in node.plugs.values())
        ]
        nlog.debug(
            f"_layout_graph: root_nodes: {[n.model.name for n in root_nodes]}"
        )

        start_x_pos = h_spacing
        start_y_pos = 0

        for root in root_nodes:
            # Initialize graph layout data
            graph_depth = [[(root, root.base_width, root.height)]]
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
                        if attr not in node.attr_names:
                            continue

                        for connection in socket.connections:
                            has_connections = True
                            src_node = connection.plug_item.parentItem()
                            if len(graph_depth) <= level + 1:
                                graph_depth.append([])
                            graph_depth[level + 1].append(
                                (
                                    src_node,
                                    src_node.base_width,
                                    src_node.height,
                                )
                            )

                scene_height = max(scene_height, lheight)
                level = level + 1 if has_connections else -1

            nlog.debug(f"_layout_graph: graph_depth = {graph_depth}")

            # Position nodes from bottom to top
            ymax = 0
            positioned_nodes = []

            for i, lst in enumerate(reversed(graph_depth)):
                xpos = start_x_pos + i * (root_nodes[0].base_width + h_spacing)
                ypos = start_y_pos + v_spacing

                for node, _, hgt in lst:
                    if node not in positioned_nodes:
                        pos = QtCore.QPointF(xpos, ypos)
                        ypos += hgt + v_spacing
                        node.setPos(pos)
                        positioned_nodes.append(node)
                ymax = max(ymax, ypos)

            # update start position for next root node
            start_y_pos = ymax

        self._scene.update_scene()
        self._center_graph_in_scene()

        # emit a dict[str, QPointF] for all nodes.
        self.signals.NodeLayoutChanged.emit(
            {n.model.name: n.pos() for n in self._scene.node_items()}
        )

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

    def initialize(self, node_factory=None, adapter=None) -> None:
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
        self._scene = NodeScene(self, self.config, self.signals)
        scene_width = config["scene_width"]
        scene_height = config["scene_height"]
        self._scene.setSceneRect(0, 0, scene_width, scene_height)
        if node_factory:
            self._scene.register_factory(node_factory)
        self.api = CoreAPI(self, self._scene)
        self.model_api = ModelAPI(
            self,
            self._scene,
            adapter if adapter else NodzAdapter(GraphModel()),
        )
        self.setScene(self._scene)

        # Connect scene node signals
        # self.signals.signal_NodeMoved.connect(self.signal_NodeMoved)
        self.delete_selected_nodes.connect(self._scene._delete_selected_nodes)
        self.snap_node_to_grid.connect(self._scene.snap_node_to_grid)

        # Tablet zoom.
        self.previous_mouse_offset = 0
        self.zoom_direction = 0
        self.zoom_incr = 0
