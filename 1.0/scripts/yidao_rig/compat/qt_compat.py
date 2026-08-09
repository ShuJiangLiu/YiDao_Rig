# -*- coding: utf-8 -*-
"""Qt binding and enum compatibility for Maya 2022-2026."""
from __future__ import annotations

QT_API = None
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance
    QT_API = 'PySide6'
except ImportError:
    try:
        from PySide2 import QtCore, QtGui, QtWidgets
        from shiboken2 import wrapInstance
        QT_API = 'PySide2'
    except ImportError:
        QtCore = QtGui = QtWidgets = wrapInstance = None

if QtCore:
    if QT_API == 'PySide6':
        QT_USER_ROLE = QtCore.Qt.ItemDataRole.UserRole
        QT_ALIGN_RIGHT = QtCore.Qt.AlignmentFlag.AlignRight
        QT_ALIGN_VCENTER = QtCore.Qt.AlignmentFlag.AlignVCenter
        QT_ALIGN_CENTER = QtCore.Qt.AlignmentFlag.AlignCenter
        QT_ALIGN_HCENTER = QtCore.Qt.AlignmentFlag.AlignHCenter
        QT_ALIGN_BOTTOM = QtCore.Qt.AlignmentFlag.AlignBottom
        QT_POINTING_HAND = QtCore.Qt.CursorShape.PointingHandCursor
        QT_WINDOW = QtCore.Qt.WindowType.Window
        QT_WINDOW_SYSTEM_MENU = QtCore.Qt.WindowType.WindowSystemMenuHint
        QT_WINDOW_CLOSE = QtCore.Qt.WindowType.WindowCloseButtonHint
        QT_WINDOW_MINIMIZE = QtCore.Qt.WindowType.WindowMinimizeButtonHint
        QT_WINDOW_MAXIMIZE = QtCore.Qt.WindowType.WindowMaximizeButtonHint
        QT_DELETE_ON_CLOSE = QtCore.Qt.WidgetAttribute.WA_DeleteOnClose
        QT_SOLID_LINE = QtCore.Qt.PenStyle.SolidLine
        QT_ROUND_CAP = QtCore.Qt.PenCapStyle.RoundCap
        QT_ROUND_JOIN = QtCore.Qt.PenJoinStyle.RoundJoin
        QT_ANTIALIASING = QtGui.QPainter.RenderHint.Antialiasing
        QT_LIST_ICON_MODE = QtWidgets.QListView.ViewMode.IconMode
        QT_LIST_LEFT_TO_RIGHT = QtWidgets.QListView.Flow.LeftToRight
        QT_LIST_ADJUST = QtWidgets.QListView.ResizeMode.Adjust
        QT_LIST_STATIC = QtWidgets.QListView.Movement.Static
        QT_MSG_YES = QtWidgets.QMessageBox.StandardButton.Yes
        QT_MSG_NO = QtWidgets.QMessageBox.StandardButton.No
    else:
        QT_USER_ROLE = QtCore.Qt.UserRole
        QT_ALIGN_RIGHT = QtCore.Qt.AlignRight
        QT_ALIGN_VCENTER = QtCore.Qt.AlignVCenter
        QT_ALIGN_CENTER = QtCore.Qt.AlignCenter
        QT_ALIGN_HCENTER = QtCore.Qt.AlignHCenter
        QT_ALIGN_BOTTOM = QtCore.Qt.AlignBottom
        QT_POINTING_HAND = QtCore.Qt.PointingHandCursor
        QT_WINDOW = QtCore.Qt.Window
        QT_WINDOW_SYSTEM_MENU = QtCore.Qt.WindowSystemMenuHint
        QT_WINDOW_CLOSE = QtCore.Qt.WindowCloseButtonHint
        QT_WINDOW_MINIMIZE = QtCore.Qt.WindowMinimizeButtonHint
        QT_WINDOW_MAXIMIZE = QtCore.Qt.WindowMaximizeButtonHint
        QT_DELETE_ON_CLOSE = QtCore.Qt.WA_DeleteOnClose
        QT_SOLID_LINE = QtCore.Qt.SolidLine
        QT_ROUND_CAP = QtCore.Qt.RoundCap
        QT_ROUND_JOIN = QtCore.Qt.RoundJoin
        QT_ANTIALIASING = QtGui.QPainter.Antialiasing
        QT_LIST_ICON_MODE = QtWidgets.QListView.IconMode
        QT_LIST_LEFT_TO_RIGHT = QtWidgets.QListView.LeftToRight
        QT_LIST_ADJUST = QtWidgets.QListView.Adjust
        QT_LIST_STATIC = QtWidgets.QListView.Static
        QT_MSG_YES = QtWidgets.QMessageBox.Yes
        QT_MSG_NO = QtWidgets.QMessageBox.No
else:
    QT_USER_ROLE = QT_ALIGN_RIGHT = QT_ALIGN_VCENTER = QT_ALIGN_CENTER = None
    QT_ALIGN_HCENTER = QT_ALIGN_BOTTOM = QT_POINTING_HAND = None
    QT_WINDOW = QT_WINDOW_SYSTEM_MENU = QT_WINDOW_CLOSE = None
    QT_WINDOW_MINIMIZE = QT_WINDOW_MAXIMIZE = QT_DELETE_ON_CLOSE = None
    QT_SOLID_LINE = QT_ROUND_CAP = QT_ROUND_JOIN = None
    QT_ANTIALIASING = QT_LIST_ICON_MODE = QT_LIST_LEFT_TO_RIGHT = None
    QT_LIST_ADJUST = QT_LIST_STATIC = QT_MSG_YES = QT_MSG_NO = None
