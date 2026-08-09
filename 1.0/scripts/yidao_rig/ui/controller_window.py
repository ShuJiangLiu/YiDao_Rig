# -*- coding: utf-8 -*-
"""ControllerTool Qt window."""
from __future__ import annotations

import os
from ..compat.qt_compat import (
    QtCore, QtGui, QtWidgets, QT_USER_ROLE, QT_ALIGN_RIGHT,
    QT_ALIGN_VCENTER, QT_ALIGN_HCENTER, QT_ALIGN_BOTTOM, QT_POINTING_HAND,
    QT_WINDOW, QT_WINDOW_SYSTEM_MENU, QT_WINDOW_CLOSE, QT_WINDOW_MINIMIZE,
    QT_WINDOW_MAXIMIZE, QT_DELETE_ON_CLOSE,
    QT_LIST_ICON_MODE, QT_LIST_LEFT_TO_RIGHT, QT_LIST_ADJUST, QT_LIST_STATIC,
    QT_MSG_YES, QT_MSG_NO,
)
from ..compat.maya_compat import cmds, maya_main_window
from ..core.ui_state import setup_state

from ..core.shape_data import (
    BUILTIN_SHAPES, MAYA_COLORS, ICONS_DIR, WINDOW_OBJECT,
    COLOR_PREVIEW, _safe_name, load_custom_shapes, save_custom_shapes,
)
from ..core.icon_renderer import _make_shape_icon, _save_shape_icon
from ..core.controller_ops import (
    add_custom_shape, capture_icon, create_controller, flip_shape,
    mirror_shape, replace_shape, replace_shape_from_reference,
    scale_controller_shapes, undo_chunk,
    _set_color, _shape_nodes, mirror_shape_to_counterpart,
)

