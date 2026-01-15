"""
Main module for Nodz.

This module provides the main entry point for the Nodz graph editor.
It demonstrates how to use the MVC architecture to create a Nodz application.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional, Set, TypedDict, Union

from qtpy import QtCore, QtGui, QtWidgets

from .slot_drawer import SlotDrawer
from .views import (
    NodeView,
    ConnectionView,
    PlugView,
    SocketView,
    SlotView,
    NodeGroupView,
    CNCT_Z,
    CNCT_Z_UP,
    NODE_Z_UP,
)
from .controllers import NodzAPI
from .utils import nlog


class LayoutConfig(TypedDict):
    """Configuration for graph layout spacing."""

    horizontal_spacing: float
    vertical_spacing: float
    group_padding: float


DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "default_config.json"
)


class NodzScene(QtWidgets.QGraphicsScene):
    """Scene for the Nodz graph editor."""

    def __init__(self, parent, config: Dict[str, Any]):
        """Initialize the scene."""
        super().__init__(parent)
        self.config = config

        # Set scene properties
        scene_width = config["scene_width"]
        scene_height = config["scene_height"]
        self.setSceneRect(0, 0, scene_width, scene_height)

        # Set background
        self._brush = QtGui.QBrush()
        self._brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        self._brush.setColor(QtGui.QColor(*config["bg_color"]))

        # bean keeping
        self._nodeviews: list[NodeView] = list()
        self._connectionviews: list[ConnectionView] = list()
        self._groupviews: list[NodeGroupView] = list()

    def drawBackground(
        self, painter: QtGui.QPainter, rect: Union[QtCore.QRectF, QtCore.QRect]
    ) -> None:
        """Draw the scene background."""
        painter.fillRect(rect, self._brush)

        # Draw grid if enabled
        if self.config.get("grid_visible", True):
            grid_size = self.config["grid_size"]
            left_line = rect.left() - rect.left() % grid_size
            top_line = rect.top() - rect.top() % grid_size
            lines = []

            # Vertical lines
            i = int(left_line)
            while i < int(rect.right()):
                lines.append(QtCore.QLineF(i, rect.top(), i, rect.bottom()))
                i += grid_size

            # Horizontal lines
            u = int(top_line)
            while u < int(rect.bottom()):
                lines.append(QtCore.QLineF(rect.left(), u, rect.right(), u))
                u += grid_size

            # Draw lines
            pen = QtGui.QPen()
            pen.setColor(QtGui.QColor(*self.config["grid_color"]))
            pen.setWidth(0)
            painter.setPen(pen)
            painter.drawLines(lines)

    def addItem(self, item: QtWidgets.QGraphicsItem) -> None:
        """Extend addItem to store lists of NodeView, ConnectionView, and
        NodeGroupView items.
        """
        if isinstance(item, NodeView):
            self._nodeviews.append(item)
        elif isinstance(item, ConnectionView):
            self._connectionviews.append(item)
        elif isinstance(item, NodeGroupView):
            self._groupviews.append(item)
        super().addItem(item)

    def removeItem(self, item: QtWidgets.QGraphicsItem) -> None:
        """Extend removeItem to update our internal item lists."""
        if isinstance(item, NodeView):
            if item in self._nodeviews:
                self._nodeviews.remove(item)
        elif isinstance(item, ConnectionView):
            if item in self._connectionviews:
                self._connectionviews.remove(item)
        elif isinstance(item, NodeGroupView):
            if item in self._groupviews:
                self._groupviews.remove(item)
        super().removeItem(item)

    def node_items(self) -> list[NodeView]:
        """Return list of all NodeView items in the scene."""
        return self._nodeviews

    def connection_items(self) -> list[ConnectionView]:
        """Return list of all ConnectionView items in the scene."""
        return self._connectionviews

    def group_items(self) -> list[NodeGroupView]:
        """Return list of all NodeGroupView items in the scene."""
        return self._groupviews

    def clear(self) -> None:
        """Clear all items from the scene and reset internal lists."""
        super().clear()
        self._nodeviews.clear()
        self._connectionviews.clear()
        self._groupviews.clear()

    def get_slot_connections(self, slot: SlotView) -> list:
        """Get all connections attached to a slot."""

        if not isinstance(slot, SlotView):
            raise TypeError(f"slot MUST be a SlotView, not {slot}")

        connections = []

        # Find all connection views in the scene
        for item in self.connection_items():
            # Check if this connection is connected to the slot
            if not hasattr(slot, "parentItem") or not slot.parentItem():
                continue

            parent = slot.parentItem()
            if not isinstance(parent, NodeView):
                continue

            node_name = parent.model.name
            attr_name = slot.model.attribute

            if (
                isinstance(slot, PlugView)
                and item.model.plug_node == node_name
                and item.model.plug_attr == attr_name
            ):
                connections.append(item)
            elif (
                isinstance(slot, SocketView)
                and item.model.socket_node == node_name
                and item.model.socket_attr == attr_name
            ):
                connections.append(item)

        return connections


class LineRubberBand(QtWidgets.QRubberBand):
    """Custom QRubberBand that draws a line instead of a rectangle."""

    def __init__(self, parent=None):
        super().__init__(QtWidgets.QRubberBand.Shape.Line, parent)
        self.start_point = QtCore.QPoint()
        self.end_point = QtCore.QPoint()

    def set_line(self, start: QtCore.QPoint, end: QtCore.QPoint):
        """Set the line coordinates and update geometry."""
        self.start_point = start
        self.end_point = end

        # Set geometry to encompass the line
        rect = QtCore.QRect(start, end).normalized()
        # Add some padding to ensure the line is visible
        rect.adjust(-2, -2, 2, 2)
        self.setGeometry(rect)

    def paintEvent(self, arg__1):
        """Paint a line instead of the default rectangle."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # Set up pen for the cutting line
        pen = QtGui.QPen(QtGui.QColor(255, 0, 0))  # Red color
        pen.setWidth(2)
        pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        # Convert global coordinates to local widget coordinates
        local_start = self.mapFromGlobal(
            self.parent().mapToGlobal(self.start_point)  # type: ignore
        )
        local_end = self.mapFromGlobal(
            self.parent().mapToGlobal(self.end_point)  # type: ignore
        )

        # Draw the line
        painter.drawLine(local_start, local_end)


