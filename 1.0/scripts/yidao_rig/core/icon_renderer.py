# -*- coding: utf-8 -*-
"""Deterministic Qt rendering for controller shape and color icons."""
from __future__ import annotations

import os
from ..compat.qt_compat import (
    QtCore, QtGui, QT_SOLID_LINE, QT_ROUND_CAP, QT_ROUND_JOIN,
    QT_ANTIALIASING,
)

from .shape_data import (
    ICONS_DIR, COLOR_PREVIEW, ICON_BACKGROUND, ICON_FOREGROUND, BUILTIN_SHAPES,
    _shape_data,
)

ICON_LINE_WIDTH = 3.0
ICON_MARGIN = 0.08


def _current_view_basis():
    """Return the active model-panel camera's exact screen-right/up vectors."""
    try:
        from ..compat.maya_compat import cmds
        from maya.api import OpenMaya as om2
        if not cmds:
            return None
        # The ControllerTool window can have focus, so prefer the model panel
        # under the mouse before falling back to the focused/visible panel.
        panel = None
        try:
            panel = cmds.getPanel(underPointer=True)
        except Exception:
            pass
        if not panel or cmds.getPanel(typeOf=panel) != 'modelPanel':
            panel = cmds.getPanel(withFocus=True)
        if not panel or cmds.getPanel(typeOf=panel) != 'modelPanel':
            panels = cmds.getPanel(visiblePanels=True) or []
            panel = next((item for item in panels
                          if cmds.getPanel(typeOf=item) == 'modelPanel'), None)
        if not panel:
            return None
        camera = cmds.modelEditor(panel, query=True, camera=True)
        matrix = om2.MMatrix(cmds.xform(
            camera, query=True, worldSpace=True, matrix=True))
        # Maya API uses row-vector multiplication. Transform the camera's
        # local +X/+Y axes, rather than assuming raw matrix rows are screen
        # axes; this also preserves camera roll and all viewport orientations.
        right_v = om2.MVector(1.0, 0.0, 0.0) * matrix
        up_v = om2.MVector(0.0, 1.0, 0.0) * matrix
        right = (right_v.x, right_v.y, right_v.z)
        up = (up_v.x, up_v.y, up_v.z)
        return right, up
    except Exception:
        return None


def _project_icon_curves(curves, use_view_camera=False):
    """Project points using Maya's view only for custom-shape icons."""
    basis = _current_view_basis() if use_view_camera else None
    result = []
    for curve in curves:
        projected = []
        for point in curve.get('points', []):
            if basis:
                right, up = basis
                projected.append((
                    point[0] * right[0] + point[1] * right[1] + point[2] * right[2],
                    point[0] * up[0] + point[1] * up[1] + point[2] * up[2],
                ))
            else:
                projected.append((point[0] + point[1] * 0.42,
                                  point[2] - point[1] * 0.42))
        if projected:
            result.append(projected)
    return result


def _make_shape_pixmap(name, size=256):
    """Render built-in and custom shapes using one deterministic icon renderer."""
    if not QtGui:
        return None
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtGui.QColor(ICON_BACKGROUND))
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QT_ANTIALIASING, True)
    # 线宽按画布比例缩放：64px 内置缩略图为 3px，256px PNG 为 12px，
    # 缩略显示后两者的视觉粗细一致。
    line_width = max(1.0, float(size) * ICON_LINE_WIDTH / 64.0)
    painter.setPen(QtGui.QPen(QtGui.QColor(ICON_FOREGROUND), line_width,
                              QT_SOLID_LINE, QT_ROUND_CAP, QT_ROUND_JOIN))
    # 图标方向保持上一版，不跟随场景控制器的 -Z 朝向反转。
    # Built-in icons retain their original fixed visual direction. Only
    # custom-shape icons follow the current Maya viewport camera.
    projected_curves = _project_icon_curves(
        _shape_data(name), use_view_camera=name not in BUILTIN_SHAPES)
    points = [point for curve in projected_curves for point in curve]
    if points:
        xs = [point[0] for point in points]
        zs = [point[1] for point in points]
        span = max(max(xs) - min(xs), max(zs) - min(zs), 0.001)
        center_x = (max(xs) + min(xs)) * 0.5
        center_z = (max(zs) + min(zs)) * 0.5
        drawable = size * (1.0 - ICON_MARGIN * 2.0)
        for curve in projected_curves:
            qpoints = [QtCore.QPointF(size * 0.5 + (x - center_x) / span * drawable,
                                      size * 0.5 - (z - center_z) / span * drawable)
                       for x, z in curve]
            if len(qpoints) > 1:
                painter.drawPolyline(qpoints)
    painter.end()
    return pixmap


def _make_shape_icon(name, size=64):
    pixmap = _make_shape_pixmap(name, size)
    return QtGui.QIcon(pixmap) if pixmap else None


def _save_shape_icon(name, path, size=256):
    """Save a custom shape icon using the current Maya viewport camera."""
    pixmap = _make_shape_pixmap(name, size)
    if not pixmap or not pixmap.save(os.path.abspath(path), 'PNG'):
        raise RuntimeError('无法保存控制器图标：%s' % os.path.abspath(path))
    return os.path.abspath(path)


def _make_color_icon(name, size=20):
    if not QtGui:
        return None
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtGui.QColor(COLOR_PREVIEW.get(name, '#777777')))
    painter = QtGui.QPainter(pixmap)
    painter.setPen(QtGui.QPen(QtGui.QColor('#dddddd'), 1))
    painter.drawRect(0, 0, size - 1, size - 1)
    painter.end()
    return QtGui.QIcon(pixmap)


