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
    Convert a list of RGB or RGBA values from the configuration to a
    QtGui.QColor object.

    Args:
        data (list): Input list of RGB or RGBA values.
        alternate (bool): Whether to generate an alternate color.
        av (int): The amount to adjust the color values by.
    Returns:
        QtGui.QColor: A QColor object
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
    Generate a multiplier based on the input color lightness to increase
    the alternate value for dark color or reduce it for bright colors.

    Args:
        color (QtGui.QColor): Input color.
        av (int): Alternate value.
    Returns:
        float: Multiplier based on color lightness.
    """
    lightness = color.lightness()
    mult = float(lightness) / 255

    return mult


def _create_pointer_bounding_box(
    pointer_pos: QtCore.QPoint, bb_size: int
) -> QtCore.QRectF:
    """
    Generate a bounding box around the pointer.

    Args:
        pointer_pos (QtCore.QPoint): Pointer position.
        bb_size (int): Width and Height of the bounding box.
    Returns:
        QtCore.QRectF: Bounding box around the pointer.
    """
    # Create pointer's bounding box.
    point = pointer_pos

    mbb_pos = point
    point.setX(int(point.x() - bb_size / 2))
    point.setY(int(point.y() - bb_size / 2))

    size = QtCore.QSize(bb_size, bb_size)
    bb = QtCore.QRect(mbb_pos, size).toRectF()

    return bb


# IO
def _load_config(file_path: str) -> dict:
    """
    Read the configuration file and strips out comments.

    Args:
        file_path (str): Path to the configuration
    Returns:
        dict: Configuration data.
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

    Args:
        file_path (str): Path to json file to save to.
        data (dict): Data to save.
    """

    def _encoder(obj):
        if isinstance(obj, QtCore.QPointF):
            obj = (obj.x(), obj.y())
        elif isinstance(obj, type):
            obj = str(obj)
        return obj

    f = open(file_path, "w")
    f.write(
        json.dumps(
            data,
            sort_keys=True,
            indent=4,
            ensure_ascii=False,
            default=_encoder,
        )
    )
    f.close()

    nlog.info("Data successfully saved !")


def _load_data(file_path: str) -> dict:
    """
    load data from a .json file.

    Args:
        file_path (str): Path to the json file to load.
    Returns:
        dict: dict loaded from the file.
    """

    def _decoder(d: dict):
        """decode specific fields to avoid code duplication."""

        if "position" in d:
            d["position"] = QtCore.QPointF(*d["position"])

        if "data_type" in d:
            data_type = d["data_type"]
            if isinstance(data_type, str) and data_type.find("<") == 0:
                d["data_type"] = eval(str(data_type.split("'")[1]))

        return d

    with open(file_path) as json_file:
        j_data = json.load(json_file, object_hook=_decoder)

    json_file.close()

    nlog.info("Data successfully loaded !")
    return j_data