if QtWidgets:
    class ControllerToolWindow(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName(WINDOW_OBJECT)
            self.setWindowTitle('ControllerTool')
            self.setMinimumSize(520, 680)
            self.setSizeGripEnabled(True)
            self.custom = load_custom_shapes()
            self._build_ui()
            self._refresh_shapes()
            self._save_ui_state = setup_state(self, 'controller_tool')

        def _build_ui(self):
            self.setStyleSheet('''
                QDialog { background: #202020; color: #e8e8e8; }
                QLabel { color: #cfcfcf; }
                QGroupBox { border: 1px solid #3c3c3c; border-radius: 5px; margin-top: 8px; padding: 8px 6px 6px 6px; font-weight: bold; color: #e0e0e0; }
                QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
                QLineEdit, QDoubleSpinBox, QComboBox { background: #292929; border: 1px solid #4a4a4a; border-radius: 3px; padding: 4px 6px; color: #f0f0f0; min-height: 22px; }
                QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 1px solid #6b9dcc; }
                QPushButton { background: #353535; border: 1px solid #4d4d4d; border-radius: 3px; padding: 5px 10px; min-height: 24px; color: #ededed; }
                QPushButton:hover { background: #454545; border-color: #6b9dcc; }
                QPushButton:pressed { background: #2a2a2a; }
                QListWidget { background: #202020; border: 1px solid #4a4a4a; border-radius: 4px; outline: none; }
                QListWidget::item { color: #d8d8d8; border-radius: 4px; padding: 3px; }
                QListWidget::item:hover { background: #303030; }
                QListWidget::item:selected { background: #3d5f7d; color: #ffffff; }
                QSlider::groove:horizontal { height: 4px; background: #444444; border-radius: 2px; }
                QSlider::handle:horizontal { width: 12px; margin: -5px 0; background: #7da6cc; border-radius: 6px; }
                QScrollBar:vertical { width: 10px; background: #202020; }
                QScrollBar::handle:vertical { background: #4a4a4a; border-radius: 5px; min-height: 20px; }
            ''')
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(10, 10, 10, 10)
            root.setSpacing(8)
            form = QtWidgets.QFormLayout()
            form.setLabelAlignment(QT_ALIGN_RIGHT | QT_ALIGN_VCENTER)
            form.setHorizontalSpacing(10)
            form.setVerticalSpacing(5)
            self.name_edit = QtWidgets.QLineEdit('ctrl')
            self.name_edit.setPlaceholderText('输入控制器名称')
            form.addRow('控制器名称', self.name_edit)
            root.addLayout(form)
            color_group = QtWidgets.QGroupBox('颜色（双击替换控制器颜色）')
            color_grid = QtWidgets.QGridLayout(color_group)
            color_grid.setContentsMargins(8, 6, 8, 6)
            color_grid.setHorizontalSpacing(2)
            color_grid.setVerticalSpacing(2)
            self.color_buttons = []
            self.selected_color_index = 0
            for index, color_name, rgb in MAYA_COLORS:
                # 使用 Maya Edit Layer Color Index 风格：紧凑色块，不显示按钮文字。
                button = QtWidgets.QToolButton()
                button.setFixedSize(24, 20)
                button.setToolTip('Color Index %02d' % index)
                button.setProperty('colorIndex', index)
                button.setCursor(QT_POINTING_HAND)
                button.setStyleSheet(
                    'QToolButton { background-color: %s; border: 1px solid #303030; padding: 0px; } '
                    'QToolButton:hover { border: 1px solid #ffffff; }' % rgb)
                button.clicked.connect(self._select_color_button)
                button.mouseDoubleClickEvent = lambda event, color_button=button: self._apply_color_double_click(color_button, event)
                color_grid.addWidget(button, index // 8, index % 8)
                self.color_buttons.append(button)
            root.addWidget(color_group)
            self._update_color_button_state()
            shape_group = QtWidgets.QGroupBox('控制器形状（双击图标创建）')
            shape_group_layout = QtWidgets.QVBoxLayout(shape_group)
            self.shape_list = QtWidgets.QListWidget()
            self.shape_list.itemDoubleClicked.connect(self._create_from_item)
            self.shape_list.setViewMode(QT_LIST_ICON_MODE)
            self.shape_list.setFlow(QT_LIST_LEFT_TO_RIGHT)
            self.shape_list.setWrapping(True)
            self.shape_list.setResizeMode(QT_LIST_ADJUST)
            self.shape_list.setMovement(QT_LIST_STATIC)
            self.shape_list.setIconSize(QtCore.QSize(72, 72))
            self.shape_list.setGridSize(QtCore.QSize(82, 82))
            self.shape_list.setSpacing(4)
            self.shape_list.setMinimumHeight(210)
            self.shape_list.setAlternatingRowColors(False)
            shape_group_layout.addWidget(self.shape_list)
            root.addWidget(shape_group)
            edit_row = QtWidgets.QHBoxLayout()
            edit_row.setSpacing(6)
            replace_btn = QtWidgets.QPushButton('替换形状'); replace_btn.clicked.connect(lambda: self._replace(False))
            edit_row.addWidget(replace_btn); root.addLayout(edit_row)
            axis_group = QtWidgets.QGroupBox('形状操作')
            axis_row = QtWidgets.QHBoxLayout(axis_group)
            self.axis_combo = QtWidgets.QComboBox(); self.axis_combo.addItems(['X', 'Y', 'Z'])
            axis_row.setSpacing(6)
            axis_row.addWidget(QtWidgets.QLabel('轴向')); axis_row.addWidget(self.axis_combo)
            mirror_btn = QtWidgets.QPushButton('镜像'); mirror_btn.clicked.connect(self._mirror); axis_row.addWidget(mirror_btn)
            flip_btn = QtWidgets.QPushButton('翻转'); flip_btn.clicked.connect(self._flip); axis_row.addWidget(flip_btn)
            root.addWidget(axis_group)
            scale_group = QtWidgets.QGroupBox('缩放')
            scale_row = QtWidgets.QHBoxLayout(scale_group)
            self.scale_factor = QtWidgets.QDoubleSpinBox()
            self.scale_factor.setRange(0.1, 10.0)
            self.scale_factor.setDecimals(1)
            self.scale_factor.setSingleStep(0.1)
            self.scale_factor.setValue(1.0)
            self.scale_factor.setToolTip('输入直接缩放倍率，例如 0.9、1.1 或 2.0')
            scale_apply_btn = QtWidgets.QPushButton('应用缩放')
            scale_apply_btn.clicked.connect(self._apply_scale)
            scale_row.addWidget(QtWidgets.QLabel('调整控制器大小'))
            scale_row.addWidget(self.scale_factor)
            scale_row.addWidget(scale_apply_btn)
            root.addWidget(scale_group)
            custom_row = QtWidgets.QHBoxLayout(); custom_row.setSpacing(6)
            add_btn = QtWidgets.QPushButton('添加自定义形状'); add_btn.clicked.connect(self._add_custom)
            delete_btn = QtWidgets.QPushButton('删除形状'); delete_btn.clicked.connect(self._delete_custom)
            custom_row.addWidget(add_btn); custom_row.addWidget(delete_btn); root.addLayout(custom_row)
            self.status = QtWidgets.QLabel('就绪'); self.status.setObjectName('statusLabel'); root.addWidget(self.status)
            self.setStyleSheet(self.styleSheet() + ' QLabel#statusLabel { color: #ffffff; padding: 3px 2px; } QLabel#statusLabel[error="true"] { color: #ff6b6b; }')

        def _selected_shape(self):
            item = self.shape_list.currentItem()
            return item.data(QT_USER_ROLE) if item else 'circle'

        def _refresh_shapes(self):
            self.shape_list.clear()
            for name in list(BUILTIN_SHAPES) + list(self.custom):
                item = QtWidgets.QListWidgetItem()
                item.setData(QT_USER_ROLE, name)
                item.setToolTip('双击图标创建控制器')
                icon = self.custom.get(name, {}).get('icon', '')
                if icon and os.path.isfile(icon):
                    item.setIcon(QtGui.QIcon(icon))
                else:
                    generated = _make_shape_icon(name)
                    if generated: item.setIcon(generated)
                self.shape_list.addItem(item)
            self.shape_list.setCurrentRow(0)

        def _set_status(self, text, error=False):
            self.status.setProperty('error', 'true' if error else 'false')
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.status.setText(text)

        def _run(self, fn, message):
            try:
                with undo_chunk(message): fn()
                self._set_status('完成：' + message)
            except Exception as exc:
                self._set_status('失败：' + str(exc), error=True); cmds.warning(str(exc))

        def _create(self):
            self._run(lambda: create_controller(name=self.name_edit.text() or 'ctrl', shape=self._selected_shape(), size=1.0, color=self.selected_color_index), '创建控制器')

        def _create_from_item(self, item):
            self._run(lambda: create_controller(name=self.name_edit.text() or 'ctrl', shape=item.data(QT_USER_ROLE), size=1.0, color=self.selected_color_index), '创建控制器')

        def _replace(self, append=False): self._run(lambda: replace_shape_from_reference(), '替换选中控制器形状')
        def _mirror(self): self._run(lambda: mirror_shape_to_counterpart(self.axis_combo.currentText()), '镜像到左右对应控制器')
        def _flip(self): self._run(lambda: flip_shape(self.axis_combo.currentText(), degrees=90.0), '90度翻转控制器形状')
        def _select_color_button(self):
            button = self.sender()
            self.selected_color_index = int(button.property('colorIndex'))
            self._update_color_button_state()
            self.status.setText('已选择 Maya 颜色索引：%d' % self.selected_color_index)

        def _update_color_button_state(self):
            for button in getattr(self, 'color_buttons', []):
                index = int(button.property('colorIndex'))
                rgb = next((item[2] for item in MAYA_COLORS if item[0] == index), '#777777')
                if index == self.selected_color_index:
                    # 原生色板选中状态：白色外框 + 黑色内框，仍保持色块可见。
                    border = '2px solid #ffffff; outline: 1px solid #000000;'
                else:
                    border = '1px solid #303030;'
                button.setStyleSheet(
                    'QToolButton { background-color: %s; border: %s padding: 0px; } '
                    'QToolButton:hover { border: 1px solid #ffffff; }' % (rgb, border))

        def _apply_color_double_click(self, button, event):
            self.selected_color_index = int(button.property('colorIndex'))
            self._update_color_button_state()
            selected = cmds.ls(selection=True, type='transform') or []
            self._run(lambda: _set_color(_shape_nodes(selected[0]), self.selected_color_index), '替换控制器颜色')
            # 自定义形状图标同步使用当前颜色，避免场景控制器与图标不一致。
            key = self._selected_shape()
            if key in self.custom and selected:
                try:
                    path = _save_shape_icon(
                        key, os.path.join(ICONS_DIR, _safe_name(key) + '.png'))
                    data = load_custom_shapes(); data[key]['icon'] = path; save_custom_shapes(data)
                    self.custom = data; self._refresh_shapes()
                    self.status.setText('控制器颜色和图标已同步：Index %d' % self.selected_color_index)
                except Exception as exc:
                    self._set_status('颜色已替换，但图标更新失败：' + str(exc), error=True); cmds.warning(str(exc))
            event.accept()
        def _apply_scale(self):
            """Apply the entered value as a direct scale multiplier."""
            factor = self.scale_factor.value()
            self._run(lambda: scale_controller_shapes(factor=factor), '调整选中控制器大小')
        def _delete_custom(self):
            key = self._selected_shape()
            if key not in self.custom:
                self._set_status('只能删除自定义形状，内置形状不可删除。', error=True)
                return
            display_name = self.custom.get(key, {}).get('displayName', key)
            answer = QtWidgets.QMessageBox.question(
                self, '确认删除', '确定删除已保存的形状“%s”及其图标吗？\n不会删除场景中的控制器。' % display_name,
                QT_MSG_YES | QT_MSG_NO,
                QT_MSG_NO)
            if answer != QT_MSG_YES:
                return
            try:
                data = load_custom_shapes()
                entry = data.pop(key, {})
                icon = entry.get('icon', '')
                if icon and os.path.isfile(icon):
                    os.remove(icon)
                else:
                    default_icon = os.path.join(ICONS_DIR, _safe_name(key) + '.png')
                    if os.path.isfile(default_icon): os.remove(default_icon)
                save_custom_shapes(data)
                self.custom = data
                self._refresh_shapes()
                self.status.setText('已删除保存的形状：' + display_name)
            except Exception as exc:
                self._set_status('删除失败：' + str(exc), error=True); cmds.warning(str(exc))

        def _add_custom(self):
            try:
                key = add_custom_shape()
                path = _save_shape_icon(
                    key, os.path.join(ICONS_DIR, _safe_name(key) + '.png'))
                data = load_custom_shapes(); data[key]['icon'] = path; save_custom_shapes(data)
                self.custom = data; self._refresh_shapes()
                self.status.setText('自定义形状和图标已添加')
            except Exception as exc:
                self._set_status('添加失败：' + str(exc), error=True); cmds.warning(str(exc))
        def _screenshot(self):
            try:
                key = self._selected_shape()
                if key not in self.custom:
                    raise RuntimeError('只有自定义形状可以更新截图图标；内置形状使用自动线稿图标。')
                path = _save_shape_icon(
                    key, os.path.join(ICONS_DIR, _safe_name(key) + '.png'))
                data = load_custom_shapes(); data[key]['icon'] = path; save_custom_shapes(data); self.custom = data; self._refresh_shapes()
                self.status.setText('图标已更新：' + key)
            except Exception as exc: self._set_status('截图失败：' + str(exc), error=True); cmds.warning(str(exc))
else:
    ControllerToolWindow = None


def show():
    """Show the tool as an independent floating window, not docked in Maya."""
    if not QtWidgets:
        raise RuntimeError('无法导入 PySide2/PySide6；请在 Maya 2022-2026 中运行。')
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_OBJECT:
            widget.close(); widget.deleteLater()
    parent = maya_main_window()
    window = ControllerToolWindow(parent=parent)
    window.setWindowFlags(QT_WINDOW | QT_WINDOW_SYSTEM_MENU |
                          QT_WINDOW_CLOSE | QT_WINDOW_MINIMIZE |
                          QT_WINDOW_MAXIMIZE)
    window.setAttribute(QT_DELETE_ON_CLOSE, True)
    window.showNormal()
    window.raise_()
    window.activateWindow()
    return window
