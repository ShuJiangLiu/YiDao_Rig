# -*- coding: utf-8 -*-
"""YiDao Rig Maya Python plug-in entry point.

This file is loaded by Maya's Plug-in Manager. It creates a persistent
YiDao Rig menu while the plug-in is loaded.
"""
from __future__ import print_function

import os
import sys
import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMaya as om
import maya.OpenMayaMPx as ompx

PLUGIN_NAME = 'YiDao_Rig'
MENU_NAME = 'YiDao_Rig_MainMenu'


def _add_package_path(mobject=None):
    """Resolve the module scripts path without relying on __file__."""
    plugin_path = ''
    if mobject is not None:
        try:
            plugin_path = ompx.MFnPlugin(mobject).fullPathName()
        except Exception:
            plugin_path = ''
    if not plugin_path:
        try:
            plugin_path = cmds.pluginInfo(PLUGIN_NAME, query=True, path=True) or ''
        except Exception:
            plugin_path = ''
    if plugin_path:
        version_root = os.path.dirname(os.path.dirname(plugin_path))
        scripts_dir = os.path.join(version_root, 'scripts')
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)


def _show_controller_tool(*args):
    import yidao_rig
    yidao_rig.show_controller_tool()


def _show_mirror_joints(*args):
    import yidao_rig
    yidao_rig.show_mirror_joints()


def _show_attribute_cleanup(*args):
    import yidao_rig
    yidao_rig.show_attribute_cleanup()


def _show_joint_match(*args):
    import yidao_rig
    yidao_rig.show_joint_match()


def _show_skin_weight_tool(*args):
    import yidao_rig
    yidao_rig.show_skin_weight_tool()


def initializePlugin(mobject):
    plugin = ompx.MFnPlugin(mobject, 'YiDao Rig', '1.0.0', 'Any')
    _add_package_path(mobject)
    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME)
    main_window = mel.eval('$tmp = $gMainWindow')
    cmds.menu(MENU_NAME, label='YiDao Rig', parent=main_window, tearOff=True)
    tools_menu = cmds.menuItem(label='Tools', parent=MENU_NAME,
                                subMenu=True, tearOff=True)
    joint_menu = cmds.menuItem(label='Joint', parent=tools_menu,
                               subMenu=True, tearOff=True)
    cmds.menuItem(label='Mirror Joints', parent=joint_menu,
                  command=_show_mirror_joints)
    cmds.menuItem(label='Joint Match', parent=joint_menu,
                  command=_show_joint_match)
    controller_menu = cmds.menuItem(label='Controller', parent=tools_menu,
                                    subMenu=True, tearOff=True)
    cmds.menuItem(label='Controller Tool', parent=controller_menu,
                  command=_show_controller_tool)
    attribute_menu = cmds.menuItem(label='Attribute', parent=tools_menu,
                                   subMenu=True, tearOff=True)
    cmds.menuItem(label='Attribute Cleanup', parent=attribute_menu,
                  command=_show_attribute_cleanup)
    skin_menu = cmds.menuItem(label='Skin', parent=tools_menu,
                              subMenu=True, tearOff=True)
    cmds.menuItem(label='Skin Weight Import / Export', parent=skin_menu,
                  command=_show_skin_weight_tool)
    cmds.menuItem(divider=True, parent=MENU_NAME)
    developer_menu = cmds.menuItem(label='Developer', parent=MENU_NAME,
                                    subMenu=True, tearOff=True)
    cmds.menuItem(label='Reload All YiDao Rig Tools', parent=developer_menu,
                  command=lambda *args: _reload_all_tools())
    om.MGlobal.displayInfo('[YiDao Rig] Plug-in loaded. Menu: YiDao Rig')


def _reload_all_tools():
    _add_package_path()
    import yidao_rig
    reloaded = yidao_rig.reload_all_tools()
    om.MGlobal.displayInfo('[YiDao Rig] Reloaded %d package modules. No tool window was opened.' % len(reloaded))


def uninitializePlugin(mobject):
    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME)
    om.MGlobal.displayInfo('[YiDao Rig] Plug-in unloaded.')
