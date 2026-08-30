# -*- coding: utf-8 -*-
"""Qt UI for explicit source/target Joint Match."""
from __future__ import print_function

from ..compat.qt_compat import (
    QtCore, QtWidgets, QT_WINDOW, QT_WINDOW_SYSTEM_MENU, QT_WINDOW_CLOSE,
    QT_WINDOW_MINIMIZE, QT_WINDOW_MAXIMIZE, QT_DELETE_ON_CLOSE,
)
from ..compat.maya_compat import cmds, display_node, maya_main_window
from ..core.joint_match_ops import match_joint_root_sets, undo_chunk
from ..core.ui_state import setup_state

WINDOW_OBJECT = 'yidaoJointMatchWindow'
_STYLE = '''
QDialog { background: #202020; color: #e8e8e8; }
QLabel { color: #cfcfcf; }
QGroupBox { border: 1px solid #3c3c3c; border-radius: 5px; margin-top: 8px; padding: 8px 6px 6px 6px; font-weight: bold; color: #e0e0e0; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QListWidget, QLineEdit { background: #292929; border: 1px solid #4a4a4a; border-radius: 3px; padding: 4px 6px; color: #f0f0f0; }
QListWidget { min-height: 105px; }
QPushButton { background: #353535; border: 1px solid #4d4d4d; border-radius: 3px; padding: 5px 10px; min-height: 26px; color: #ededed; }
QPushButton:hover { background: #454545; border-color: #6b9dcc; }
QCheckBox { color: #d8d8d8; spacing: 6px; }
'''


if QtWidgets:
    class JointMatchWindow(QtWidgets.QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName(WINDOW_OBJECT)
            self.setWindowTitle('Joint Match')
            self.setMinimumSize(700, 430)
            self.setStyleSheet(_STYLE)
            self._build_ui()
            self._save_ui_state = setup_state(self, 'joint_match')

        def _build_ui(self):
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(10, 10, 10, 10)
            root.setSpacing(8)
            info = QtWidgets.QLabel(
                '左侧加载源骨骼，右侧加载目标骨骼。源和目标均可加载多个。\n'
                '工具只匹配当前加载的骨骼，并在去除命名空间后按名称匹配。')
            info.setWordWrap(True)
            root.addWidget(info)

            columns = QtWidgets.QHBoxLayout()
            self.source_list, source_box = self._make_column(
                '源骨骼（可多选）', role_name='源骨骼')
            self.target_list, target_box = self._make_column(
                '目标骨骼（可多选）', role_name='目标骨骼')
            columns.addWidget(source_box)
            columns.addWidget(target_box)
            root.addLayout(columns)

            attrs = QtWidgets.QGroupBox('匹配属性')
            attrs_layout = QtWidgets.QHBoxLayout(attrs)
            self.translation_check = QtWidgets.QCheckBox('Translation')
            self.translation_check.setChecked(True)
            self.rotation_check = QtWidgets.QCheckBox('Rotation')
            self.rotation_check.setChecked(True)
            self.scale_check = QtWidgets.QCheckBox('Scale')
            self.scale_check.setChecked(False)
            for widget in (self.translation_check, self.rotation_check, self.scale_check):
                attrs_layout.addWidget(widget)
            attrs_layout.addStretch()
            root.addWidget(attrs)

            button = QtWidgets.QPushButton('匹配所选骨骼')
            button.setMinimumHeight(38)
            button.clicked.connect(self._match)
            root.addWidget(button)
            self.status = QtWidgets.QLabel('就绪：请分别加载源骨骼和目标骨骼')
            self.status.setObjectName('statusLabel')
            self.status.setStyleSheet('QLabel#statusLabel { color: #ffffff; padding: 3px 2px; } QLabel#statusLabel[error="true"] { color: #ff4d4d; }')
            root.addWidget(self.status)

        def _make_column(self, title, role_name):
            box = QtWidgets.QGroupBox(title)
            layout = QtWidgets.QVBoxLayout(box)
            listing = QtWidgets.QListWidget()
            listing.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
            add = QtWidgets.QPushButton('从当前选择加载')
            clear = QtWidgets.QPushButton('清除')
            add.clicked.connect(
                lambda: self._load_current(listing, role_name))
            clear.clicked.connect(listing.clear)
            layout.addWidget(listing)
            buttons = QtWidgets.QHBoxLayout()
            buttons.addWidget(add)
            buttons.addWidget(clear)
            layout.addLayout(buttons)
            return listing, box

        def _load_current(self, listing, role_name):
            selection = cmds.ls(selection=True, type='joint', long=True) or []
            if not selection:
                self._set_status(
                    '失败：请先在 Maya 中选择骨骼', error=True)
                return
            listing.clear()
            roots = selection
            for root in roots:
                # Keep the full DAG path as internal data. Display a short
                # name when unique, otherwise the full DAG path.
                item = QtWidgets.QListWidgetItem(display_node(root))
                item.setData(QtCore.Qt.UserRole, root)
                listing.addItem(item)
            listing.setCurrentRow(0)
            if len(roots) == 1:
                message = '已加载：' + display_node(roots[0])
            else:
                message = '已加载 %d 个%s' % (len(roots), role_name)
            self._set_status(message, error=False)

        def _loaded_roots(self, listing):
            roots = []
            for index in range(listing.count()):
                item = listing.item(index)
                root = item.data(QtCore.Qt.UserRole)
                if root:
                    roots.append(root)
            return roots

        def _set_status(self, text, error=False):
            self.status.setProperty('error', 'true' if error else 'false')
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.status.setText(text)

        def _match(self):
            sources = self._loaded_roots(self.source_list)
            targets = self._loaded_roots(self.target_list)
            try:
                with undo_chunk('YiDao Joint Match'):
                    matched, warnings = match_joint_root_sets(
                        sources, targets,
                        hierarchy=False,
                        translation=self.translation_check.isChecked(),
                        rotation=self.rotation_check.isChecked(),
                        scale=self.scale_check.isChecked())
                for warning in warnings:
                    cmds.warning(warning)
                self._set_status('完成：匹配 %d 个骨骼，警告 %d 条' %
                                 (len(matched), len(warnings)), error=bool(warnings))
            except Exception as exc:
                self._set_status('失败：' + str(exc), error=True)
                cmds.warning(str(exc))
else:
    JointMatchWindow = None


def show():
    if not QtWidgets:
        raise RuntimeError('无法导入 PySide2/PySide6；请在 Maya 2022-2026 中运行。')
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_OBJECT:
            widget.close()
            widget.deleteLater()
    window = JointMatchWindow(parent=maya_main_window())
    window.setWindowFlags(QT_WINDOW | QT_WINDOW_SYSTEM_MENU | QT_WINDOW_CLOSE |
                          QT_WINDOW_MINIMIZE | QT_WINDOW_MAXIMIZE)
    window.setAttribute(QT_DELETE_ON_CLOSE, True)
    window.showNormal()
    window.raise_()
    window.activateWindow()
    return window
