# -*- coding: utf-8 -*-
"""Qt UI for Attribute Cleanup."""
from __future__ import print_function

from ..compat.qt_compat import (
    QtCore, QtWidgets, QT_WINDOW, QT_WINDOW_SYSTEM_MENU, QT_WINDOW_CLOSE,
    QT_WINDOW_MINIMIZE, QT_WINDOW_MAXIMIZE, QT_DELETE_ON_CLOSE,
)
from ..compat.maya_compat import cmds, maya_main_window
from ..core.attribute_cleanup_ops import (
    cleanup_attributes, find_non_default_transforms, undo_chunk)
from ..core.ui_state import setup_state


WINDOW_OBJECT = 'yidaoAttributeCleanupWindow'
_STYLE = '''
QDialog { background: #202020; color: #e8e8e8; }
QLabel { color: #cfcfcf; }
QGroupBox { border: 1px solid #3c3c3c; border-radius: 5px; margin-top: 8px; padding: 8px 6px 6px 6px; font-weight: bold; color: #e0e0e0; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QPushButton { background: #353535; border: 1px solid #4d4d4d; border-radius: 3px; padding: 5px 10px; min-height: 26px; color: #ededed; }
QPushButton:hover { background: #454545; border-color: #6b9dcc; }
QCheckBox { color: #d8d8d8; spacing: 6px; }
'''


if QtWidgets:
    class AttributeCleanupWindow(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName(WINDOW_OBJECT)
            self.setWindowTitle('Attribute Cleanup')
            self.setMinimumSize(470, 350)
            self.setStyleSheet(_STYLE)
            self._build_ui()
            self._save_ui_state = setup_state(self, 'attribute_cleanup')

        def _build_ui(self):
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(10, 10, 10, 10)
            root.setSpacing(8)
            info = QtWidgets.QLabel('直接设置属性值，不使用 Freeze Transformations。')
            info.setWordWrap(True)
            root.addWidget(info)

            transform_group = QtWidgets.QGroupBox('Transform 属性清理')
            transform_layout = QtWidgets.QVBoxLayout(transform_group)
            self.translate_check = QtWidgets.QCheckBox('Translate → 0, 0, 0')
            self.translate_check.setChecked(False)
            self.rotate_check = QtWidgets.QCheckBox('Rotate → 0, 0, 0')
            self.rotate_check.setChecked(False)
            self.scale_check = QtWidgets.QCheckBox('Scale → 1, 1, 1')
            self.scale_check.setChecked(False)
            for widget in (self.translate_check, self.rotate_check, self.scale_check):
                transform_layout.addWidget(widget)
            root.addWidget(transform_group)

            joint_group = QtWidgets.QGroupBox('Joint 选项')
            joint_layout = QtWidgets.QVBoxLayout(joint_group)
            self.zero_orient_check = QtWidgets.QCheckBox('选中骨骼时，将 Joint Orient → 0, 0, 0')
            self.bake_rotation_check = QtWidgets.QCheckBox('将 Rotate 烘焙到 Joint Orient（普通骨骼；支持 orientConstraint / parentConstraint）')
            joint_layout.addWidget(self.zero_orient_check)
            joint_layout.addWidget(self.bake_rotation_check)
            root.addWidget(joint_group)

            button = QtWidgets.QPushButton('清理所选对象属性')
            button.setMinimumHeight(38)
            button.clicked.connect(self._cleanup)
            root.addWidget(button)

            scan_button = QtWidgets.QPushButton(
                '筛查非默认 Transform，并选中异常对象')
            scan_button.setMinimumHeight(34)
            scan_button.clicked.connect(self._scan)
            root.addWidget(scan_button)
            self.status = QtWidgets.QLabel('就绪：请选择对象或骨骼')
            self.status.setObjectName('statusLabel')
            self.status.setStyleSheet('QLabel#statusLabel { color: #ffffff; padding: 3px 2px; } QLabel#statusLabel[error="true"] { color: #ff6b6b; }')
            root.addWidget(self.status)

        def _set_status(self, text, error=False):
            self.status.setProperty('error', 'true' if error else 'false')
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.status.setText(text)

        def _scan(self):
            try:
                offenders, details = find_non_default_transforms()
                if offenders:
                    self._set_status('筛查完成：选中 %d 个非默认对象' % len(offenders))
                    print('[YiDao Rig] 非默认 Transform 筛查结果：')
                    for detail in details:
                        print('[YiDao Rig] ' + detail)
                else:
                    self._set_status('筛查完成：所有对象均为默认 Transform')
            except Exception as exc:
                self._set_status('筛查失败：' + str(exc), error=True)
                if cmds:
                    cmds.warning(str(exc))

        def _cleanup(self):
            if self.zero_orient_check.isChecked() and self.bake_rotation_check.isChecked():
                result = QtWidgets.QMessageBox.question(
                    self,
                    '确认 Joint 操作',
                    '你同时勾选了“Joint Orient 清零”和“将 Rotate 烘焙到 Joint Orient”。\\n\\n'
                    '烘焙完成后，Joint Orient 会被清零，烘焙的旋转结果将不会保留。\\n'
                    '确定要继续执行吗？',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No)
                if result != QtWidgets.QMessageBox.Yes:
                    self._set_status('已取消：请重新选择 Joint 操作')
                    return
            try:
                with undo_chunk('YiDao Attribute Cleanup'):
                    changed, warnings = cleanup_attributes(
                        translate=self.translate_check.isChecked(),
                        rotate=self.rotate_check.isChecked(),
                        scale=self.scale_check.isChecked(),
                        zero_joint_orient=self.zero_orient_check.isChecked(),
                        bake_joint_rotation=self.bake_rotation_check.isChecked())
                if warnings:
                    self._set_status('完成：%d 个对象，跳过 %d 个（请查看警告）' %
                                     (len(changed), len(warnings)), error=True)
                    for warning in warnings:
                        if cmds:
                            cmds.warning(warning)
                else:
                    self._set_status('完成：已清理 %d 个对象' % len(changed))
            except Exception as exc:
                self._set_status('失败：' + str(exc), error=True)
                if cmds:
                    cmds.warning(str(exc))
else:
    AttributeCleanupWindow = None


def show():
    if not QtWidgets:
        raise RuntimeError('无法导入 PySide2/PySide6；请在 Maya 2022-2026 中运行。')
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_OBJECT:
            widget.close()
            widget.deleteLater()
    window = AttributeCleanupWindow(parent=maya_main_window())
    window.setWindowFlags(QT_WINDOW | QT_WINDOW_SYSTEM_MENU | QT_WINDOW_CLOSE |
                          QT_WINDOW_MINIMIZE | QT_WINDOW_MAXIMIZE)
    window.setAttribute(QT_DELETE_ON_CLOSE, True)
    window.showNormal()
    window.raise_()
    window.activateWindow()
    return window
