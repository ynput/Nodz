import json
import re
import logging
from qtpy import QtCore, QtGui

logging.basicConfig(
    format="[%(name)s]  %(levelname)8s  %(msg)s",
    level=logging.INFO,
)
nlog = logging.getLogger("Nodz")


def _convertDataToColor(
    data: list, alternate: bool = False, av: int = 20
) -> QtGui.QColor:
    """
    Convert a list of 3 (rgb) or 4(rgba) values from the configuration
    file into a QColor.

    :param data: Input color.
    :type  data: List.

    :param alternate: Whether or not this is an alternate color.
    :type  alternate: Bool.

    :param av: Alternate value.
    :type  av: Int.

    """
    # rgb
    if len(data) == 3:
        color = QtGui.QColor(data[0], data[1], data[2])
        if alternate:
            mult = _generateAlternateColorMultiplier(color, av)

            color = QtGui.QColor(
                max(0, data[0] - (av * mult)),
                max(0, data[1] - (av * mult)),
                max(0, data[2] - (av * mult)),
            )
        return color

    # rgba
    elif len(data) == 4:
        color = QtGui.QColor(data[0], data[1], data[2], data[3])
        if alternate:
            mult = _generateAlternateColorMultiplier(color, av)
            color = QtGui.QColor(
                max(0, data[0] - (av * mult)),
                max(0, data[1] - (av * mult)),
                max(0, data[2] - (av * mult)),
                data[3],
            )
        return color

    # wrong
    else:
        nlog.warning(f"Color from configuration is not recognized : {data}")
        nlog.info("Can only be [R, G, B] or [R, G, B, A]")
        nlog.info("Using default color !")
        color = QtGui.QColor(120, 120, 120)
        if alternate:
            color = QtGui.QColor(120 - av, 120 - av, 120 - av)
        return color


def _generateAlternateColorMultiplier(color: QtGui.QColor, av: int) -> float:
    """
    Generate a multiplier based on the input color lighness to increase
    the alternate value for dark color or reduce it for bright colors.

    :param color: Input color.
    :type  color: QColor.

    :param av: Alternate value.
    :type  av: Int.

    """
    lightness = color.lightness()
    mult = float(lightness) / 255

    return mult


def _createPointerBoundingBox(
    pointerPos: QtCore.QPoint, bbSize: int
) -> QtCore.QRectF:
    """
    generate a bounding box around the pointer.

    :param pointerPos: Pointer position.
    :type  pointerPos: QPoint.

    :param bbSize: Width and Height of the bounding box.
    :type  bbSize: Int.

    """
    # Create pointer's bounding box.
    point = pointerPos

    mbbPos = point
    point.setX(int(point.x() - bbSize / 2))
    point.setY(int(point.y() - bbSize / 2))

    size = QtCore.QSize(bbSize, bbSize)
    bb = QtCore.QRect(mbbPos, size).toRectF()

    return bb


def _swapListIndices(inputList: list, oldIndex: int, newIndex: int) -> None:
    """
    Simply swap 2 indices in a the specified list.

    :param inputList: List that contains the elements to swap.
    :type  inputList: List.

    :param oldIndex: Index of the element to move.
    :type  oldIndex: Int.

    :param newIndex: Destination index of the element.
    :type  newIndex: Int.

    """
    if oldIndex == -1:
        oldIndex = len(inputList) - 1

    if newIndex == -1:
        newIndex = len(inputList)

    value = inputList[oldIndex]
    inputList.pop(oldIndex)
    inputList.insert(newIndex, value)


# IO
def _loadConfig(filePath: str) -> dict:
    """
    Read the configuration file and strips out comments.

    :param filePath: File path.
    :type  filePath: Str.

    """
    with open(filePath, "r") as myfile:
        fileString = myfile.read()

        # remove comments
        cleanString = re.sub(r"//.*?\n|/\*.*?\*/", "", fileString, re.S)

        data = json.loads(cleanString)

    return data


def _saveData(filePath: str, data: dict) -> None:
    """
    save data as a .json file

    :param filePath: Path of the .json file.
    :type  filePath: Str.

    :param data: Data you want to save.
    :type  data: Dict or List.

    """
    f = open(filePath, "w")
    f.write(json.dumps(data, sort_keys=True, indent=4, ensure_ascii=False))
    f.close()

    nlog.info("Data successfully saved !")


def _loadData(filePath: str) -> dict:
    """
    load data from a .json file.

    :param filePath: Path of the .json file.
    :type  filePath: Str.

    """
    with open(filePath) as json_file:
        j_data = json.load(json_file)

    json_file.close()

    nlog.info("Data successfully loaded !")
    return j_data