class NodzView(QtWidgets.QGraphicsView):
    """View for the Nodz graph editor."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        config_path: str = DEFAULT_CONFIG_PATH,
    ):
        """Initialize the view."""
        super().__init__(parent)

        # Load configuration
        self.config = self._load_config(config_path)

        # initialize slot drawer singleton
        SlotDrawer(self.config)

        # Setup view
        self._setup_view()

        # Create scene
        self.nodz_scene = NodzScene(self, self.config)
        self.setScene(self.nodz_scene)

        # Create API
        self.api = NodzAPI(self.nodz_scene, self.config)

        self._show_help = False
        self._viewport_help_document = None
        self._viewport_help_hint = None

        # Grid snapping state
        self._grid_snap_enabled = False

        # Rubberband selection
        self.setDragMode(
            QtWidgets.QGraphicsView.DragMode.NoDrag
        )  # We'll handle rubberband manually
        self.rubberband_origin = QtCore.QPoint()
        self.rubberband_rect = QtCore.QRect()
        self.is_rubberband_active = False
        self.selection_operation = (
            QtCore.Qt.ItemSelectionOperation.ReplaceSelection
        )
        self.selection_mode = "replace"  # "replace" or "subtract"
        self.rubber_band = QtWidgets.QRubberBand(
            QtWidgets.QRubberBand.Shape.Rectangle, self
        )
        self.previously_selected = []  # Store previously selected items

        # Line rubberband for connection cutting
        self.is_line_rubberband_active = False
        self.line_rubberband = LineRubberBand(self)
        self.line_start = QtCore.QPoint()
        self.line_end = QtCore.QPoint()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from a file."""
        import json
        import re

        class CommentedJsonDecoder:
            """JSON decoder that strips C-style comments."""

            def __init__(self):
                # Regex pattern for single-line comments (// ...)
                self.single_line_pattern = re.compile(r"//.*?$", re.MULTILINE)
                # Regex pattern for multi-line comments (/* ... */)
                self.multi_line_pattern = re.compile(r"/\*.*?\*/", re.DOTALL)

            def strip_comments(self, text: str) -> str:
                """Strip C-style comments from text and replace with empty
                lines."""

                # First, handle multi-line comments
                def replace_with_newlines(match):
                    # Count the number of newlines in the comment
                    newlines = match.group(0).count("\n")
                    # Replace with the same number of newlines to preserve
                    # line numbers
                    return "\n" * newlines if newlines > 0 else ""

                text = self.multi_line_pattern.sub(replace_with_newlines, text)

                # Then handle single-line comments
                text = self.single_line_pattern.sub("", text)

                return text

            def decode(self, text: str) -> Dict[str, Any]:
                """Decode JSON text with comments."""
                # Strip comments
                text = self.strip_comments(text)
                # Parse JSON
                return json.loads(text)

        # Read the file
        with open(config_path, "r") as f:
            content = f.read()

        # Use the custom decoder
        decoder = CommentedJsonDecoder()
        return decoder.decode(content)

    def _setup_view(self) -> None:
        """Setup the view."""
        # Set rendering hints
        self.setRenderHint(
            QtGui.QPainter.RenderHint.Antialiasing, self.config["antialiasing"]
        )
        self.setRenderHint(
            QtGui.QPainter.RenderHint.TextAntialiasing,
            self.config["antialiasing"],
        )
        self.setRenderHint(
            QtGui.QPainter.RenderHint.SmoothPixmapTransform,
            self.config["smooth_pixmap"],
        )

        # Set viewport update mode
        self.setViewportUpdateMode(
            QtWidgets.QGraphicsView.ViewportUpdateMode.FullViewportUpdate
        )

        # Set transformation anchor
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )

        # Set scroll bar policies
        self.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

    def drawForeground(
        self, painter: QtGui.QPainter, rect: Union[QtCore.QRectF, QtCore.QRect]
    ) -> None:
        """
        Draws the foreground elements of the viewdocstring such as available
        keyboard shortcuts.

        Args:
            painter (QtGui.QPainter): The QPainter instance used for drawing.
            rect (QtCore.QRectF | QtCore.QRect): The rectangle specifying
                the area of the view that needs to be updated.
        """

        def _build_doc(_docstr: str):
            _doc = QtGui.QTextDocument()
            font_size = painter.fontInfo().pointSize()
            _doc.setDefaultFont(
                QtGui.QFont(painter.font().family(), max(10, font_size - 2))
            )
            _doc.setMarkdown(_docstr)
            return _doc

        painter.save()

        if not self._viewport_help_hint:
            h_str = "**H**: Toggle help overlay"
            self._viewport_help_hint = _build_doc(h_str)

        if not self._viewport_help_document:
            h_str = (
                "*Keyboard Shortcuts:*   \n\n"
                "**L**: Layout graph    "
                "**A**: Frame all nodes    "
                "**F**: Frame selection    "
                "**Ctrl+G**: Create group from selection    "
                "**Ctrl+Shift+G**: Remove selected groups    \n\n"
                "**H**: Toggle help overlay    "
                "**Del/Backspace**: Delete selection    \n\n"
                "**Shift+Click**: Add to selection    "
                "**Ctrl+Click**: Remove from selection    "
                "**Alt+Drag**: Cut connections    "
                "**S-down**: Snap to grid"
            )
            self._viewport_help_document = _build_doc(h_str)

        vp_bottom_left = self.viewport().rect().bottomLeft()
        painter.resetTransform()
        doc = (
            self._viewport_help_document
            if self._show_help
            else self._viewport_help_hint
        )
        painter.translate(
            QtCore.QPoint(
                vp_bottom_left.x() + 20,
                vp_bottom_left.y() - int(doc.size().height()) - 10,
            )
        )
        painter.setOpacity(0.5)
        doc.drawContents(painter)
        painter.restore()

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """Handle wheel events for zooming."""
        # Set transformation anchor
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )

        # Calculate zoom factor
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor

        # Get zoom direction
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor

        # Apply zoom
        self.scale(zoom_factor, zoom_factor)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse press events."""
        # Middle mouse button for panning
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
            # Create a fake event to initiate the drag
            fake_event = QtGui.QMouseEvent(
                QtCore.QEvent.Type.MouseButtonPress,
                event.pos(),
                QtCore.Qt.MouseButton.LeftButton,
                event.buttons() | QtCore.Qt.MouseButton.LeftButton,
                event.modifiers(),
            )
            super().mousePressEvent(fake_event)
        # Left mouse button for selection
        elif event.button() == QtCore.Qt.MouseButton.LeftButton:
            modifiers = event.modifiers()
            pos = event.pos()

            # Alt+Drag for connection cutting
            if modifiers & QtCore.Qt.KeyboardModifier.AltModifier:
                self.is_line_rubberband_active = True
                self.line_start = pos
                self.line_end = pos
                self.line_rubberband.set_line(pos, pos)
                self.line_rubberband.show()
                event.accept()
                return

            # Get the item at the click position
            item = self.itemAt(pos)

            # If clicking on an item
            if item and isinstance(item, QtWidgets.QGraphicsItem):
                # Store current selection for Shift or Ctrl click
                currently_selected = [
                    i for i in self.nodz_scene.selectedItems()
                ]

                # Determine selection operation based on modifiers
                if modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier:
                    # Shift-click: add to selection
                    # Add the clicked item to selection without clearing
                    item.setSelected(True)

                    # Make sure previously selected items stay selected
                    for selected_item in currently_selected:
                        selected_item.setSelected(True)

                    # Update connection Z values after selection change
                    self._update_connection_z_values()

                    # Skip default event handling
                    event.accept()
                    return

                elif modifiers & QtCore.Qt.KeyboardModifier.ControlModifier:
                    # Ctrl-click: toggle selection
                    was_selected = item.isSelected()
                    item.setSelected(not was_selected)

                    # Make sure previously selected items stay selected
                    # (except the toggled one)
                    for selected_item in currently_selected:
                        if selected_item != item:
                            selected_item.setSelected(True)

                    # Update connection Z values after selection change
                    self._update_connection_z_values()

                    # Skip default event handling
                    event.accept()
                    return

                # Normal click: clear selection and select only this item
                else:
                    # Let the default handler take care of it
                    super().mousePressEvent(event)
                    # Update connection Z values after selection change
                    self._update_connection_z_values()
                    return
            # If clicking on empty space, start rubberband selection
            else:
                # Store current selection if using Shift or Ctrl
                self.previously_selected = []
                if (
                    modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier
                    or modifiers & QtCore.Qt.KeyboardModifier.ControlModifier
                ):
                    self.previously_selected = [
                        item for item in self.nodz_scene.selectedItems()
                    ]

                # Determine selection operation based on modifiers
                if modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier:
                    # Shift: add to selection
                    self.selection_operation = (
                        QtCore.Qt.ItemSelectionOperation.AddToSelection
                    )
                elif modifiers & QtCore.Qt.KeyboardModifier.ControlModifier:
                    # Ctrl: subtract from selection (handled manually since
                    # there's no RemoveFromSelection)
                    self.selection_mode = "subtract"
                    self.selection_operation = (
                        QtCore.Qt.ItemSelectionOperation.ReplaceSelection
                    )
                else:
                    # Normal: replace selection
                    self.selection_mode = "replace"
                    self.selection_operation = (
                        QtCore.Qt.ItemSelectionOperation.ReplaceSelection
                    )

                    # Clear selection if starting a new rubberband without
                    # modifiers
                    if not (
                        modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier
                        or modifiers
                        & QtCore.Qt.KeyboardModifier.ControlModifier
                    ):
                        self.nodz_scene.clearSelection()
                        # Emit signal when selection is cleared
                        self.api.signals.selection_cleared.emit()

                # Start rubberband selection
                self.rubberband_origin = pos
                self.is_rubberband_active = True
                self.rubber_band.setGeometry(QtCore.QRect(pos, QtCore.QSize()))
                self.rubber_band.show()

                # Skip default event handling to prevent selection clearing
                event.accept()
                return

            super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse release events."""
        # Reset drag mode
        if self.dragMode() == QtWidgets.QGraphicsView.DragMode.ScrollHandDrag:
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
            # Create a fake event to end the drag
            fake_event = QtGui.QMouseEvent(
                QtCore.QEvent.Type.MouseButtonRelease,
                event.pos(),
                QtCore.Qt.MouseButton.LeftButton,
                event.buttons() & ~QtCore.Qt.MouseButton.LeftButton,
                event.modifiers(),
            )
            super().mouseReleaseEvent(fake_event)
        elif self.is_line_rubberband_active:
            self.is_line_rubberband_active = False
            self.line_rubberband.hide()

            # Convert line coordinates to scene coordinates
            scene_start = self.mapToScene(self.line_start)
            scene_end = self.mapToScene(self.line_end)

            # Find connections that intersect with the line
            connections_to_cut = self._find_intersecting_connections(
                scene_start, scene_end
            )

            # Disconnect the intersecting connections
            for connection in connections_to_cut:
                if isinstance(connection, ConnectionView):
                    self.api.delete_connection(
                        connection.model.plug_node,
                        connection.model.plug_attr,
                        connection.model.socket_node,
                        connection.model.socket_attr,
                    )

            event.accept()
            return
        elif self.is_rubberband_active:
            self.is_rubberband_active = False
            self.rubber_band.hide()

            # Create a path from the rubber band rectangle
            rect = self.rubber_band.geometry()
            scene_rect = self.mapToScene(rect).boundingRect()
            path = QtGui.QPainterPath()
            path.addRect(scene_rect)

            # Get items in the rubber band
            items_in_rubber_band = self.nodz_scene.items(scene_rect)

            if (
                self.selection_operation
                == QtCore.Qt.ItemSelectionOperation.AddToSelection
            ):
                # Restore previous selection
                for item in self.previously_selected:
                    item.setSelected(True)

                # Add new items to selection
                for item in items_in_rubber_band:
                    item.setSelected(True)
            elif self.selection_mode == "subtract":
                # Restore previous selection
                for item in self.previously_selected:
                    item.setSelected(True)

                # Remove items in rubber band from selection
                for item in items_in_rubber_band:
                    item.setSelected(False)
            else:
                # Replace selection - let Qt handle it
                self.nodz_scene.setSelectionArea(path)

            # Reset selection operation to default
            self.selection_operation = (
                QtCore.Qt.ItemSelectionOperation.ReplaceSelection
            )
            self.previously_selected = []

            # Update connection Z values after selection change
            self._update_connection_z_values()

            # Skip default event handling
            event.accept()
            return
        else:
            super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse move events."""
        # If in scroll hand drag mode, pass the event to the parent
        if self.dragMode() == QtWidgets.QGraphicsView.DragMode.ScrollHandDrag:
            super().mouseMoveEvent(event)
        # If in line rubberband mode, update the line
        elif self.is_line_rubberband_active:
            self.line_end = event.pos()
            # Update line rubberband to show the line
            self.line_rubberband.set_line(self.line_start, self.line_end)
            super().mouseMoveEvent(event)
        # If in rubberband drag mode, update the rubberband
        elif self.is_rubberband_active:
            self.rubber_band.setGeometry(
                QtCore.QRect(self.rubberband_origin, event.pos()).normalized()
            )
            super().mouseMoveEvent(event)
        else:
            # If grid snapping is enabled and we're dragging nodes, snap them
            # to grid
            if (
                self._grid_snap_enabled
                and event.buttons() & QtCore.Qt.MouseButton.LeftButton
            ):
                # Let the default move happen first
                super().mouseMoveEvent(event)
                # Then snap any selected nodes to grid
                self._snap_selected_nodes_to_grid()
            else:
                super().mouseMoveEvent(event)

            # Update all connections after any node movement
            self._update_all_connections()

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Handle key press events."""
        # Frame all nodes with 'A'
        if event.key() == QtCore.Qt.Key.Key_A:
            self.frame_all()
        # Frame selected nodes with 'F'
        elif event.key() == QtCore.Qt.Key.Key_F:
            self.frame_selected()
        # Create group from selection with Ctrl+G
        # Remove selected group with Ctrl+Shift+G
        elif (
            event.key() == QtCore.Qt.Key.Key_G
            and event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            if event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier:
                self.remove_group_from_selection()
            else:
                self.create_group_from_selection()
        # show help overlay with 'H'
        elif event.key() == QtCore.Qt.Key.Key_H:
            self._show_help = False if self._show_help else True
            self.scene().update()
        # Layout graph with 'L'
        elif event.key() == QtCore.Qt.Key.Key_L:
            self.layout_graph()
        # Enable grid snapping with 'S' (hold down)
        elif event.key() == QtCore.Qt.Key.Key_S:
            if not event.isAutoRepeat():
                # Only on first press, not auto-repeat
                self._grid_snap_enabled = True
                self._snap_selected_nodes_to_grid()
        # Delete selected nodes with Delete or Backspace
        elif event.key() in (
            QtCore.Qt.Key.Key_Delete,
            QtCore.Qt.Key.Key_Backspace,
        ):
            self.delete_selected()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QtGui.QKeyEvent) -> None:
        """Handle key release events."""
        # Disable grid snapping when 'S' is released
        if event.key() == QtCore.Qt.Key.Key_S:
            if not event.isAutoRepeat():
                # Only on actual release, not auto-repeat
                self._grid_snap_enabled = False
        else:
            super().keyReleaseEvent(event)

    def _apply_viewport_margin(self, rect: QtCore.QRectF) -> None:
        """
        Apply viewport margins to a rectangle, converting from viewport space
        to scene space.

        Args:
            rect (QtCore.QRectF): The rectangle to adjust with margins.
        """

        # Get margin value from config
        viewport_margin = self.config["viewport_margins"]

        # Convert margin from viewport space to scene space
        # Create two points in viewport coordinates
        viewport_point1 = QtCore.QPoint(0, 0)
        viewport_point2 = QtCore.QPoint(viewport_margin, viewport_margin)

        # Map these points to scene coordinates
        scene_point1 = self.mapToScene(viewport_point1)
        scene_point2 = self.mapToScene(viewport_point2)

        # Calculate the scene margin (distance between the two points in scene
        # coordinates)
        scene_margin = max(
            abs(scene_point2.x() - scene_point1.x()),
            abs(scene_point2.y() - scene_point1.y()),
        )

        # Apply the margin to the rectangle
        rect.adjust(-scene_margin, -scene_margin, scene_margin, scene_margin)

    def frame_all(self) -> None:
        """Frame all nodes in the view."""
        # Get bounding rect of all items
        items_rect = self.nodz_scene.itemsBoundingRect()
        self.fitInView(items_rect, QtCore.Qt.AspectRatioMode.KeepAspectRatio)
        self._apply_viewport_margin(items_rect)
        self.fitInView(items_rect, QtCore.Qt.AspectRatioMode.KeepAspectRatio)

    def frame_selected(self) -> None:
        """Frame only the selected nodes in the view."""
        # Get all selected node views
        selected_items = [
            item
            for item in self.nodz_scene.selectedItems()
            if isinstance(item, (NodeView, NodeGroupView))
        ]

        if not selected_items:
            # If no nodes are selected, do nothing
            return

        # Calculate the bounding rectangle of selected nodes
        selection_rect = None
        for item in selected_items:
            if not selection_rect:
                selection_rect = item.sceneBoundingRect()
            else:
                selection_rect = selection_rect.united(
                    item.sceneBoundingRect()
                )

        if not selection_rect:
            return

        # Fit the selected nodes in view
        self.fitInView(
            selection_rect, QtCore.Qt.AspectRatioMode.KeepAspectRatio
        )
        self._apply_viewport_margin(selection_rect)
        self.fitInView(
            selection_rect, QtCore.Qt.AspectRatioMode.KeepAspectRatio
        )

    def delete_selected(self) -> None:
        """Delete all selected nodes from the graph."""
        # Get all selected node views
        selected_nodes = [
            item
            for item in self.nodz_scene.selectedItems()
            if isinstance(item, (NodeView, NodeGroupView))
        ]

        if not selected_nodes:
            # If no nodes are selected, do nothing
            return

        # Delete each selected node using the API
        for node in selected_nodes:
            if isinstance(node, NodeView):
                self.api.delete_node(node.model.name, emit=True)
            elif isinstance(node, NodeGroupView):
                self.api.delete_node_group(node.model.name, emit=True)

    def create_group_from_selection(self) -> None:
        """Create a node group from currently selected nodes.

        Generates a unique group name like "Group 1", "Group 2", etc.
        and creates a group containing all selected nodes.
        """
        # Get all selected node views
        selected_nodes = [
            item.model.name
            for item in self.nodz_scene.selectedItems()
            if isinstance(item, NodeView)
        ]

        if len(selected_nodes) < 1:
            # Need at least one node to create a group
            return

        # Generate a unique group name
        base_name = "Group"
        counter = 1
        existing_groups = self.api.list_node_groups()
        while f"{base_name} {counter}" in existing_groups:
            counter += 1
        group_name = f"{base_name} {counter}"

        # Create the group via the API
        try:
            self.api.create_node_group(group_name, selected_nodes, emit=True)
            nlog.info(
                f"Created group '{group_name}' with {len(selected_nodes)} "
                "node(s)"
            )
        except Exception as e:
            nlog.error(f"Failed to create group: {e}")

    def remove_group_from_selection(self) -> None:
        """Remove node groups from the current selection.

        Deletes all selected node groups.
        """
        # Get all selected group views
        selected_groups = [
            item
            for item in self.nodz_scene.selectedItems()
            if isinstance(item, NodeGroupView)
        ]

        if not selected_groups:
            # No groups selected, do nothing
            return

        # Delete each selected group using the API
        for group in selected_groups:
            try:
                self.api.delete_node_group(group.model.name, emit=True)
                nlog.info(f"Removed group '{group.model.name}'")
            except Exception as e:
                nlog.error(f"Failed to remove group '{group.model.name}': {e}")

    def _center_graph_in_scene(self):
        """
        Move all nodes to the center of the scene.
        """
        # Center the graph in the scene
        scene_center = self.scene().sceneRect().center()
        graph_center = self.scene().itemsBoundingRect().center()
        offset = scene_center - graph_center

        node_views = self._get_all_node_views()

        for node in node_views:
            scene_pos = node.pos() + offset
            node.setPos(scene_pos)
            self.api.signals.node_moved.emit(node.model.name, scene_pos)

        self._update_all_connections()

    def layout_graph(self) -> None:
        """
        Organize nodes in the graph according to their connections using a
        hierarchical layout.

        This method arranges nodes in columns based on their dependency
        relationships, with root nodes (no incoming connections) on the left
        and dependent nodes arranged in subsequent columns to the right.

        If node groups exist, the method will:
        1. Layout nodes within each group as a sub-graph
        2. Treat each group as a "super-node" and layout groups based on
           inter-group connections

        Raises:
            ValueError: If the scene or configuration is invalid
        """
        try:
            node_views = self._get_all_node_views()
            if not node_views:
                return

            # Build node mapping and connection data
            name_to_views = self._build_node_mapping(node_views)
            if not name_to_views:
                return

            # Check if there are node groups
            group_views = self.nodz_scene.group_items()

            if group_views:
                # Group-aware layout
                self._layout_graph_with_groups(name_to_views, group_views)
            else:
                # Standard layout without groups
                self._layout_graph_standard(name_to_views)

            # Update visual elements
            self._finalize_layout()

        except Exception as e:
            nlog.error(f"Error during graph layout: {e}")
            # Fallback: just center the graph without changing positions
            self._center_graph_in_scene()

    def _layout_graph_standard(
        self, name_to_views: Dict[str, NodeView]
    ) -> None:
        """
        Perform standard hierarchical layout without groups.

        Args:
            name_to_views: Mapping of node names to NodeView objects.
        """
        node_connections = self._analyze_node_connections(name_to_views)

        # Find nodes that have no incoming connections (root nodes)
        root_nodes = self._find_root_nodes(name_to_views, node_connections)
        if not root_nodes:
            # If no root nodes found, treat all nodes as roots
            root_nodes = list(name_to_views.values())

        # Layout each root node hierarchy
        layout_config = self._get_layout_config()
        self._layout_node_hierarchies(
            root_nodes, name_to_views, node_connections, layout_config
        )

    def _layout_graph_with_groups(
        self,
        name_to_views: Dict[str, NodeView],
        group_views: List[NodeGroupView],
    ) -> None:
        """
        Perform hierarchical layout with group awareness.

        This method:
        1. Layouts nodes within each group as sub-graphs
        2. Treats each group as a super-node and layouts groups based on
           inter-group connections
        3. Handles ungrouped nodes separately

        Args:
            name_to_views: Mapping of node names to NodeView objects.
            group_views: List of NodeGroupView items.
        """
        layout_config = self._get_layout_config()

        # Build group membership mapping
        group_members, ungrouped_nodes = self._categorize_nodes_by_group(
            name_to_views, group_views
        )

        # Step 1: Layout nodes within each group as sub-graphs
        group_dimensions = self._layout_nodes_within_groups(
            group_members, name_to_views, layout_config
        )

        # Step 2: Analyze inter-group connections
        inter_group_connections = self._analyze_inter_group_connections(
            group_members, name_to_views, ungrouped_nodes
        )

        # Step 3: Layout groups as super-nodes
        self._layout_groups_as_supernodes(
            group_views,
            group_dimensions,
            inter_group_connections,
            layout_config,
        )

        # Step 4: Layout ungrouped nodes
        if ungrouped_nodes:
            self._layout_ungrouped_nodes(
                ungrouped_nodes,
                name_to_views,
                group_views,
                inter_group_connections,
                layout_config,
            )

        # Step 5: Update group rectangles to fit their members
        self._update_group_rects_after_layout(group_views, name_to_views)

    def _categorize_nodes_by_group(
        self,
        name_to_views: Dict[str, NodeView],
        group_views: List[NodeGroupView],
    ) -> tuple[Dict[str, List[str]], List[str]]:
        """
        Categorize nodes by their group membership.

        Args:
            name_to_views: Mapping of node names to NodeView objects.
            group_views: List of NodeGroupView items.

        Returns:
            Tuple of (group_members dict, ungrouped_nodes list):
            - group_members: Dict mapping group names to list of member names
            - ungrouped_nodes: List of node names not in any group
        """
        group_members: Dict[str, List[str]] = {}
        nodes_in_groups: set = set()

        for group_view in group_views:
            group_name = group_view.model.name
            members = list(group_view.model.members)
            # Filter to only include nodes that exist in the scene
            valid_members = [m for m in members if m in name_to_views]
            group_members[group_name] = valid_members
            nodes_in_groups.update(valid_members)

        ungrouped_nodes = [
            name
            for name in name_to_views.keys()
            if name not in nodes_in_groups
        ]

        return group_members, ungrouped_nodes

    def _layout_nodes_within_groups(
        self,
        group_members: Dict[str, List[str]],
        name_to_views: Dict[str, NodeView],
        layout_config: LayoutConfig,
    ) -> Dict[str, Dict[str, float]]:
        """
        Layout nodes within each group as a sub-graph.

        Each group's nodes are laid out using hierarchical logic based on
        their internal connections. The positions are relative (starting
        from 0,0) and will be adjusted when groups are positioned.

        Args:
            group_members: Dict mapping group names to member node names.
            name_to_views: Mapping of node names to NodeView objects.
            layout_config: Layout spacing configuration.

        Returns:
            Dict mapping group names to their dimensions (width, height).
        """
        group_dimensions: Dict[str, Dict[str, float]] = {}

        for group_name, member_names in group_members.items():
            if not member_names:
                group_dimensions[group_name] = {
                    "width": 100.0,
                    "height": 100.0,
                }
                continue

            # Build mapping for this group's nodes only
            group_node_views = {
                name: name_to_views[name]
                for name in member_names
                if name in name_to_views
            }

            if not group_node_views:
                group_dimensions[group_name] = {
                    "width": 100.0,
                    "height": 100.0,
                }
                continue

            # Analyze connections within the group only
            internal_connections = self._analyze_internal_connections(
                group_node_views
            )

            # Find root nodes within the group
            root_nodes = self._find_root_nodes_in_subset(
                group_node_views, internal_connections
            )
            if not root_nodes:
                root_nodes = list(group_node_views.values())

            # Layout nodes within the group starting at origin
            self._layout_subgraph(
                root_nodes,
                group_node_views,
                internal_connections,
                layout_config,
                start_x=0.0,
                start_y=0.0,
            )

            # Calculate group dimensions based on positioned nodes
            dimensions = self._calculate_group_bounds(group_node_views)
            group_dimensions[group_name] = dimensions

        return group_dimensions

    def _analyze_internal_connections(
        self, group_node_views: Dict[str, NodeView]
    ) -> Dict[str, Dict[str, List]]:
        """
        Analyze connections only between nodes in a specific group.

        Args:
            group_node_views: Mapping of node names to views for group members.

        Returns:
            Connection data for internal connections only.
        """
        node_connections = {
            name: {"plugs": [], "sockets": []}
            for name in group_node_views.keys()
        }

        for item in self.nodz_scene.connection_items():
            plug_node = item.model.plug_node
            socket_node = item.model.socket_node

            # Only include connections where both nodes are in the group
            if (
                plug_node in group_node_views
                and socket_node in group_node_views
            ):
                node_connections[plug_node]["plugs"].append(item)
                node_connections[socket_node]["sockets"].append(item)

        return node_connections

    def _find_root_nodes_in_subset(
        self,
        node_views: Dict[str, NodeView],
        node_connections: Dict[str, Dict[str, List]],
    ) -> List[NodeView]:
        """
        Find root nodes within a subset of nodes.

        Root nodes are those with no incoming connections from within
        the same subset.

        Args:
            node_views: Mapping of node names to NodeView objects.
            node_connections: Connection data for the subset.

        Returns:
            List of NodeView objects that are root nodes in this subset.
        """
        root_nodes = [
            node
            for name, node in node_views.items()
            if len(node_connections.get(name, {}).get("plugs", [])) == 0
        ]
        return root_nodes

    def _layout_subgraph(
        self,
        root_nodes: List[NodeView],
        node_views: Dict[str, NodeView],
        node_connections: Dict[str, Dict[str, List]],
        layout_config: LayoutConfig,
        start_x: float,
        start_y: float,
    ) -> float:
        """
        Layout a sub-graph of nodes hierarchically.

        Args:
            root_nodes: List of root nodes to start layout from.
            node_views: Mapping of node names to NodeView objects.
            node_connections: Connection data for the sub-graph.
            layout_config: Layout spacing configuration.
            start_x: Starting X position.
            start_y: Starting Y position.

        Returns:
            Maximum Y position used.
        """
        if not root_nodes:
            return start_y

        base_width = root_nodes[0].base_width if root_nodes else 100.0
        current_y_offset = start_y

        for root_node in root_nodes:
            hierarchy_levels = self._build_node_hierarchy_subset(
                root_node, node_views, node_connections
            )

            max_y_position = self._position_hierarchy_nodes(
                hierarchy_levels,
                start_x,
                current_y_offset,
                layout_config,
                base_width,
            )

            current_y_offset = max_y_position

        return current_y_offset

    def _build_node_hierarchy_subset(
        self,
        root_node: NodeView,
        node_views: Dict[str, NodeView],
        node_connections: Dict[str, Dict[str, List]],
    ) -> List[List[tuple]]:
        """
        Build hierarchy for a subset of nodes.

        Similar to _build_node_hierarchy but operates on a subset.

        Args:
            root_node: The root node to start from.
            node_views: Mapping of node names to NodeView objects.
            node_connections: Connection data for the subset.

        Returns:
            List of levels with (node, width, height) tuples.
        """
        hierarchy_levels = [
            [(root_node, root_node.base_width, root_node.height)]
        ]
        visited = {root_node.model.name}

        current_level = 0
        while current_level >= 0:
            has_connections_at_level = False

            for node, _, _ in hierarchy_levels[current_level]:
                # Find connected nodes within the subset
                connected_nodes = []
                node_name = node.model.name

                for conn in node_connections.get(node_name, {}).get(
                    "sockets", []
                ):
                    source_name = conn.model.plug_node
                    if (
                        source_name in node_views
                        and source_name not in visited
                    ):
                        connected_nodes.append(node_views[source_name])
                        visited.add(source_name)

                if connected_nodes:
                    has_connections_at_level = True

                    if len(hierarchy_levels) <= current_level + 1:
                        hierarchy_levels.append([])

                    for connected_node in connected_nodes:
                        hierarchy_levels[current_level + 1].append(
                            (
                                connected_node,
                                connected_node.base_width,
                                connected_node.height,
                            )
                        )

            current_level = (
                current_level + 1 if has_connections_at_level else -1
            )

        return hierarchy_levels

    def _calculate_group_bounds(
        self, node_views: Dict[str, NodeView]
    ) -> Dict[str, float]:
        """
        Calculate the bounding dimensions for a group of nodes.

        Args:
            node_views: Mapping of node names to NodeView objects.

        Returns:
            Dict with 'width' and 'height' keys.
        """
        if not node_views:
            return {"width": 100.0, "height": 100.0}

        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")

        for node in node_views.values():
            pos = node.pos()
            rect = node.boundingRect()

            min_x = min(min_x, pos.x())
            min_y = min(min_y, pos.y())
            max_x = max(max_x, pos.x() + rect.width())
            max_y = max(max_y, pos.y() + rect.height())

        width = max_x - min_x if max_x > min_x else 100.0
        height = max_y - min_y if max_y > min_y else 100.0

        return {"width": width, "height": height}

    def _analyze_inter_group_connections(
        self,
        group_members: Dict[str, List[str]],
        name_to_views: Dict[str, NodeView],
        ungrouped_nodes: List[str],
    ) -> Dict[str, Dict[str, List]]:
        """
        Analyze connections between groups and ungrouped nodes.

        Args:
            group_members: Dict mapping group names to member node names.
            name_to_views: Mapping of node names to NodeView objects.
            ungrouped_nodes: List of ungrouped node names.

        Returns:
            Dict mapping entity names (groups/ungrouped nodes) to their
            inter-entity connections:
            {
                "entity_name": {
                    "outgoing": [list of target entity names],
                    "incoming": [list of source entity names]
                }
            }
        """
        # Build reverse lookup: node_name -> group_name (or None)
        node_to_group: Dict[str, Optional[str]] = {}
        for group_name, members in group_members.items():
            for member in members:
                node_to_group[member] = group_name

        for ungrouped in ungrouped_nodes:
            node_to_group[ungrouped] = None

        # Initialize connection tracking
        inter_connections: Dict[str, Dict[str, List]] = {}
        for group_name in group_members.keys():
            inter_connections[group_name] = {"outgoing": [], "incoming": []}
        for ungrouped in ungrouped_nodes:
            inter_connections[ungrouped] = {"outgoing": [], "incoming": []}

        # Analyze all connections
        for item in self.nodz_scene.connection_items():
            plug_node = item.model.plug_node
            socket_node = item.model.socket_node

            source_entity = node_to_group.get(plug_node)
            target_entity = node_to_group.get(socket_node)

            # For ungrouped nodes, use the node name as entity
            if source_entity is None:
                source_entity = plug_node
            if target_entity is None:
                target_entity = socket_node

            # Skip if same entity (internal connection)
            if source_entity == target_entity:
                continue

            # Record inter-entity connection
            if source_entity in inter_connections:
                if (
                    target_entity
                    not in inter_connections[source_entity]["outgoing"]
                ):
                    inter_connections[source_entity]["outgoing"].append(
                        target_entity
                    )
            if target_entity in inter_connections:
                if (
                    source_entity
                    not in inter_connections[target_entity]["incoming"]
                ):
                    inter_connections[target_entity]["incoming"].append(
                        source_entity
                    )

        return inter_connections

    def _compute_hierarchy_levels(
        self,
        group_names: Set[str],
        root_groups: List[NodeGroupView],
        inter_group_connections: Dict[str, Dict[str, List]],
        group_views: List[NodeGroupView],
    ) -> List[List[NodeGroupView]]:
        """
        Compute hierarchy levels using Kahn's algorithm (topological sort).

        Uses longest path algorithm to ensure each group is placed after
        ALL its dependencies.

        Args:
            group_names: Set of all group names.
            root_groups: List of root groups (no incoming connections).
            inter_group_connections: Inter-group connection data.
            group_views: All group views.

        Returns:
            List of levels, where each level contains NodeGroupView items.
        """
        # Each group's level = max(level of all incoming groups) + 1
        group_levels: Dict[str, int] = {}

        # Initialize root groups at level 0
        for gv in root_groups:
            group_levels[gv.model.name] = 0

        # Calculate in-degree (from other groups only)
        in_degree: Dict[str, int] = {gv.model.name: 0 for gv in group_views}
        for gv in group_views:
            group_name = gv.model.name
            incoming = inter_group_connections.get(group_name, {}).get(
                "incoming", []
            )
            incoming_from_groups = [
                src for src in incoming if src in group_names
            ]
            in_degree[group_name] = len(incoming_from_groups)

        # Process queue starts with root groups (in_degree == 0)
        process_queue = [gv.model.name for gv in root_groups]

        while process_queue:
            current_name = process_queue.pop(0)
            current_level = group_levels.get(current_name, 0)

            # Get outgoing connections to other groups
            outgoing = inter_group_connections.get(current_name, {}).get(
                "outgoing", []
            )

            for target in outgoing:
                if target not in group_names:
                    continue

                # Update target's level to be at least current_level + 1
                target_current_level = group_levels.get(target, 0)
                new_level = current_level + 1
                if new_level > target_current_level:
                    group_levels[target] = new_level

                # Decrease in-degree and add to queue if ready
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    process_queue.append(target)

        # Build levels list from group_levels dict
        max_level = max(group_levels.values()) if group_levels else 0
        levels: List[List[NodeGroupView]] = [[] for _ in range(max_level + 1)]

        for gv in group_views:
            group_name = gv.model.name
            level = group_levels.get(group_name, 0)
            levels[level].append(gv)

        return levels

    def _layout_groups_as_supernodes(
        self,
        group_views: List[NodeGroupView],
        group_dimensions: Dict[str, Dict[str, float]],
        inter_group_connections: Dict[str, Dict[str, List]],
        layout_config: LayoutConfig,
    ) -> None:
        """
        Layout groups as super-nodes based on inter-group connections.

        Groups are positioned hierarchically based on their connections
        to other groups.

        Args:
            group_views: List of NodeGroupView items.
            group_dimensions: Dict of group dimensions (width, height).
            inter_group_connections: Inter-group connection data.
            layout_config: Layout spacing configuration.
        """
        if not group_views:
            return

        # Find root groups (data sources with no incoming connections from
        # other groups). This is opposite of standard node layout which starts
        # from sinks - for groups we show data flow left-to-right.
        group_names = {gv.model.name for gv in group_views}
        root_groups = []

        for gv in group_views:
            group_name = gv.model.name
            incoming = inter_group_connections.get(group_name, {}).get(
                "incoming", []
            )
            incoming_from_groups = [
                src for src in incoming if src in group_names
            ]
            if not incoming_from_groups:
                root_groups.append(gv)

        if not root_groups:
            root_groups = group_views.copy()

        nlog.debug(f"Root groups: {[g.model.name for g in root_groups]}")

        # Layout groups hierarchically
        horizontal_spacing = layout_config["horizontal_spacing"]
        vertical_spacing = layout_config["vertical_spacing"]
        group_padding = layout_config["group_padding"]

        # Compute hierarchy levels using topological sort
        levels = self._compute_hierarchy_levels(
            group_names, root_groups, inter_group_connections, group_views
        )

        positioned_groups: Set[str] = set()

        # Position groups level by level
        current_x = horizontal_spacing

        for level_groups in levels:
            # First pass: calculate max width in this level for right-alignment
            max_width_in_level = 0.0
            for gv in level_groups:
                group_name = gv.model.name
                dims = group_dimensions.get(
                    group_name, {"width": 100.0, "height": 100.0}
                )
                max_width_in_level = max(max_width_in_level, dims["width"])

            # Second pass: position groups right-aligned within the column
            current_y = vertical_spacing

            for gv in level_groups:
                if gv.model.name in positioned_groups:
                    continue

                group_name = gv.model.name
                dims = group_dimensions.get(
                    group_name, {"width": 100.0, "height": 100.0}
                )

                # Right-align: offset by (max_width - group_width)
                right_align_offset = max_width_in_level - dims["width"]
                group_x = current_x + right_align_offset

                # Move all member nodes by the offset from origin
                self._move_group_members_to_position(gv, group_x, current_y)

                positioned_groups.add(group_name)
                current_y += dims["height"] + group_padding + vertical_spacing

            # Move to next column
            current_x += (
                max_width_in_level + group_padding + horizontal_spacing
            )

    def _move_group_members_to_position(
        self,
        group_view: NodeGroupView,
        target_x: float,
        target_y: float,
    ) -> None:
        """
        Move all members of a group so the group starts at target position.

        Args:
            group_view: The NodeGroupView to move.
            target_x: Target X position for the group.
            target_y: Target Y position for the group.
        """
        members = group_view.model.members
        if not members:
            return

        # Find the current bounding box of group members
        min_x = min_y = float("inf")

        for member_name in members:
            node_view = self._find_node_view_by_name(member_name)
            if node_view:
                pos = node_view.pos()
                min_x = min(min_x, pos.x())
                min_y = min(min_y, pos.y())

        if min_x == float("inf"):
            return

        # Calculate offset needed
        offset_x = target_x - min_x
        offset_y = target_y - min_y

        # Move all member nodes
        for member_name in members:
            node_view = self._find_node_view_by_name(member_name)
            if node_view:
                old_pos = node_view.pos()
                new_pos = QtCore.QPointF(
                    old_pos.x() + offset_x, old_pos.y() + offset_y
                )
                node_view.setPos(new_pos)
                self.api.signals.node_moved.emit(member_name, new_pos)

    def _find_node_view_by_name(self, name: str) -> Optional[NodeView]:
        """
        Find a NodeView by its model name.

        Args:
            name: The node name to search for.

        Returns:
            The NodeView if found, None otherwise.
        """
        for node_view in self.nodz_scene.node_items():
            if node_view.model.name == name:
                return node_view
        return None

    def _layout_ungrouped_nodes(
        self,
        ungrouped_nodes: List[str],
        name_to_views: Dict[str, NodeView],
        group_views: List[NodeGroupView],
        inter_connections: Dict[str, Dict[str, List]],
        layout_config: LayoutConfig,
    ) -> None:
        """
        Layout ungrouped nodes based on their connections to groups.

        Args:
            ungrouped_nodes: List of ungrouped node names.
            name_to_views: Mapping of node names to NodeView objects.
            group_views: List of NodeGroupView items.
            inter_connections: Inter-entity connection data.
            layout_config: Layout spacing configuration.
        """
        if not ungrouped_nodes:
            return

        horizontal_spacing = layout_config["horizontal_spacing"]
        vertical_spacing = layout_config["vertical_spacing"]

        # Find the rightmost edge of all groups
        max_group_x = 0.0
        for gv in group_views:
            for member_name in gv.model.members:
                node_view = self._find_node_view_by_name(member_name)
                if node_view:
                    pos = node_view.pos()
                    rect = node_view.boundingRect()
                    max_group_x = max(max_group_x, pos.x() + rect.width())

        # Build subset mapping for ungrouped nodes
        ungrouped_views = {
            name: name_to_views[name]
            for name in ungrouped_nodes
            if name in name_to_views
        }

        # Analyze connections only among ungrouped nodes
        ungrouped_connections = self._analyze_internal_connections(
            ungrouped_views
        )

        # Find root nodes among ungrouped
        root_nodes = self._find_root_nodes_in_subset(
            ungrouped_views, ungrouped_connections
        )
        if not root_nodes:
            root_nodes = list(ungrouped_views.values())

        # Position ungrouped nodes to the right of groups
        start_x = max_group_x + horizontal_spacing * 2
        start_y = vertical_spacing

        self._layout_subgraph(
            root_nodes,
            ungrouped_views,
            ungrouped_connections,
            layout_config,
            start_x,
            start_y,
        )

    def _update_group_rects_after_layout(
        self,
        group_views: List[NodeGroupView],
        name_to_views: Dict[str, NodeView],
    ) -> None:
        """
        Update group rectangles to fit their member nodes after layout.

        Args:
            group_views: List of NodeGroupView items.
            name_to_views: Mapping of node names to NodeView objects.
        """
        for group_view in group_views:
            group_view.update_rect_from_members(name_to_views)

    def _get_all_node_views(self) -> List[NodeView]:
        """Get all NodeView items from the scene."""
        return self.nodz_scene.node_items()

    def _build_node_mapping(
        self, node_views: List[NodeView]
    ) -> Dict[str, NodeView]:
        """
        Build a mapping from node names to NodeView objects.

        Args:
            node_views: List of NodeView objects

        Returns:
            Dictionary mapping node names to NodeView objects

        Raises:
            ValueError: If nodes have invalid models or duplicate names
        """
        name_to_views = {}

        for node in node_views:
            node_name = node.model.name
            if not node_name:
                nlog.warning("Node has empty name, skipping")
                continue

            if node_name in name_to_views:
                nlog.warning(
                    f"Duplicate node name '{node_name}', using latest instance"
                )

            name_to_views[node_name] = node

        return name_to_views

    def _analyze_node_connections(
        self, name_to_views: Dict[str, NodeView]
    ) -> Dict[str, Dict[str, List]]:
        """
        Analyze all connections in the scene and categorize them by node.

        Args:
            name_to_views: Mapping of node names to NodeView objects

        Returns:
            Dict mapping node names to their connection data:
            {
                "node_name": {
                    "plugs": [list of outgoing connections],
                    "sockets": [list of incoming connections]
                }
            }
        """
        node_connections = {
            name: {"plugs": [], "sockets": []} for name in name_to_views.keys()
        }

        # Collect all connection views from the scene
        for item in self.nodz_scene.connection_items():
            plug_node = item.model.plug_node
            socket_node = item.model.socket_node

            # Validate node names exist in our mapping
            if plug_node not in name_to_views:
                nlog.warning(
                    f"Connection references unknown plug node '{plug_node}', skipping"
                )
                continue

            if socket_node not in name_to_views:
                nlog.warning(
                    f"Connection references unknown socket node '{socket_node}', skipping"
                )
                continue

            # Add connection to the appropriate node's lists
            node_connections[plug_node]["plugs"].append(item)
            node_connections[socket_node]["sockets"].append(item)

        return node_connections

    def _find_root_nodes(
        self,
        name_to_views: Dict[str, NodeView],
        node_connections: Dict[str, Dict[str, List]],
    ) -> List[NodeView]:
        """
        Find root nodes (nodes with no incoming connections).

        Args:
            name_to_views: Mapping of node names to NodeView objects
            node_connections: Connection data for each node

        Returns:
            List of NodeView objects that are root nodes
        """
        return self._find_root_nodes_in_subset(name_to_views, node_connections)

    def _get_layout_config(self) -> LayoutConfig:
        """
        Get layout configuration values with fallback defaults.

        Returns:
            LayoutConfig with spacing values for graph layout.
        """
        try:
            horizontal_spacing = self.config.get(
                "horizontal_node_spacing", 80.0
            )
            vertical_spacing = self.config.get("vertical_node_spacing", 40.0)
            group_padding = self.config.get("group_padding", 50.0)

            return LayoutConfig(
                horizontal_spacing=float(horizontal_spacing),
                vertical_spacing=float(vertical_spacing),
                group_padding=float(group_padding),
            )
        except (KeyError, TypeError, ValueError) as e:
            nlog.warning(f"Error reading layout config: {e}, using defaults")
            return LayoutConfig(
                horizontal_spacing=80.0,
                vertical_spacing=40.0,
                group_padding=50.0,
            )

    def _layout_node_hierarchies(
        self,
        root_nodes: List[NodeView],
        name_to_views: Dict[str, NodeView],
        node_connections: Dict[str, Dict[str, List]],
        layout_config: LayoutConfig,
    ) -> None:
        """
        Layout each root node hierarchy separately.

        Args:
            root_nodes: List of root nodes to layout
            name_to_views: Mapping of node names to NodeView objects
            node_connections: Connection data for each node
            layout_config: Layout spacing configuration
        """
        start_x_position = layout_config["horizontal_spacing"]
        current_y_offset = 0

        for root_node in root_nodes:
            # Build the hierarchy tree for this root node
            hierarchy_levels = self._build_node_hierarchy(
                root_node, name_to_views, node_connections
            )

            # Position nodes in this hierarchy
            max_y_position = self._position_hierarchy_nodes(
                hierarchy_levels,
                start_x_position,
                current_y_offset,
                layout_config,
                root_nodes[0].base_width,
            )

            # Update y offset for next root node hierarchy
            current_y_offset = max_y_position

    def _build_node_hierarchy(
        self,
        root_node: NodeView,
        name_to_views: Dict[str, NodeView],
        node_connections: Dict[str, Dict[str, List]],
    ) -> List[List[tuple]]:
        """
        Build a hierarchical representation of nodes starting from a root node.

        Args:
            root_node: The root node to start from
            name_to_views: Mapping of node names to NodeView objects
            node_connections: Connection data for each node

        Returns:
            List of levels, where each level contains tuples of (node, width, height)
        """
        # Initialize with root node at level 0
        hierarchy_levels = [
            [(root_node, root_node.base_width, root_node.height)]
        ]

        current_level = 0
        while current_level >= 0:
            has_connections_at_level = False

            # Process each node at the current level
            for node, _, _ in hierarchy_levels[current_level]:
                # Find all nodes connected to this node's sockets
                connected_nodes = self._find_connected_nodes(
                    node, name_to_views, node_connections
                )

                if connected_nodes:
                    has_connections_at_level = True

                    # Ensure next level exists
                    if len(hierarchy_levels) <= current_level + 1:
                        hierarchy_levels.append([])

                    # Add connected nodes to next level
                    for connected_node in connected_nodes:
                        hierarchy_levels[current_level + 1].append(
                            (
                                connected_node,
                                connected_node.base_width,
                                connected_node.height,
                            )
                        )

            # Move to next level if there were connections, otherwise stop
            current_level = (
                current_level + 1 if has_connections_at_level else -1
            )

        return hierarchy_levels

    def _find_connected_nodes(
        self,
        node: NodeView,
        name_to_views: Dict[str, NodeView],
        node_connections: Dict[str, Dict[str, List]],
    ) -> List[NodeView]:
        """
        Find all nodes connected to the given node's sockets.

        Args:
            node: The node to find connections for
            name_to_views: Mapping of node names to NodeView objects
            node_connections: Connection data for each node

        Returns:
            List of NodeView objects connected to this node
        """
        connected_nodes = []

        node_name = node.model.name
        if node_name not in node_connections:
            nlog.warning(f"Node '{node_name}' not found in connection data")
            return connected_nodes

        # Check each socket attribute of the node
        try:
            for attribute_name, socket in node.sockets.items():
                if attribute_name not in node.model.attributes:
                    continue

                # Find connections to this socket
                for connection in node_connections[node_name]["sockets"]:
                    source_node_name = connection.model.plug_node
                    if source_node_name in name_to_views:
                        source_node = name_to_views[source_node_name]
                        connected_nodes.append(source_node)
                    else:
                        nlog.warning(
                            f"Connected node '{source_node_name}' not found in node mapping"
                        )

        except (AttributeError, KeyError, TypeError) as e:
            nlog.warning(
                f"Error finding connected nodes for '{node_name}': {e}"
            )

        return connected_nodes

    def _position_hierarchy_nodes(
        self,
        hierarchy_levels: List[List[tuple]],
        start_x: float,
        start_y: float,
        layout_config: LayoutConfig,
        base_node_width: float,
    ) -> float:
        """
        Position nodes within a hierarchy based on their levels.

        Args:
            hierarchy_levels: List of levels with node data
            start_x: Starting X position
            start_y: Starting Y position
            layout_config: Layout spacing configuration
            base_node_width: Width of nodes for spacing calculations

        Returns:
            Maximum Y position used
        """
        max_y_position = 0
        positioned_nodes = set()

        horizontal_spacing = layout_config["horizontal_spacing"]
        vertical_spacing = layout_config["vertical_spacing"]

        for level_index, level_nodes in enumerate(hierarchy_levels):
            # Calculate X position for this level (moving left to right)
            x_position = start_x - level_index * (
                base_node_width + horizontal_spacing
            )
            y_position = start_y + vertical_spacing

            # Position each node in this level
            for node, _, node_height in level_nodes:
                if node not in positioned_nodes:
                    position = QtCore.QPointF(x_position, y_position)
                    node.setPos(position)
                    positioned_nodes.add(node)

                    # Emit node_moved signal for programmatic positioning
                    self.api.signals.node_moved.emit(node.model.name, position)

                    # Move to next vertical position
                    y_position += node_height + vertical_spacing

            max_y_position = max(max_y_position, y_position)

        return max_y_position

    def _finalize_layout(self) -> None:
        """Update connections, center graph, and refresh the view."""
        self._update_all_connections()
        self.scene().update()
        self._center_graph_in_scene()
        self.frame_all()

    def _find_intersecting_connections(
        self, line_start: QtCore.QPointF, line_end: QtCore.QPointF
    ) -> list:
        """Find all connections that intersect with the given line."""
        intersecting_connections = []

        # Find all connection views in the scene
        for item in self.nodz_scene.connection_items():
            # Get connection endpoints
            conn_start = item.source_point
            conn_end = item.target_point

            # Check if the line intersects with the connection
            if self._lines_intersect(
                line_start, line_end, conn_start, conn_end
            ):
                intersecting_connections.append(item)

        return intersecting_connections

    def _lines_intersect(
        self,
        line1_start: QtCore.QPointF,
        line1_end: QtCore.QPointF,
        line2_start: QtCore.QPointF,
        line2_end: QtCore.QPointF,
    ) -> bool:
        """Check if two line segments intersect using the cross product
        method."""

        def ccw(A, B, C):
            """Check if three points are in counter-clockwise order."""
            return (C.y() - A.y()) * (B.x() - A.x()) > (B.y() - A.y()) * (
                C.x() - A.x()
            )

        # Two line segments intersect if the endpoints of each segment are on
        # opposite sides of the other segment
        return ccw(line1_start, line2_start, line2_end) != ccw(
            line1_end, line2_start, line2_end
        ) and ccw(line1_start, line1_end, line2_start) != ccw(
            line1_start, line1_end, line2_end
        )

    def _update_connection_z_values(self) -> None:
        """Update Z values of connections based on node selection."""
        # Get all selected nodes
        selected_nodes = set()
        for item in self.nodz_scene.selectedItems():
            if isinstance(item, NodeView):
                selected_nodes.add(item.model.name)
                item.setZValue(NODE_Z_UP)

        # Find all connection views and update their Z values
        for item in self.nodz_scene.connection_items():
            # Check if either end of the connection is connected to a selected
            # node
            is_connected_to_selected = (
                item.model.plug_node in selected_nodes
                or item.model.socket_node in selected_nodes
            )

            # Set Z value based on selection
            if is_connected_to_selected:
                # Raise above normal connections and nodes
                item.setZValue(CNCT_Z_UP)
            else:
                # Default Z value for unselected connections
                item.setZValue(CNCT_Z)
            # print(f"{item}: {item.zValue()}")

    def _update_all_connections(self) -> None:
        """Update all connection paths in the scene."""
        # Find all connection views in the scene
        for item in self.nodz_scene.connection_items():
            # Find the source and target views
            source_node = None
            target_node = None

            for node_item in self.nodz_scene.items():
                if not isinstance(node_item, NodeView):
                    continue

                if node_item.model.name == item.model.plug_node:
                    source_node = node_item
                elif node_item.model.name == item.model.socket_node:
                    target_node = node_item

                if source_node and target_node:
                    break

            # Update connection endpoints
            if (
                isinstance(source_node, NodeView)
                and item.model.plug_attr in source_node.plugs
            ):
                plug = source_node.plugs[item.model.plug_attr]
                item.source_point = plug.center()

            if (
                isinstance(target_node, NodeView)
                and item.model.socket_attr in target_node.sockets
            ):
                socket = target_node.sockets[item.model.socket_attr]
                item.target_point = socket.center()

            # Update the path
            item.update_path()

        # Update connection Z values after updating paths
        self._update_connection_z_values()

    def _snap_selected_nodes_to_grid(self) -> None:
        """Snap all selected nodes to the grid."""
        grid_size = self.config["grid_size"]

        # Get all selected node views
        selected_nodes = [
            item
            for item in self.nodz_scene.selectedItems()
            if isinstance(item, NodeView)
        ]

        for node in selected_nodes:
            # Get current position
            current_pos = node.pos()

            # Calculate snapped position
            snapped_x = round(current_pos.x() / grid_size) * grid_size
            snapped_y = round(current_pos.y() / grid_size) * grid_size
            snapped_pos = QtCore.QPointF(snapped_x, snapped_y)

            # Set the snapped position
            node.setPos(snapped_pos)

            # Update model position if it exists
            if isinstance(node, NodeView):
                node.model._position = snapped_pos

        # Update all connections after snapping
        self._update_all_connections()

    def get_viewport_framing(self) -> Dict[str, Any]:
        """
        Get the current viewport framing settings.

        Returns:
            Dictionary containing the visible scene rectangle that can be
            used with fitInView() to restore the current view.
        """
        # Get the currently visible scene rectangle
        viewport_rect = self.viewport().rect()
        visible_scene_rect = self.mapToScene(viewport_rect).boundingRect()

        return {
            "visible_rect": [
                visible_scene_rect.x(),
                visible_scene_rect.y(),
                visible_scene_rect.width(),
                visible_scene_rect.height(),
            ]
        }

    def set_viewport_framing(self, framing_data: Dict[str, Any]) -> None:
        """
        Restore the viewport framing settings.

        Args:
            framing_data: Dictionary containing viewport settings as returned by
                         get_viewport_framing()
        """
        if not isinstance(framing_data, dict):
            raise ValueError("framing_data must be a dictionary")

        if "visible_rect" not in framing_data:
            raise ValueError("framing_data must contain 'visible_rect'")

        visible_rect_list = framing_data["visible_rect"]
        if (
            not isinstance(visible_rect_list, list)
            or len(visible_rect_list) != 4
        ):
            raise ValueError(
                "'visible_rect' must be a list of 4 numbers [x, y, width, height]"
            )

        # Create QRectF from the stored rectangle
        visible_rect = QtCore.QRectF(
            visible_rect_list[0],
            visible_rect_list[1],
            visible_rect_list[2],
            visible_rect_list[3],
        )

        # Use fitInView to restore the exact view
        self.fitInView(visible_rect, QtCore.Qt.AspectRatioMode.KeepAspectRatio)


