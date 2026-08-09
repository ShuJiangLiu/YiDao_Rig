# -*- coding: utf-8 -*-
"""YiDao Rig Maya launcher and package-wide development reload helpers."""
from __future__ import print_function

import importlib
import os
import pkgutil
import sys


_PACKAGE_PREFIX = 'yidao_rig'
def _module_reload_order(name):
    """Reload dependencies before consumers, while keeping package last."""
    if name == _PACKAGE_PREFIX:
        return (50, 0, name)
    if name.startswith(_PACKAGE_PREFIX + '.compat'):
        return (0, -name.count('.'), name)
    if name.startswith(_PACKAGE_PREFIX + '.core'):
        return (10, -name.count('.'), name)
    if name.startswith(_PACKAGE_PREFIX + '.ui'):
        return (20, -name.count('.'), name)
    if name.startswith(_PACKAGE_PREFIX + '.tools'):
        return (30, -name.count('.'), name)
    return (40, -name.count('.'), name)


def _package_module_names():
    """Return every Python module physically present in the package."""
    package = sys.modules.get(_PACKAGE_PREFIX)
    if package is None:
        package = importlib.import_module(_PACKAGE_PREFIX)
    names = [_PACKAGE_PREFIX]
    package_path = getattr(package, '__path__', None)
    if not package_path:
        return names
    for module_info in pkgutil.walk_packages(package_path,
                                             _PACKAGE_PREFIX + '.'):
        if not module_info.ispkg:
            names.append(module_info.name)
    return names


def reload_all_tools():
    """Import and reload every YiDao Rig Python module on disk.

    This also imports newly added tools that have not been opened yet. It
    does not open/rebuild Qt windows and does not rebuild the Maya menu.
    """
    names = _package_module_names()
    # Import new modules first so their dependencies exist during reload.
    for name in names:
        if name not in sys.modules:
            try:
                importlib.import_module(name)
            except Exception as exc:
                print('[YiDao Rig] Import skipped %s: %s' % (name, exc))
    names = [name for name in names if name in sys.modules]
    reloaded = []
    for name in sorted(names, key=_module_reload_order):
        module = sys.modules.get(name)
        if module is None:
            continue
        try:
            importlib.reload(module)
            reloaded.append(name)
        except Exception as exc:
            print('[YiDao Rig] Reload skipped %s: %s' % (name, exc))
    print('[YiDao Rig] Reloaded %d package modules.' % len(reloaded))
    return reloaded


def show_controller_tool():
    from .tools import controller_tool
    return controller_tool.show()


def show_mirror_joints():
    from .tools import mirror_joints_tool
    return mirror_joints_tool.run()


def reload_controller_tool():
    """Backward-compatible alias for the complete package reload."""
    return reload_all_tools()
