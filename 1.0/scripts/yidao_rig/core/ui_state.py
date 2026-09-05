# -*- coding: utf-8 -*-
"""Persistent UI state shared by all YiDao Rig tools."""
from __future__ import print_function

import os

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None

try:
    from ..compat.qt_compat import QtCore, QtWidgets
except ImportError:
    QtCore = QtWidgets = None

_ORGANIZATION = 'YiDao Rig'
_APPLICATION = 'YiDao Rig Tools'


def _clear_status(status):
    status.setProperty('error', 'false')
    status.style().unpolish(status)
    status.style().polish(status)
    status.clear()


if QtCore:
    class _ViewportEmptyClickFilter(QtCore.QObject):
        """Clear status after a user clicks empty space in a Maya viewport."""
        def __init__(self, window, status):
            super(_ViewportEmptyClickFilter, self).__init__(window)
            self._window = window
            self._status = status

        def eventFilter(self, watched, event):
            if event.type() != QtCore.QEvent.MouseButtonPress:
                return False
            # Selection changes after the mouse press has been delivered.
            # Defer the check so clicks on an object do not look like blank
            # clicks merely because the previous selection was empty.
            QtCore.QTimer.singleShot(0, self._clear_after_viewport_click)
            return False

        def _clear_after_viewport_click(self):
            try:
                panel = cmds.getPanel(underPointer=True)
                if not panel or cmds.getPanel(typeOf=panel) != 'modelPanel':
                    return
                if not cmds.ls(selection=True):
                    _clear_status(self._status)
            except Exception:
                pass
else:
    _ViewportEmptyClickFilter = None


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


def setup_empty_selection_status(window):
    """Clear a status label when the user clicks empty Maya viewport space.

    This deliberately does not use Maya's SelectionChanged event: tools can
    temporarily alter selection while running, which is not a user request to
    dismiss the status message.
    """
    if not cmds or not QtWidgets:
        return None
    status = window.findChild(QtWidgets.QLabel, 'statusLabel')
    if status is None:
        return None

    click_filter = {'object': None}

    def cleanup(*args):
        filter_object = click_filter['object']
        if filter_object is not None:
            try:
                QtWidgets.QApplication.instance().removeEventFilter(filter_object)
            except Exception:
                pass
            click_filter['object'] = None

    try:
        if _ViewportEmptyClickFilter is not None:
            filter_object = _ViewportEmptyClickFilter(window, status)
            QtWidgets.QApplication.instance().installEventFilter(filter_object)
            click_filter['object'] = filter_object
        window.destroyed.connect(cleanup)
    except Exception:
        cleanup()
    return cleanup


def setup_state(window, tool_key):
    restore_state(window, tool_key)
    clear_status_job = setup_empty_selection_status(window)

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
    save.clear_status_job = clear_status_job
    return save
