from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from qtpy import QtCore, QtGui


class UnknownShapeError(BaseException):
    pass


@dataclass
class SlotShapeDef:
    shape: str
    color: list[int]
    connection_width: int
    border_width: int
    border_color: list[int]
    draw_calls: list = field(default_factory=list)


class PrimType(Enum):
    Ellipse = 0
    Rect = 1
    RoundedRect = 2
    Polygon = 3


@dataclass
class RectPrim:
    type: PrimType
    points: list
    radius: float = 0.3
    rect: QtCore.QRectF = field(default_factory=QtCore.QRectF)

    def __post_init__(self):
        if len(self.points) != 2:
            raise ValueError(
                "Need 2 points to define a bounding rect ! "
                f"(got {len(self.points)})"
            )
        self.rect = QtCore.QRectF(*self.points[0], *self.points[1])

    def draw(self, painter: QtGui.QPainter, rect: QtCore.QRectF):
        r = QtCore.QRectF(self.rect)
        r.setWidth(r.width() * rect.width())
        r.setHeight(r.height() * rect.height())
        r.moveCenter(rect.center())
        if self.type == PrimType.Ellipse:
            painter.drawEllipse(r)
        elif self.type == PrimType.Rect:
            painter.drawRect(r)
        elif self.type == PrimType.RoundedRect:
            radius = self.radius * rect.width()
            painter.drawRoundedRect(r, radius, radius)


@dataclass
class PolygonPrim:
    type: PrimType
    vertices: list

    def draw(self, painter: QtGui.QPainter, rect: QtCore.QRectF):
        vtx = [
            QtCore.QPointF(
                v[0] * rect.width() + rect.x(),
                v[1] * rect.height() + rect.y(),
            )
            for v in self.vertices
        ]
        painter.drawPolygon(vtx)


class SlotDrawer:
    _instance = None
    _initialized = False

    def __new__(cls, config: Optional[dict] = None):
        """Create or return singleton instance with double-checked locking."""
        if cls._instance is None:
            cls._instance = super(SlotDrawer, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[dict] = None):
        if SlotDrawer._initialized:
            return

        if config is None:
            raise ValueError(
                "First call to SlotDrawer must include the config !"
            )

        # draw calls for named shapes
        self.shape_defs = config.get("shapes_definitions", {})
        if "circle" not in self.shape_defs:
            self.shape_defs["circle"] = (
                [{"ellipse": [(0.0, 0.0), (1.0, 1.0)]}],
            )

        # shape definitions
        tmp_slot_shapes = config.get("slot_shapes", {})
        if "default" not in tmp_slot_shapes:
            tmp_slot_shapes["default"] = {
                "shape": "circle",
                "color": [255, 155, 0],
                "connection_width": 2,
                "border_width": 1,
                "border_color": [200, 120, 0],
            }
        self.slot_shapes: dict[str, SlotShapeDef] = {}
        for k, v in tmp_slot_shapes.items():
            if v["shape"] not in self.shape_defs:
                raise UnknownShapeError(f"{k} = {v}")
            obj = SlotShapeDef(**v)
            drawcalls: list = self.shape_defs.get(
                obj.shape, self.shape_defs.get("circle")
            )
            for dc in drawcalls:
                if "ellipse" in dc:
                    obj.draw_calls.append(
                        RectPrim(type=PrimType.Ellipse, points=dc["ellipse"])
                    )
                elif "rect" in dc:
                    obj.draw_calls.append(
                        RectPrim(type=PrimType.Rect, points=dc["rect"])
                    )
                elif "rounded_rect" in dc:
                    obj.draw_calls.append(
                        RectPrim(
                            type=PrimType.RoundedRect,
                            points=dc["rounded_rect"],
                            radius=dc["radius"],
                        )
                    )
                elif "polygon" in dc:
                    obj.draw_calls.append(
                        PolygonPrim(
                            type=PrimType.Polygon, vertices=dc["polygon"]
                        )
                    )
            self.slot_shapes[k] = obj

        # ready to go !
        SlotDrawer._initialized = True

    def connection_pen(self, data_type: Any) -> QtGui.QPen:
        slot_def = self.slot_shapes.get(
            str(data_type), self.slot_shapes["default"]
        )
        pen = QtGui.QPen(QtGui.QColor(*slot_def.color))
        pen.setWidth(slot_def.connection_width)
        return pen

    def pen_and_brush(self, data_type: Any) -> tuple[QtGui.QPen, QtGui.QBrush]:
        slot_def = self.slot_shapes.get(
            str(data_type), self.slot_shapes["default"]
        )
        brush = QtGui.QBrush(QtGui.QColor(*slot_def.color))
        pen = QtGui.QPen(QtGui.QColor(*slot_def.border_color))
        pen.setWidth(slot_def.border_width)
        return pen, brush

    def paint(
        self,
        data_type: Any,
        painter: QtGui.QPainter,
        rect: QtCore.QRectF,
    ):
        slot_def = self.slot_shapes.get(
            str(data_type), self.slot_shapes["default"]
        )
        for prim in slot_def.draw_calls:
            prim.draw(painter, rect)
