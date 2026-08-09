# -*- coding: utf-8 -*-
"""Controller shape definitions, persistence, and Maya color data."""
from __future__ import annotations

import json
import os
import re

try:
    import maya.cmds as cmds
    import maya.OpenMaya as om1
except ImportError:
    cmds = om1 = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_ROOT = os.path.dirname(os.path.dirname(ROOT))
USER_DATA_DIR = os.path.join(VERSION_ROOT, 'data')
SHAPES_FILE = os.path.join(USER_DATA_DIR, 'controller_shapes.json')
ICONS_DIR = os.path.join(USER_DATA_DIR, 'controller_icons')
LEGACY_USER_DATA_DIR = os.path.join(os.path.expanduser('~'), 'Documents', 'maya', 'scripts', 'controller_tool_data')
LEGACY_SHAPES_FILE = os.path.join(ROOT, 'controller_shapes.json')
WINDOW_OBJECT = 'adroControllerToolWindow'

# Shared icon-rendering colors. Keep these in the data layer so every tool
# uses the same preview appearance after a package-wide reload.
ICON_BACKGROUND = '#202020'
ICON_FOREGROUND = '#ffffff'

_FALLBACK_MAYA_RGB = [
    '#000000', '#404040', '#808080', '#bfbfbf', '#800000', '#000080',
    '#008000', '#008080', '#800080', '#808000', '#804000', '#c0c000',
    '#ff0000', '#0000ff', '#00ff00', '#00ffff', '#ffff00', '#ffffff',
    '#ff00ff', '#c08080', '#c00000', '#8080ff', '#00c000', '#00c0c0',
    '#c000c0', '#c0c000', '#c0c0c0', '#604020', '#ff8080', '#80ff80',
    '#80ffff', '#ff80ff',
]


def _maya_index_rgb(index):
    """Read the same Maya Color Index palette used by Display Layer UI."""
    index = int(index)
    # colorIndex -q is the palette exposed by Maya's Color Index UI.
    if cmds:
        try:
            values = cmds.colorIndex(index, query=True)
            if values and len(values) >= 3:
                values = [max(0.0, min(1.0, float(value))) for value in values[:3]]
                return '#%02x%02x%02x' % tuple(int(value * 255.0 + 0.5) for value in values)
        except Exception:
            pass
    # Fallback for unusual Maya builds where colorIndex is unavailable.
    if om1:
        try:
            color = om1.MColor()
            om1.M3dView.colorAtIndex(index, color)
            values = [max(0.0, min(1.0, float(color[i]))) for i in range(3)]
            return '#%02x%02x%02x' % tuple(int(value * 255.0 + 0.5) for value in values)
        except Exception:
            pass
    return _FALLBACK_MAYA_RGB[index]


MAYA_COLORS = [(index, 'Index %02d' % index, _maya_index_rgb(index)) for index in range(32)]
COLORS = {'Index %02d' % index: index for index in range(32)}
COLOR_PREVIEW = {'Index %02d' % index: rgb for index, label, rgb in MAYA_COLORS}

# Each entry contains one or more independent linear curve descriptions.
BUILTIN_SHAPES = {
    'circle': [{'degree': 1, 'points': [[1, 0, 0], [.866, 0, .5], [.5, 0, .866], [0, 0, 1], [-.5, 0, .866], [-.866, 0, .5], [-1, 0, 0], [-.866, 0, -.5], [-.5, 0, -.866], [0, 0, -1], [.5, 0, -.866], [.866, 0, -.5], [1, 0, 0]], 'knots': list(range(13))}],
    'square': [{'degree': 1, 'points': [[-1, 0, -1], [-1, 0, 1], [1, 0, 1], [1, 0, -1], [-1, 0, -1]], 'knots': list(range(5))}],
    'cube': [{'degree': 1, 'points': [[-.5,.5,.5],[-.5,-.5,.5],[.5,-.5,.5],[.5,.5,.5],[-.5,.5,.5],[-.5,.5,-.5],[.5,.5,-.5],[.5,.5,.5],[.5,-.5,.5],[.5,-.5,-.5],[.5,.5,-.5],[.5,-.5,-.5],[-.5,-.5,-.5],[-.5,.5,-.5],[-.5,-.5,-.5],[-.5,-.5,.5]], 'knots': list(range(16))}],
    'arrow': [{'degree': 1, 'points': [[-.5,0,-1],[-.5,0,0],[-1,0,0],[0,0,1],[1,0,0],[.5,0,0],[.5,0,-1],[-.5,0,-1]], 'knots': list(range(8))}],
    'cross': [{'degree': 1, 'points': [[-2.5,0,-.5],[-.5,0,-.5],[-.5,0,-2.5],[.5,0,-2.5],[.5,0,-.5],[2.5,0,-.5],[2.5,0,.5],[.5,0,.5],[.5,0,2.5],[-.5,0,2.5],[-.5,0,.5],[-2.5,0,.5],[-2.5,0,-.5]], 'knots': list(range(13))}],
    'star': [{'degree': 1, 'points': [[0,0,1],[.22,0,.32],[.95,0,.31],[.36,0,-.12],[.59,0,-.81],[0,0,-.4],[-.59,0,-.81],[-.36,0,-.12],[-.95,0,.31],[-.22,0,.32],[0,0,1]], 'knots': list(range(11))}],
}


def _ensure_dirs():
    if not os.path.isdir(ICONS_DIR):
        os.makedirs(ICONS_DIR)


def _safe_name(value):
    value = re.sub(r'[^A-Za-z0-9_\-]+', '_', value.strip())
    return value.strip('_') or 'controller'


def load_custom_shapes():
    shape_file = SHAPES_FILE
    if not os.path.isfile(shape_file):
        legacy_user_file = os.path.join(LEGACY_USER_DATA_DIR, 'controller_shapes.json')
        shape_file = legacy_user_file if os.path.isfile(legacy_user_file) else LEGACY_SHAPES_FILE
    if not os.path.isfile(shape_file):
        return {}
    try:
        with open(shape_file, 'r', encoding='utf-8') as stream:
            data = json.load(stream)
        if not isinstance(data, dict):
            return {}
        # Older versions stored absolute project paths. Preserve the entry but
        # remap a matching icon filename into the new per-user icon directory.
        for entry in data.values():
            if not isinstance(entry, dict):
                continue
            icon = entry.get('icon', '')
            if icon and not os.path.isfile(icon):
                candidates = [os.path.join(ICONS_DIR, os.path.basename(icon)),
                              os.path.join(LEGACY_USER_DATA_DIR, 'controller_icons', os.path.basename(icon))]
                candidate = next((path for path in candidates if os.path.isfile(path)), None)
                if candidate:
                    entry['icon'] = candidate
        return data
    except (OSError, ValueError):
        return {}


def save_custom_shapes(data):
    _ensure_dirs()
    with open(SHAPES_FILE, 'w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


def _shape_data(name):
    if name in BUILTIN_SHAPES:
        return BUILTIN_SHAPES[name]
    return load_custom_shapes().get(name, {}).get('curves', [])


def _oriented_shape_data(name):
    """Return shape data with the controller's forward direction on world -Z."""
    oriented = []
    for curve in _shape_data(name):
        oriented.append(dict(curve, points=[[p[0], p[1], -p[2]] for p in curve.get('points', [])]))
    return oriented


