"""
Main module for Nodz.

This module provides the main entry point for the Nodz graph editor.
It demonstrates how to use the MVC architecture to create a Nodz application.
"""

import os
import sys
from typing import Any, Dict, Optional, Union
from qtpy import QtCore, QtGui, QtWidgets

from .views import NodeView, ConnectionView, SlotType
from .controllers import NodzAPI


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

    def get_slot_connections(self, slot) -> list:
        """Get all connections attached to a slot."""
        connections = []

        # Find all connection views in the scene
        for item in self.items():
            # Check if it's a connection view
            if not isinstance(item, ConnectionView):
                continue

            # Check if it has the necessary attributes
            if not hasattr(item, "model"):
                continue

            if (
                not hasattr(item.model, "plug_node")
                or not hasattr(item.model, "plug_attr")
                or not hasattr(item.model, "socket_node")
                or not hasattr(item.model, "socket_attr")
            ):
                continue

            # Check if this connection is connected to the slot
            if (
                not hasattr(slot, "parentItem")
                or not hasattr(slot.parentItem(), "model")
                or not hasattr(slot.parentItem().model, "name")
                or not hasattr(slot, "model")
                or not hasattr(slot.model, "attribute")
            ):
                continue

            node_name = slot.parentItem().model.name
            attr_name = slot.model.attribute

            if (
                hasattr(slot, "slot_type")
                and slot.slot_type == SlotType.PLUG
                and item.model.plug_node == node_name
                and item.model.plug_attr == attr_name
            ):
                connections.append(item)
            elif (
                hasattr(slot, "slot_type")
                and slot.slot_type == SlotType.SOCKET
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

        # Setup view
        self._setup_view()

        # Create scene
        self.nodz_scene = NodzScene(self, self.config)
        self.setScene(self.nodz_scene)

        # Create API
        self.api = NodzAPI(self.nodz_scene, self.config)

        self._show_help = True
        self._viewport_help_document = None

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
        if not self._show_help:
            return
        vp_bottom_left = self.viewport().rect().bottomLeft()
        painter.resetTransform()
        if not self._viewport_help_document:
            h_str = (
                "*Keyboard Shortcuts:*   \n\n"
                "**L**: Layout graph    "
                "**A**: Frame all nodes    "
                "**F**: Frame selection    "
                "**H**: Toggle help overlay    "
                "**Del/Backspace**: Delete selection    \n\n"
                "**Shift+Click**: Add to selection    "
                "**Ctrl+Click**: Remove from selection    "
                "**Alt+Drag**: Cut connections    "
                "**S-down**: Snap to grid"
            )
            self._viewport_help_document = QtGui.QTextDocument()
            font_size = painter.fontInfo().pointSize()
            self._viewport_help_document.setDefaultFont(
                QtGui.QFont(painter.font().family(), max(10, font_size - 2))
            )
            self._viewport_help_document.setMarkdown(h_str)
        painter.translate(
            QtCore.QPoint(vp_bottom_left.x() + 20, vp_bottom_left.y() - 80)
        )
        painter.setOpacity(0.5)
        self._viewport_help_document.drawContents(painter)

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
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.RubberBandDrag)
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
                if hasattr(connection, "model"):
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

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Handle key press events."""
        # Frame all nodes with 'A'
        if event.key() == QtCore.Qt.Key.Key_A:
            self.frame_all()
        # Frame selected nodes with 'F'
        elif event.key() == QtCore.Qt.Key.Key_F:
            self.frame_selected()
        # show help overlay with 'H'
        elif event.key() == QtCore.Qt.Key.Key_H:
            self._show_help = False if self._show_help else True
            self.scene().update()
        # Layout graph with 'L'
        elif event.key() == QtCore.Qt.Key.Key_L:
            self.layout_graph()
        # Enable grid snapping with 'S' (hold down)
        elif event.key() == QtCore.Qt.Key.Key_S:
            if (
                not event.isAutoRepeat()
            ):  # Only on first press, not auto-repeat
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
            if (
                not event.isAutoRepeat()
            ):  # Only on actual release, not auto-repeat
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
            if isinstance(item, NodeView)
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
            if isinstance(item, NodeView)
        ]

        if not selected_nodes:
            # If no nodes are selected, do nothing
            return

        # Delete each selected node using the API
        for node in selected_nodes:
            if hasattr(node.model, "name"):
                self.api.delete_node(node.model.name)

    def layout_graph(self) -> None:
        """Layout the graph automatically based on node ranking."""
        # Get all node views
        node_views = [
            item
            for item in self.nodz_scene.items()
            if isinstance(item, NodeView)
        ]

        if not node_views:
            return

        # Create a mapping from node name to node view
        node_view_map = {
            node_view.model.name: node_view for node_view in node_views
        }

        # Get all connections
        connections = []
        for item in self.nodz_scene.items():
            if isinstance(item, ConnectionView):
                connections.append(
                    (item.model.plug_node, item.model.socket_node)
                )

        # Calculate node ranks
        ranks = {}
        incoming_connections = {
            node_name: 0 for node_name in node_view_map.keys()
        }

        # Count incoming connections for each node
        for source, target in connections:
            if target in incoming_connections:
                incoming_connections[target] += 1

        # Assign rank 0 to nodes with no incoming connections
        rank = 0
        remaining_nodes = set(node_view_map.keys())

        while remaining_nodes:
            # Find nodes with no incoming connections
            current_rank_nodes = [
                node
                for node in remaining_nodes
                if incoming_connections[node] == 0
            ]

            if not current_rank_nodes:
                # Handle cycles by assigning the current rank to a node and
                # decrementing its incoming count
                node = next(iter(remaining_nodes))
                ranks[node] = rank
                remaining_nodes.remove(node)

                # Decrement incoming count for nodes connected to this node
                for source, target in connections:
                    if source == node and target in remaining_nodes:
                        incoming_connections[target] -= 1
            else:
                # Assign current rank to nodes
                for node in current_rank_nodes:
                    ranks[node] = rank
                    remaining_nodes.remove(node)

                # Decrement incoming count for nodes connected to current
                # rank nodes
                for source, target in connections:
                    if (
                        source in current_rank_nodes
                        and target in remaining_nodes
                    ):
                        incoming_connections[target] -= 1

                # Move to next rank
                rank += 1

        # Group nodes by rank
        nodes_by_rank = {}
        for node_name, node_rank in ranks.items():
            if node_rank not in nodes_by_rank:
                nodes_by_rank[node_rank] = []
            nodes_by_rank[node_rank].append(node_name)

        # Layout nodes in columns based on rank
        grid_size = self.config["grid_size"]
        max_width = 0
        max_height = 0

        # Find maximum node dimensions
        for node_view in node_views:
            rect = node_view.boundingRect()
            max_width = max(max_width, rect.width())
            max_height = max(max_height, rect.height())

        # Add padding
        column_width = max_width + grid_size * 4
        row_height = max_height + grid_size * 2

        # Position nodes
        for rank, nodes in sorted(nodes_by_rank.items()):
            # Sort nodes within the same rank (optional)
            nodes.sort()

            # Position nodes in this rank
            for i, node_name in enumerate(nodes):
                node_view = node_view_map[node_name]

                # Calculate position
                x = rank * column_width
                y = i * row_height

                # Set position
                node_view.setPos(x, y)

                # Update model position directly without triggering
                # notifications
                if hasattr(node_view.model, "_position"):
                    node_view.model._position = QtCore.QPointF(x, y)

        # Calculate the bounding rectangle of all nodes
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")

        for node_view in node_views:
            rect = node_view.boundingRect()
            pos = node_view.pos()
            min_x = min(min_x, pos.x())
            min_y = min(min_y, pos.y())
            max_x = max(max_x, pos.x() + rect.width())
            max_y = max(max_y, pos.y() + rect.height())

        # Calculate the center of the nodes
        nodes_center_x = (min_x + max_x) / 2
        nodes_center_y = (min_y + max_y) / 2

        # Calculate the center of the scene
        scene_center_x = self.nodz_scene.sceneRect().width() / 2
        scene_center_y = self.nodz_scene.sceneRect().height() / 2

        # Calculate the offset to center the nodes
        offset_x = scene_center_x - nodes_center_x
        offset_y = scene_center_y - nodes_center_y

        # Apply the offset to all nodes
        for node_view in node_views:
            pos = node_view.pos()
            node_view.setPos(pos.x() + offset_x, pos.y() + offset_y)

            # Update model position directly without triggering notifications
            if hasattr(node_view, "model") and hasattr(
                node_view.model, "_position"
            ):
                node_view.model._position = QtCore.QPointF(
                    pos.x() + offset_x, pos.y() + offset_y
                )

        # Update all connections
        self._update_all_connections()

        # Frame all nodes
        self.frame_all()

    def _find_intersecting_connections(
        self, line_start: QtCore.QPointF, line_end: QtCore.QPointF
    ) -> list:
        """Find all connections that intersect with the given line."""
        intersecting_connections = []

        # Find all connection views in the scene
        for item in self.nodz_scene.items():
            # Check if it's a connection view
            if not isinstance(item, ConnectionView):
                continue

            # Check if it has the necessary attributes
            if (
                not hasattr(item, "model")
                or not hasattr(item, "source_point")
                or not hasattr(item, "target_point")
            ):
                continue

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

        # Find all connection views and update their Z values
        for item in self.nodz_scene.items():
            # Check if it's a connection view
            if not isinstance(item, ConnectionView):
                continue

            # Check if it has the necessary attributes
            if not hasattr(item, "model"):
                continue

            if not hasattr(item.model, "plug_node") or not hasattr(
                item.model, "socket_node"
            ):
                continue

            # Check if either end of the connection is connected to a selected
            # node
            is_connected_to_selected = (
                item.model.plug_node in selected_nodes
                or item.model.socket_node in selected_nodes
            )

            # Set Z value based on selection
            if is_connected_to_selected:
                item.setZValue(2)  # Raise above normal connections and nodes
            else:
                item.setZValue(
                    -1
                )  # Default Z value for unselected connections

    def _update_all_connections(self) -> None:
        """Update all connection paths in the scene."""
        # Find all connection views in the scene
        for item in self.nodz_scene.items():
            # Check if it's a connection view
            if not isinstance(item, ConnectionView):
                continue

            # Check if it has the necessary attributes
            if not hasattr(item, "model") or not hasattr(item, "update_path"):
                continue

            if (
                not hasattr(item.model, "plug_node")
                or not hasattr(item.model, "plug_attr")
                or not hasattr(item.model, "socket_node")
                or not hasattr(item.model, "socket_attr")
            ):
                continue

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
                source_node
                and hasattr(source_node, "plugs")
                and item.model.plug_attr in source_node.plugs
            ):
                plug = source_node.plugs[item.model.plug_attr]
                if hasattr(plug, "center"):
                    item.source_point = plug.center()

            if (
                target_node
                and hasattr(target_node, "sockets")
                and item.model.socket_attr in target_node.sockets
            ):
                socket = target_node.sockets[item.model.socket_attr]
                if hasattr(socket, "center"):
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
            if hasattr(node, "model") and hasattr(node.model, "_position"):
                node.model._position = snapped_pos

        # Update all connections after snapping
        self._update_all_connections()


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
