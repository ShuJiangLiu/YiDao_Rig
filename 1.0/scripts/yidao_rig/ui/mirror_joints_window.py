# -*- coding: utf-8 -*-
"""Qt interface for the precision Mirror Joints tool."""
from __future__ import print_function

from ..compat.qt_compat import (
    QtCore, QtWidgets, QT_ALIGN_RIGHT, QT_ALIGN_VCENTER,
    QT_WINDOW, QT_WINDOW_SYSTEM_MENU, QT_WINDOW_CLOSE,
    QT_WINDOW_MINIMIZE, QT_WINDOW_MAXIMIZE, QT_DELETE_ON_CLOSE,
)
from ..compat.maya_compat import cmds, maya_main_window
from ..core.joint_mirror_ops import mirror_selected
from ..core.ui_state import setup_state

WINDOW_OBJECT = 'yidaoMirrorJointsWindow'

_STYLE = '''
QDialog { background: #202020; color: #e8e8e8; }
QLabel { color: #cfcfcf; }
QGroupBox { border: 1px solid #3c3c3c; border-radius: 5px; margin-top: 8px; padding: 8px 6px 6px 6px; font-weight: bold; color: #e0e0e0; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLineEdit, QComboBox { background: #292929; border: 1px solid #4a4a4a; border-radius: 3px; padding: 4px 6px; color: #f0f0f0; min-height: 22px; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #6b9dcc; }
QPushButton { background: #353535; border: 1px solid #4d4d4d; border-radius: 3px; padding: 5px 10px; min-height: 24px; color: #ededed; }
QPushButton:hover { background: #454545; border-color: #6b9dcc; }
QPushButton:pressed { background: #2a2a2a; }
QCheckBox { color: #d8d8d8; spacing: 6px; }
'''


if QtWidgets:
    class MirrorJointsWindow(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName(WINDOW_OBJECT)
            self.setWindowTitle('Mirror Joints')
            self.setMinimumSize(520, 430)
            self.setStyleSheet(_STYLE)
            self._build_ui()
            self._save_ui_state = setup_state(self, 'mirror_joints')

        def _build_ui(self):
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(10, 10, 10, 10)
            root.setSpacing(8)

            plane_group = QtWidgets.QGroupBox('镜像平面')
            plane_layout = QtWidgets.QHBoxLayout(plane_group)
            self.plane_combo = QtWidgets.QComboBox()
            self.plane_combo.addItem('XY（翻转 Z 轴）', 'XY')
            self.plane_combo.addItem('YZ（翻转 X 轴）', 'YZ')
            self.plane_combo.addItem('XZ（翻转 Y 轴）', 'XZ')
            self.plane_combo.setCurrentIndex(1)
            plane_layout.addWidget(QtWidgets.QLabel('Mirror Across'))
            plane_layout.addWidget(self.plane_combo)
            root.addWidget(plane_group)

            mode_group = QtWidgets.QGroupBox('镜像方式')
            mode_layout = QtWidgets.QVBoxLayout(mode_group)
            self.behavior_radio = QtWidgets.QRadioButton('Behavior 行为镜像（与 Maya mirrorJoint -mb 一致）')
            self.orientation_radio = QtWidgets.QRadioButton('Orientation 仅镜像位置，保持旋转')
            self.behavior_radio.setChecked(True)
            mode_layout.addWidget(self.behavior_radio)
            mode_layout.addWidget(self.orientation_radio)
            root.addWidget(mode_group)

            name_group = QtWidgets.QGroupBox('命名替换')
            name_layout = QtWidgets.QHBoxLayout(name_group)
            self.search_edit = QtWidgets.QLineEdit('_r')
            self.replace_edit = QtWidgets.QLineEdit('_l')
            swap = QtWidgets.QPushButton('<->')
            swap.setFixedWidth(48)
            swap.clicked.connect(self._swap_names)
            name_layout.addWidget(QtWidgets.QLabel('Search'))
            name_layout.addWidget(self.search_edit)
            name_layout.addWidget(swap)
            name_layout.addWidget(QtWidgets.QLabel('Replace'))
            name_layout.addWidget(self.replace_edit)
            root.addWidget(name_group)

            self.hierarchy_check = QtWidgets.QCheckBox('镜像整个层级  Mirror Hierarchy')
            self.hierarchy_check.setChecked(True)
            root.addWidget(self.hierarchy_check)

            button = QtWidgets.QPushButton('镜像所选骨骼  Mirror Selected Joints')
            button.setMinimumHeight(38)
            button.clicked.connect(self._mirror)
            root.addWidget(button)
            self.status = QtWidgets.QLabel('就绪：请选择要镜像的骨骼')
            self.status.setObjectName('statusLabel')
            self.status.setStyleSheet('QLabel#statusLabel { color: #ffffff; padding: 3px 2px; } QLabel#statusLabel[error="true"] { color: #ff6b6b; }')
            root.addWidget(self.status)

        def _swap_names(self):
            search = self.search_edit.text()
            self.search_edit.setText(self.replace_edit.text())
            self.replace_edit.setText(search)

        def _set_status(self, text, error=False):
            self.status.setProperty('error', 'true' if error else 'false')
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.status.setText(text)

        def _mirror(self):
            search = self.search_edit.text()
            replace = self.replace_edit.text()
            if not search:
                self._set_status('失败：Search 不能为空', error=True)
                if cmds:
                    cmds.warning('Search 不能为空')
                return
            try:
                done = mirror_selected(
                    plane=self.plane_combo.currentData(),
                    behavior=self.behavior_radio.isChecked(),
                    search=search,
                    replace=replace,
                    hierarchy=self.hierarchy_check.isChecked(),
                )
                self._set_status('完成：镜像 %d 根骨骼' % len(done) if done else '未镜像任何骨骼')
            except Exception as exc:
                self._set_status('失败：' + str(exc), error=True)
                if cmds:
                    cmds.warning(str(exc))
else:
    MirrorJointsWindow = None


def run():
    if not QtWidgets:
        raise RuntimeError('无法导入 PySide2/PySide6；请在 Maya 2022-2026 中运行。')
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_OBJECT:
            widget.close()
            widget.deleteLater()
    window = MirrorJointsWindow(parent=maya_main_window())
    window.setWindowFlags(QT_WINDOW | QT_WINDOW_SYSTEM_MENU |
                          QT_WINDOW_CLOSE | QT_WINDOW_MINIMIZE |
                          QT_WINDOW_MAXIMIZE)
    window.setAttribute(QT_DELETE_ON_CLOSE, True)
    window.showNormal()
    window.raise_()
    window.activateWindow()
    return window
