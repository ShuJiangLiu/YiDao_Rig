# -*- coding: utf-8 -*-
"""Qt UI for skin weight import/export."""
from __future__ import print_function

from ..compat.qt_compat import (
    QtCore, QtWidgets, QT_WINDOW, QT_WINDOW_SYSTEM_MENU, QT_WINDOW_CLOSE,
    QT_WINDOW_MINIMIZE, QT_WINDOW_MAXIMIZE, QT_DELETE_ON_CLOSE,
)
from ..compat.maya_compat import cmds, maya_main_window
from ..core.skin_weight_ops import export_weights, import_weights, undo_chunk, _selected_meshes
from ..core.ui_state import setup_state

WINDOW_OBJECT = 'yidaoSkinWeightWindow'
_STYLE = '''
QDialog { background: #202020; color: #e8e8e8; }
QLabel { color: #cfcfcf; }
QGroupBox { border: 1px solid #3c3c3c; border-radius: 5px; margin-top: 8px; padding: 8px 6px 6px 6px; font-weight: bold; color: #e0e0e0; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLineEdit { background: #292929; border: 1px solid #4a4a4a; border-radius: 3px; padding: 4px 6px; color: #f0f0f0; min-height: 22px; }
QPushButton { background: #353535; border: 1px solid #4d4d4d; border-radius: 3px; padding: 5px 10px; min-height: 26px; color: #ededed; }
QPushButton:hover { background: #454545; border-color: #6b9dcc; }
'''

if QtWidgets:
    class SkinWeightWindow(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName(WINDOW_OBJECT)
            self.setWindowTitle('Skin Weight Import / Export')
            self.setMinimumSize(620, 270)
            self.setStyleSheet(_STYLE)
            self._build_ui()
            self._save_ui_state = setup_state(self, 'skin_weight')

        def _build_ui(self):
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(10, 10, 10, 10)
            root.setSpacing(8)
            info = QtWidgets.QLabel(
                '可同时选择多个网格，每个模型分别导出为一个 JSON 文件。文件保存顶点权重和影响骨骼的精确小数值，\n'
                '导入时选择一个 JSON 文件或包含多个 JSON 文件的文件夹；没有 skinCluster 的目标会自动创建蒙皮。')
            info.setWordWrap(True)
            root.addWidget(info)

            file_group = QtWidgets.QGroupBox('权重文件')
            file_layout = QtWidgets.QHBoxLayout(file_group)
            self.path_edit = QtWidgets.QLineEdit()
            self.path_edit.setPlaceholderText('选择 .json 文件或权重文件夹')
            browse = QtWidgets.QPushButton('浏览...')
            browse.clicked.connect(self._browse)
            file_layout.addWidget(self.path_edit)
            file_layout.addWidget(browse)
            root.addWidget(file_group)

            actions = QtWidgets.QHBoxLayout()
            export_button = QtWidgets.QPushButton('导出所选网格权重')
            import_button = QtWidgets.QPushButton('导入权重到所选网格')
            export_button.setMinimumHeight(38)
            import_button.setMinimumHeight(38)
            export_button.clicked.connect(self._export)
            import_button.clicked.connect(self._import)
            actions.addWidget(export_button)
            actions.addWidget(import_button)
            root.addLayout(actions)
            self.status = QtWidgets.QLabel('就绪：请选择带 skinCluster 的网格')
            self.status.setObjectName('statusLabel')
            self.status.setStyleSheet('QLabel#statusLabel { color: #ffffff; padding: 3px 2px; } QLabel#statusLabel[error="true"] { color: #ff4d4d; }')
            root.addWidget(self.status)

        def _set_status(self, text, error=False):
            self.status.setProperty('error', 'true' if error else 'false')
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.status.setText(text)

        def _browse(self):
            path = QtWidgets.QFileDialog.getExistingDirectory(
                self, '选择蒙皮权重文件夹', self.path_edit.text() or '')
            if path:
                self.path_edit.setText(path)

        def _export(self):
            path = QtWidgets.QFileDialog.getExistingDirectory(
                self, '选择权重导出文件夹', self.path_edit.text() or '')
            if not path:
                return
            try:
                meshes = _selected_meshes()
                if not meshes:
                    raise RuntimeError('请至少选择一个网格。')
                payload = export_weights(path, meshes=meshes)
                self.path_edit.setText(path)
                self._set_status('导出完成：%d 个 JSON 文件' % len(payload))
            except Exception as exc:
                self._set_status('导出失败：' + str(exc), error=True)
                cmds.warning(str(exc))

        def _import(self):
            path = self.path_edit.text().strip()
            if not path:
                self._browse()
                path = self.path_edit.text().strip()
            if not path:
                return
            try:
                with undo_chunk('YiDao Skin Weight Import'):
                    meshes = _selected_meshes()
                    if not meshes:
                        raise RuntimeError('请至少选择一个目标网格。')
                    changed, warnings = import_weights(path, meshes=meshes)
                if warnings:
                    self._set_status('导入完成：%d 个网格，存在额外影响骨骼' % len(changed))
                    for warning in warnings:
                        print('[YiDao Rig] ' + warning)
                        cmds.warning(warning)
                else:
                    self._set_status('导入完成：%d 个网格' % len(changed))
            except Exception as exc:
                self._set_status('导入失败：' + str(exc), error=True)
                cmds.warning(str(exc))
else:
    SkinWeightWindow = None


def show():
    if not QtWidgets:
        raise RuntimeError('无法导入 PySide2/PySide6；请在 Maya 2022-2026 中运行。')
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_OBJECT:
            widget.close()
            widget.deleteLater()
    window = SkinWeightWindow(parent=maya_main_window())
    window.setWindowFlags(QT_WINDOW | QT_WINDOW_SYSTEM_MENU | QT_WINDOW_CLOSE |
                          QT_WINDOW_MINIMIZE | QT_WINDOW_MAXIMIZE)
    window.setAttribute(QT_DELETE_ON_CLOSE, True)
    window.showNormal()
    window.raise_()
    window.activateWindow()
    return window
