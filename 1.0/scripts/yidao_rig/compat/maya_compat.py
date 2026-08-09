# -*- coding: utf-8 -*-
"""Maya API compatibility helpers."""
from __future__ import annotations

try:
    import maya.cmds as cmds
    import maya.OpenMayaUI as omui
except ImportError:
    cmds = omui = None

from .qt_compat import QtWidgets, wrapInstance


def maya_version():
    if not cmds:
        return None
    try:
        return int(str(cmds.about(version=True)).split('.')[0])
    except Exception:
        return None


def maya_version_string():
    if not cmds:
        return 'Outside Maya'
    try:
        return str(cmds.about(version=True))
    except Exception:
        return 'Unknown'


def maya_main_window():
    if not omui or not wrapInstance or not QtWidgets:
        return None
    pointer = omui.MQtUtil.mainWindow()
    if not pointer:
        return None
    return wrapInstance(int(pointer), QtWidgets.QWidget)
