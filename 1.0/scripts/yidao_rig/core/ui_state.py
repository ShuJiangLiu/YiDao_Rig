# -*- coding: utf-8 -*-
"""Persistent UI state shared by all YiDao Rig tools."""
from __future__ import print_function

import os

try:
    from ..compat.qt_compat import QtCore, QtWidgets
except ImportError:
    QtCore = QtWidgets = None

_ORGANIZATION = 'YiDao Rig'
_APPLICATION = 'YiDao Rig Tools'


def _settings_path():
    # ui_state.py: 1.0/scripts/yidao_rig/core/ui_state.py
    # Keep preferences inside the installed version so uninstalling the
    # YiDao_Rig module removes them together with the tools.
    version_root = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', '..'))
    data_dir = os.path.join(version_root, 'data')
    if not os.path.isdir(data_dir):
        try:
            os.makedirs(data_dir)
        except OSError:
            pass
    return os.path.join(data_dir, 'ui_state.ini')


def _settings():
    return QtCore.QSettings(_settings_path(), QtCore.QSettings.IniFormat)


def _key(widget):
    name = widget.objectName()
    return name or widget.__class__.__name__


def _assign_missing_keys(window):
    counts = {}
    for widget in window.findChildren(QtWidgets.QWidget):
        if widget.objectName():
            continue
        base = widget.__class__.__name__
        counts[base] = counts.get(base, 0) + 1
        widget.setObjectName('%s_%d' % (base, counts[base]))


def restore_state(window, tool_key):
    """Restore persistent values after a tool UI has been built."""
    if not QtWidgets:
        return
    _assign_missing_keys(window)
    settings = _settings()
    settings.beginGroup(tool_key)
    for widget in window.findChildren(QtWidgets.QWidget):
        key = _key(widget)
        if not settings.contains(key):
            continue
        value = settings.value(key)
        try:
            if isinstance(widget, QtWidgets.QCheckBox) or isinstance(widget, QtWidgets.QRadioButton):
                widget.setChecked(str(value).lower() in ('1', 'true', 'yes', 'on'))
            elif isinstance(widget, QtWidgets.QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QtWidgets.QComboBox):
                index = widget.findData(value)
                if index < 0:
                    index = widget.findText(str(value))
                if index < 0:
                    index = int(value)
                if index >= 0:
                    widget.setCurrentIndex(index)
            elif isinstance(widget, QtWidgets.QSpinBox) or isinstance(widget, QtWidgets.QDoubleSpinBox):
                widget.setValue(float(value) if isinstance(widget, QtWidgets.QDoubleSpinBox) else int(value))
        except Exception:
            pass
    settings.endGroup()


def save_state(window, tool_key):
    if not QtWidgets:
        return
    settings = _settings()
    settings.beginGroup(tool_key)
    for widget in window.findChildren(QtWidgets.QWidget):
        key = _key(widget)
        try:
            if isinstance(widget, QtWidgets.QCheckBox) or isinstance(widget, QtWidgets.QRadioButton):
                settings.setValue(key, widget.isChecked())
            elif isinstance(widget, QtWidgets.QLineEdit):
                settings.setValue(key, widget.text())
            elif isinstance(widget, QtWidgets.QComboBox):
                data = widget.currentData()
                settings.setValue(key, data if data is not None else widget.currentIndex())
            elif isinstance(widget, QtWidgets.QSpinBox) or isinstance(widget, QtWidgets.QDoubleSpinBox):
                settings.setValue(key, widget.value())
        except Exception:
            pass
    settings.endGroup()
    settings.sync()


def setup_state(window, tool_key):
    restore_state(window, tool_key)

    def save(*args):
        save_state(window, tool_key)
    for widget in window.findChildren(QtWidgets.QWidget):
        for signal_name in ('toggled', 'textChanged', 'currentIndexChanged', 'valueChanged'):
            signal = getattr(widget, signal_name, None)
            if signal is not None:
                try:
                    signal.connect(save)
                except Exception:
                    pass
    return save
