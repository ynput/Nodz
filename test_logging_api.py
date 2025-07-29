#!/usr/bin/env python3
"""
Test script to demonstrate the logging level API functionality.
"""

import logging
import sys
from qtpy import QtWidgets
from nodz.main import create_nodz_view
from nodz.utils import nlog


def test_logging_levels():
    """Test the logging level API."""
    # Create a Nodz view to get access to the API
    nodz = create_nodz_view()

    print("=== Testing Logging Level API ===")

    # Test getting current logging level
    current_level = nodz.api.get_logging_level()
    print(
        f"Current logging level: {current_level} "
        f"({logging.getLevelName(current_level)})"
    )

    # Test setting logging level with string
    print("\n1. Setting logging level to DEBUG using string...")
    nodz.api.set_logging_level("DEBUG")
    nlog.debug("This is a DEBUG message")
    nlog.info("This is an INFO message")
    nlog.warning("This is a WARNING message")

    # Test setting logging level with logging constant
    print("\n2. Setting logging level to WARNING using logging constant...")
    nodz.api.set_logging_level(logging.WARNING)
    nlog.debug("This DEBUG message should not appear")
    nlog.info("This INFO message should not appear")
    nlog.warning("This WARNING message should appear")
    nlog.error("This ERROR message should appear")

    # Test setting logging level to INFO
    print("\n3. Setting logging level back to INFO...")
    nodz.api.set_logging_level("INFO")
    nlog.debug("This DEBUG message should not appear")
    nlog.info("This INFO message should appear")
    nlog.warning("This WARNING message should appear")

    # Test getting the updated logging level
    final_level = nodz.api.get_logging_level()
    print(
        f"\nFinal logging level: {final_level} "
        f"({logging.getLevelName(final_level)})"
    )

    print("\n=== Logging Level API Test Complete ===")


if __name__ == "__main__":
    # Create QApplication
    app = QtWidgets.QApplication(sys.argv)
    test_logging_levels()
