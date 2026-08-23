# -*- coding: utf-8 -*-
"""Naming operations for selected Maya transforms and joint chains."""
from __future__ import print_function

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None


def _selected_transforms():
    selection = [node for node in
                 (cmds.ls(selection=True, long=True) or [])
                 if cmds.nodeType(node) in ('transform', 'joint')]
    if not selection:
        raise RuntimeError('请先选择需要重命名的对象或骨骼。')
    return list(dict.fromkeys(selection))


def _descendants(node, joints_only=False):
    descendants = cmds.listRelatives(
        node, allDescendents=True, fullPath=True) or []
    if joints_only:
        return [item for item in descendants if cmds.nodeType(item) == 'joint']
    return [item for item in descendants
            if cmds.nodeType(item) in ('transform', 'joint')]


def _depth(node):
    return node.count('|')


def _leaf_name(node):
    return node.rsplit('|', 1)[-1]


def _local_name(node):
    leaf = _leaf_name(node)
    namespace, separator, local = leaf.rpartition(':')
    return local if separator else leaf


def _namespace(node):
    leaf = _leaf_name(node)
    namespace, separator, _local = leaf.rpartition(':')
    return namespace + ':' if separator else ''


def _rename_with_temporary_names(nodes, final_names):
    """Rename a hierarchy safely without invalidating stored DAG paths."""
    nodes = sorted(nodes, key=_depth, reverse=True)
    temporary = {}
    counter = 0
    for node in nodes:
        while True:
            candidate = '__YiDaoNamingTmp_%d' % counter
            counter += 1
            if not cmds.objExists(candidate):
                break
        temporary[node] = cmds.rename(node, candidate)
    renamed = []
    for original in sorted(nodes, key=_depth):
        temp_name = temporary[original]
        matches = cmds.ls(temp_name, long=True) or []
        if not matches:
            raise RuntimeError('临时重命名对象丢失：%s' % original)
        current = matches[0]
        renamed.append(cmds.rename(current, final_names[original]))
    return renamed


def search_replace(search, replace, hierarchy=False, targets=None):
    """Search and replace local names on selected transforms."""
    if not cmds:
        raise RuntimeError('该工具必须在 Maya 中运行。')
    search = str(search)
    replace = str(replace)
    if not search:
        raise RuntimeError('查找内容不能为空。')
    targets = targets or _selected_transforms()
    nodes = list(targets)
    if hierarchy:
        for node in targets:
            nodes.extend(_descendants(node))
    nodes = list(dict.fromkeys(nodes))
    final_names = {}
    changed = []
    for node in nodes:
        local = _local_name(node)
        if search not in local:
            continue
        final_names[node] = _namespace(node) + local.replace(search, replace)
        changed.append(node)
    if not changed:
        return []
    return _rename_with_temporary_names(changed, final_names)


def _default_chain_base(root):
    local = _local_name(root)
    if len(local) > 3 and local[-3] in ('_', '-') and local[-2:].isdigit():
        return local[:-3]
    return local


def rename_hierarchy_chain(base_name='', separator='_', start_index=0,
                           digits=2, include_children=False, root=None):
    """Rename a selected transform hierarchy from parent to child order."""
    if not cmds:
        raise RuntimeError('该工具必须在 Maya 中运行。')
    if root is None:
        selected = [node for node in
                    (cmds.ls(selection=True, long=True) or [])
                    if cmds.nodeType(node) in ('transform', 'joint')]
        if not selected:
            raise RuntimeError('请先选择层级链的根节点。')
        root = selected[0]
    if cmds.nodeType(root) not in ('transform', 'joint'):
        raise RuntimeError('选择的对象不是可重命名的层级节点：%s' % root)
    nodes = [root]
    if include_children:
        nodes += _descendants(root)
    nodes = list(dict.fromkeys(nodes))
    nodes.sort(key=_depth)
    base_name = str(base_name).strip() or _default_chain_base(root)
    separator = str(separator)
    try:
        start_index = int(start_index)
        digits = max(1, int(digits))
    except (TypeError, ValueError):
        raise RuntimeError('起始编号和位数必须是整数。')
    final_names = {}
    for offset, node in enumerate(nodes):
        number = str(start_index + offset).zfill(digits)
        final_names[node] = base_name + separator + number
    return _rename_with_temporary_names(nodes, final_names)


def chain_base_from_selection():
    selected = [node for node in
                (cmds.ls(selection=True, long=True) or [])
                if cmds.nodeType(node) in ('transform', 'joint')]
    if not selected:
        return ''
    return _default_chain_base(selected[0])


# Backward-compatible alias for scripts that used the earlier name.
rename_joint_chain = rename_hierarchy_chain


def undo_chunk(label):
    class _Chunk(object):
        def __enter__(self):
            cmds.undoInfo(openChunk=True, chunkName=label)
            return self
        def __exit__(self, exc_type, exc_value, traceback):
            cmds.undoInfo(closeChunk=True)
    return _Chunk()
