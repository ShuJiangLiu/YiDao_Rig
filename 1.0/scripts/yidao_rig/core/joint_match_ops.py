# -*- coding: utf-8 -*-
"""Joint matching operations based on source/target naming."""
from __future__ import print_function

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None

from ..compat.maya_compat import display_node


def _short(node):
    return node.split('|')[-1]


def _match_name(node):
    """Matching uses identical short names; namespaces select the target."""
    return _short(node)


def _hierarchy(root):
    result = []

    def visit(node):
        result.append(node)
        for child in cmds.listRelatives(node, children=True, type='joint',
                                        fullPath=True) or []:
            visit(child)
    visit(root)
    return result


def _unique_nodes(nodes):
    result = []
    seen = set()
    for node in nodes:
        if node not in seen:
            seen.add(node)
            result.append(node)
    return result


def _world_matrix(node):
    return cmds.xform(node, query=True, worldSpace=True, matrix=True)


def _node_namespace(node):
    """Return the namespace portion of a Maya node's short name."""
    short = _short(node)
    if ':' not in short:
        return ''
    return short.rsplit(':', 1)[0]


def _find_target_joints(short_name, target_namespace=''):
    """Find target joints, optionally restricted to an exact namespace."""
    target_namespace = (target_namespace or '').strip().rstrip(':')
    if target_namespace:
        pattern = target_namespace + ':' + short_name
        return _unique_nodes(cmds.ls(pattern, type='joint', long=True) or [])
    candidates = []
    for pattern in (short_name, '*:' + short_name):
        candidates.extend(cmds.ls(pattern, type='joint', long=True) or [])
    return _unique_nodes(candidates)


def _match_one(source, target, translation=True, rotation=True, scale=False):
    matrix = _world_matrix(source)
    if translation or rotation:
        # Matching the complete world matrix is the most reliable way to
        # preserve joint orientation and parent-space behavior. If only one
        # component is requested, retain the target's other world components.
        if translation and rotation:
            cmds.xform(target, worldSpace=True, matrix=matrix)
        else:
            if translation:
                position = cmds.xform(source, query=True, worldSpace=True,
                                      translation=True)
                cmds.xform(target, worldSpace=True, translation=position)
            if rotation:
                rotation = cmds.xform(source, query=True, worldSpace=True,
                                      rotation=True)
                cmds.xform(target, worldSpace=True, rotation=rotation)
    if scale:
        scale_value = cmds.xform(source, query=True, worldSpace=True, scale=True)
        cmds.xform(target, worldSpace=True, scale=scale_value)


def match_joints(roots, hierarchy=True, translation=True, rotation=True,
                 scale=False, target_namespace=''):
    """Match identical joint names, restricted by optional target namespace."""
    if not cmds:
        raise RuntimeError('该工具必须在 Maya 中运行。')
    if not roots:
        raise RuntimeError('请先选择源骨骼。')
    if not (translation or rotation or scale):
        raise RuntimeError('至少选择一个需要匹配的属性。')
    sources = []
    for root in roots:
        sources.extend(_hierarchy(root) if hierarchy else [root])
    sources = _unique_nodes(sources)
    matched = []
    warnings = []
    for source in sources:
        target_name = _match_name(source)
        target = _find_target_joints(target_name, target_namespace)
        if not target:
            warnings.append('找不到目标骨骼: %s（源: %s）' %
                            (target_name, display_node(source)))
            continue
        if len(target) > 1:
            warnings.append('目标名称不唯一，跳过: %s（候选: %s）' %
                            (target_name, ', '.join(display_node(item)
                                                     for item in target)))
            continue
        try:
            _match_one(source, target[0], translation, rotation, scale)
            matched.append((source, target[0]))
        except Exception as exc:
            warnings.append('%s → %s：%s' %
                            (display_node(source), display_node(target[0]), exc))
    return matched, warnings


def _relative_joint_map(root):
    """Map a joint hierarchy by relative child-index path."""
    result = {}

    def visit(node, path):
        result[path] = node
        children = cmds.listRelatives(node, children=True, type='joint',
                                      fullPath=True) or []
        for index, child in enumerate(children):
            visit(child, path + (index,))
    visit(root, ())
    return result


def match_joint_roots(source_root, target_root, hierarchy=True,
                      translation=True, rotation=True, scale=False):
    """Match an explicitly loaded source root to an explicitly loaded target root.

    The two hierarchies are paired by identical short joint names and relative
    child paths. Explicit roots make referenced namespaces unambiguous.
    """
    if not cmds:
        raise RuntimeError('该工具必须在 Maya 中运行。')
    if not source_root or not target_root:
        raise RuntimeError('请分别加载源骨骼和目标骨骼。')
    if not (translation or rotation or scale):
        raise RuntimeError('至少选择一个需要匹配的属性。')
    source_root = (cmds.ls(source_root, long=True, type='joint') or [None])[0]
    target_root = (cmds.ls(target_root, long=True, type='joint') or [None])[0]
    if not source_root or not target_root:
        raise RuntimeError('源骨骼或目标骨骼不存在。')
    sources = _relative_joint_map(source_root)
    targets = _relative_joint_map(target_root)
    if not hierarchy:
        sources = {(): source_root}
        targets = {(): target_root}
    matched, warnings = [], []
    for path, source in sources.items():
        target = targets.get(path)
        if not target:
            warnings.append('目标缺少对应层级: %s' % ('/'.join(map(str, path)) or '<root>'))
            continue
        if _short(source) != _short(target):
            warnings.append('名称不一致，跳过: %s → %s' %
                            (display_node(source), display_node(target)))
            continue
        try:
            _match_one(source, target, translation, rotation, scale)
            matched.append((source, target))
        except Exception as exc:
            warnings.append('%s → %s：%s' %
                            (display_node(source), display_node(target), exc))
    return matched, warnings


def undo_chunk(label):
    class _Chunk(object):
        def __enter__(self):
            cmds.undoInfo(openChunk=True, chunkName=label)
            return self
        def __exit__(self, exc_type, exc_value, traceback):
            cmds.undoInfo(closeChunk=True)
    return _Chunk()
