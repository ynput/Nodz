import json
import re
import logging
from qtpy import QtCore, QtGui

logging.basicConfig(
    format="[%(name)s]  %(levelname)8s  %(msg)s",
    level=logging.INFO,
)
nlog = logging.getLogger("Nodz")


def _convert_data_to_color(
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
            mult = _generate_alternate_color_multiplier(color, av)

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
            mult = _generate_alternate_color_multiplier(color, av)
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


def _generate_alternate_color_multiplier(
    color: QtGui.QColor, av: int
) -> float:
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


def _create_pointer_bounding_box(
    pointer_pos: QtCore.QPoint, bb_size: int
) -> QtCore.QRectF:
    """
    generate a bounding box around the pointer.

    :param pointer_pos: Pointer position.
    :type  pointer_pos: QPoint.

    :param bb_size: Width and Height of the bounding box.
    :type  bb_size: Int.

    """
    # Create pointer's bounding box.
    point = pointer_pos

    mbb_pos = point
    point.setX(int(point.x() - bb_size / 2))
    point.setY(int(point.y() - bb_size / 2))

    size = QtCore.QSize(bb_size, bb_size)
    bb = QtCore.QRect(mbb_pos, size).toRectF()

    return bb


def _swap_list_indices(
    input_list: list, old_index: int, new_index: int
) -> None:
    """
    Simply swap 2 indices in a the specified list.

    :param input_list: List that contains the elements to swap.
    :type  input_list: List.

    :param old_index: Index of the element to move.
    :type  old_index: Int.

    :param new_index: Destination index of the element.
    :type  new_index: Int.

    """
    if old_index == -1:
        old_index = len(input_list) - 1

    if new_index == -1:
        new_index = len(input_list)

    value = input_list[old_index]
    input_list.pop(old_index)
    input_list.insert(new_index, value)


# IO
def _load_config(file_path: str) -> dict:
    """
    Read the configuration file and strips out comments.

    :param file_path: File path.
    :type  file_path: Str.

    """
    with open(file_path, "r") as myfile:
        file_string = myfile.read()

        # remove comments
        clean_string = re.sub(r"//.*?\n|/\*.*?\*/", "", file_string, re.S)

        data = json.loads(clean_string)

    return data


def _save_data(file_path: str, data: dict) -> None:
    """
    save data as a .json file

    :param file_path: Path of the .json file.
    :type  file_path: Str.

    :param data: Data you want to save.
    :type  data: Dict or List.

    """
    f = open(file_path, "w")
    f.write(json.dumps(data, sort_keys=True, indent=4, ensure_ascii=False))
    f.close()

    nlog.info("Data successfully saved !")


def _decoder(d: dict):
    """decode specific fields to avoid code duplication."""

    if "position" in d:
        d["position"] = QtCore.QPointF(*d["position"])

    if "dataType" in d:
        data_type = d["dataType"]
        if isinstance(data_type, str) and data_type.find("<") == 0:
            d["dataType"] = eval(str(data_type.split("'")[1]))

    return d


def _load_data(file_path: str) -> dict:
    """
    load data from a .json file.

    :param file_path: Path of the .json file.
    :type  file_path: Str.

    """
    with open(file_path) as json_file:
        j_data = json.load(json_file, object_hook=_decoder)

    json_file.close()

    nlog.info("Data successfully loaded !")
    return j_data