def create_nodz_view(
    parent: Optional[QtWidgets.QWidget] = None,
    config_path: str = DEFAULT_CONFIG_PATH,
) -> NodzView:
    """Create a Nodz view."""
    return NodzView(parent, config_path)


if __name__ == "__main__":
    # Create application
    app = QtWidgets.QApplication(sys.argv)

    # Create Nodz view
    nodz = create_nodz_view()
    nodz.setWindowTitle("Nodz MVC Demo")
    nodz.resize(800, 600)
    nodz.show()

    # Create some test nodes
    nodz.api.create_node("Node A", "node_preset_1", QtCore.QPointF(100, 100))
    nodz.api.create_attribute(
        "Node A", "Attr 1", plug=True, socket=False, data_type=str
    )
    nodz.api.create_attribute(
        "Node A", "Attr 2", plug=True, socket=True, data_type=int
    )

    nodz.api.create_node("Node B", "node_preset_1", QtCore.QPointF(300, 100))
    nodz.api.create_attribute(
        "Node B", "Attr 1", plug=False, socket=True, data_type=str
    )
    nodz.api.create_attribute(
        "Node B", "Attr 2", plug=False, socket=True, data_type=int
    )

    # Create a connection
    nodz.api.create_connection("Node A", "Attr 1", "Node B", "Attr 1")

    # Run application
    sys.exit(app.exec_())
