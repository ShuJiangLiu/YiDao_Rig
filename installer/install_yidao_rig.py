# -*- coding: utf-8 -*-
"""YiDao Rig standard Maya .mod installer.

Drag this file into Maya. It installs the versioned package and generates a
machine-specific .mod file under Documents/maya/modules/.
"""
from __future__ import print_function

import os
import shutil

SUPPORTED_VERSIONS = (2022, 2023, 2024, 2025, 2026)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_SOURCE = os.path.join(ROOT, '1.0')
MODULE_SOURCE = os.path.join(ROOT, 'module', 'YiDao_Rig.mod')


def maya_documents_dir():
    return os.path.join(os.path.expanduser('~'), 'Documents', 'maya')


def _copy_version_preserve_data(source, destination):
    source_data = os.path.join(source, 'data')
    destination_data = os.path.join(destination, 'data')
    backup_data = destination + '.data_backup'
    if os.path.isdir(destination_data):
        if os.path.isdir(backup_data):
            shutil.rmtree(backup_data)
        shutil.copytree(destination_data, backup_data)
    if os.path.isdir(destination):
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    if os.path.isdir(backup_data):
        if os.path.isdir(destination_data):
            shutil.rmtree(destination_data)
        shutil.copytree(backup_data, destination_data)
        shutil.rmtree(backup_data)


def onMayaDroppedPythonFile(*args):
    """Maya drag-and-drop callback."""
    return install()


def maya_version():
    try:
        import maya.cmds as cmds
        return int(str(cmds.about(version=True)).split('.')[0])
    except Exception:
        return None


def install():
    version = maya_version()
    if version is not None and version not in SUPPORTED_VERSIONS:
        raise RuntimeError('YiDao Rig 支持 Maya 2022-2026，当前版本：%s' % version)
    if not os.path.isdir(VERSION_SOURCE):
        raise RuntimeError('找不到版本目录：%s' % VERSION_SOURCE)
    if not os.path.isfile(MODULE_SOURCE):
        raise RuntimeError('找不到模块模板：%s' % MODULE_SOURCE)

    modules_dir = os.path.join(maya_documents_dir(), 'modules')
    if not os.path.isdir(modules_dir):
        os.makedirs(modules_dir)

    module_destination = os.path.join(modules_dir, 'YiDao_Rig')
    version_destination = os.path.join(module_destination, '1.0')
    mod_destination = os.path.join(modules_dir, 'YiDao_Rig.mod')
    _copy_version_preserve_data(VERSION_SOURCE, version_destination)

    version_root = version_destination.replace('\\', '/')
    mod_text = (
        '+ YiDao_Rig 1.0 %s\n'
        'MAYA_PLUG_IN_PATH +:= %s/plug-ins\n'
        'PYTHONPATH +:= %s/scripts\n'
        'MAYA_SCRIPT_PATH +:= %s/scripts\n'
        % (version_root, version_root, version_root, version_root)
    )
    with open(mod_destination, 'w') as stream:
        stream.write(mod_text)

    print('[YiDao Rig] Maya version: %s' % (version or 'Unknown'))
    print('[YiDao Rig] Module installed: %s' % mod_destination)
    print('[YiDao Rig] Version installed: %s' % version_destination)
    print('[YiDao Rig] Custom data: %s' % os.path.join(version_destination, 'data'))
    print('[YiDao Rig] Restart Maya, then load YiDao_Rig_plugin.py in Plug-in Manager.')
    return mod_destination


if __name__ == '__main__':
    install()
