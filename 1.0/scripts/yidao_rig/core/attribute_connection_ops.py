# -*- coding: utf-8 -*-
"""Record, disconnect and rebuild transform attribute connections."""
from __future__ import print_function

try:
    import maya.cmds as cmds
except ImportError:
    cmds = None

from ..compat.maya_compat import display_node, display_plug


TRANSFORM_ATTRS = ('translate', 'rotate', 'scale')
_TRANSFORM_PLUGS = tuple(
    attr for group in (('translate', 'translateX', 'translateY', 'translateZ'),
                       ('rotate', 'rotateX', 'rotateY', 'rotateZ'),
                       ('scale', 'scaleX', 'scaleY', 'scaleZ'))
    for attr in group)
_STATE = {}
_CONSTRAINT_TYPES = ('parentConstraint', 'pointConstraint',
                     'orientConstraint', 'scaleConstraint')


def _matrix(node):
    return tuple(float(value) for value in
                 (cmds.xform(node, query=True, worldSpace=True, matrix=True) or []))


def _selected(targets=None):
    targets = targets or cmds.ls(selection=True, long=True, type='transform') or []
    if not targets:
        raise RuntimeError('请先选择需要处理的骨骼或控制器。')
    return list(dict.fromkeys(targets))


def _connection_kind(source):
    source_node = source.split('.', 1)[0]
    if not cmds.objExists(source_node):
        return 'unknown'
    node_type = cmds.nodeType(source_node) or ''
    if node_type in ('parentConstraint', 'pointConstraint', 'orientConstraint',
                     'scaleConstraint', 'aimConstraint',
                     'poleVectorConstraint', 'geometryConstraint',
                     'normalConstraint', 'tangentConstraint'):
        return 'constraint'
    if node_type.startswith('animCurve'):
        return 'setDrivenKey'
    return 'direct'


def _flatten_numbers(value):
    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            result.extend(_flatten_numbers(item))
        return result
    try:
        return [float(value)]
    except (TypeError, ValueError):
        return []


def _has_constraint_offset(node, constraint_type, target_count):
    """Infer the original -maintainOffset choice from saved offset values.

    Maya does not store a persistent maintainOffset boolean. It stores the
    resulting offsets, so a zero offset is inherently indistinguishable from
    a constraint created with maintainOffset=False.
    """
    attrs = {
        'parentConstraint': ('targetOffsetTranslate', 'targetOffsetRotate',
                             'offsetTranslate', 'offsetRotate'),
        'pointConstraint': ('targetOffsetTranslate', 'offset'),
        'orientConstraint': ('targetOffsetRotate', 'offset'),
        'scaleConstraint': ('targetOffsetScale', 'offset'),
    }.get(constraint_type, ())
    for attr in attrs:
        if attr.startswith('targetOffset'):
            for index in range(max(1, int(target_count))):
                plug = '%s.target[%d].%s' % (node, index, attr)
                if not cmds.objExists(plug):
                    continue
                values = _flatten_numbers(cmds.getAttr(plug))
                if any(abs(value) > 1.0e-8 for value in values):
                    return True
        else:
            plug = node + '.' + attr
            if not cmds.objExists(plug):
                continue
            values = _flatten_numbers(cmds.getAttr(plug))
            defaults = (1.0, 1.0, 1.0) if attr == 'offsetScale' else (0.0,)
            if any(abs(value - defaults[index % len(defaults)]) > 1.0e-8
                   for index, value in enumerate(values)):
                return True
    return False


def _constraint_snapshot(node, driven, connections):
    constraint_type = cmds.nodeType(node)
    if constraint_type not in _CONSTRAINT_TYPES:
        return None
    command = getattr(cmds, constraint_type)
    targets = command(node, query=True, targetList=True) or []
    aliases = command(node, query=True, weightAliasList=True) or []
    weights = []
    for alias in aliases:
        try:
            weights.append(float(cmds.getAttr(node + '.' + alias)))
        except Exception:
            weights.append(1.0)
    driven_plugs = set(destination.rsplit('.', 1)[-1]
                       for source, destination in connections
                       if source.split('.', 1)[0] == node)
    translate_axes = ('X', 'Y', 'Z')
    skip_translate = tuple(axis.lower() for axis in translate_axes
                           if 'translate' + axis not in driven_plugs)
    skip_rotate = tuple(axis.lower() for axis in translate_axes
                        if 'rotate' + axis not in driven_plugs)
    return {
        'node': node,
        'type': constraint_type,
        'targets': targets,
        'weights': weights,
        # The requested reconnect policy is always maintainOffset=True.
        'maintain_offset': True,
        'skip_translate': skip_translate,
        'skip_rotate': skip_rotate,
        'driven_plugs': tuple(driven_plugs),
    }


def _rebuild_constraint(data, driven):
    constraint_type = data['type']
    command = getattr(cmds, constraint_type)
    if not data['targets']:
        raise RuntimeError('%s 没有可用目标' % data['node'])
    kwargs = {
        'maintainOffset': bool(data['maintain_offset']),
        'name': data['node'],
    }
    if constraint_type in ('parentConstraint', 'pointConstraint'):
        kwargs['skipTranslate'] = data['skip_translate']
    if constraint_type in ('parentConstraint', 'orientConstraint'):
        kwargs['skipRotate'] = data['skip_rotate']
    if constraint_type == 'scaleConstraint':
        kwargs['skip'] = tuple(axis for axis in ('x', 'y', 'z')
                               if 'scale' + axis.upper() not in
                               set(data['driven_plugs']))
    result = command(*(list(data['targets']) + [driven]), **kwargs)
    new_node = result[0] if isinstance(result, (list, tuple)) else result
    aliases = command(new_node, query=True, weightAliasList=True) or []
    for alias, weight in zip(aliases, data['weights']):
        try:
            cmds.setAttr(new_node + '.' + alias, weight)
        except Exception:
            pass
    return new_node


def scan_connections(targets=None):
    """Return incoming transform connections grouped by selected node."""
    if not cmds:
        raise RuntimeError('该工具必须在 Maya 中运行。')
    result = {}
    for node in _selected(targets):
        if not cmds.objExists(node):
            continue
        connections = []
        # Query each destination plug independently. This is more reliable
        # than parsing listConnections(connections=True) for constraints,
        # because parentConstraint commonly drives the individual XYZ plugs.
        for attr in _TRANSFORM_PLUGS:
            destination = node + '.' + attr
            sources = cmds.listConnections(
                destination, source=True, destination=False, plugs=True) or []
            for source in sources:
                connections.append((source, destination))
        if connections:
            result[node] = list(dict.fromkeys(connections))
    return result


def disconnect_selected(targets=None):
    """Record all incoming transform connections and disconnect them.

    Only the destination connections are changed. Constraint nodes and their
    Maintain Offset data are deliberately left intact.
    """
    if not cmds:
        raise RuntimeError('该工具必须在 Maya 中运行。')
    selected = _selected(targets)
    scanned = scan_connections(selected)
    if not scanned:
        raise RuntimeError('所选对象的 Translate / Rotate / Scale 没有输入连接。')
    state = {}
    constraint_nodes = {}
    for node, connections in scanned.items():
        constraints = {}
        for source, _destination in connections:
            source_node = source.split('.', 1)[0]
            if _connection_kind(source) == 'constraint' and source_node not in constraints:
                snapshot = _constraint_snapshot(source_node, node, connections)
                if snapshot:
                    constraints[source_node] = snapshot
                    constraint_nodes[source_node] = snapshot
        state[node] = {
            'connections': connections,
            'world_matrix': _matrix(node),
            'constraints': constraints,
        }
        for source, destination in connections:
            if cmds.isConnected(source, destination):
                cmds.disconnectAttr(source, destination)
        # Disconnecting normally retains the evaluated value. Explicitly restore
        # the matrix as a safeguard for compound/child plug combinations.
        try:
            cmds.xform(node, worldSpace=True, matrix=state[node]['world_matrix'])
        except Exception:
            pass
    # Delete constraints only after all selected destination connections have
    # been recorded and disconnected. Rebuild happens later on reconnect.
    for constraint_node in constraint_nodes:
        if cmds.objExists(constraint_node):
            cmds.delete(constraint_node)
    _STATE.clear()
    _STATE.update(state)
    return state


def reconnect_saved():
    """Rebuild saved constraints with maintainOffset and restore connections."""
    if not cmds:
        raise RuntimeError('该工具必须在 Maya 中运行。')
    if not _STATE:
        raise RuntimeError('没有可重连的连接记录，请先执行“一键断开”。')
    restored, warnings = [], []
    rebuilt = {}
    for node, data in list(_STATE.items()):
        if not cmds.objExists(node):
            warnings.append('%s：对象不存在' % display_node(node))
            continue
        for old_name, constraint in data.get('constraints', {}).items():
            if old_name not in rebuilt:
                try:
                    rebuilt[old_name] = _rebuild_constraint(constraint, node)
                except Exception as exc:
                    warnings.append('%s：约束重建失败：%s' %
                                    (display_node(old_name), exc))
                    rebuilt[old_name] = None

        expected = []
        for source, destination in data['connections']:
            source_node, source_attr = source.split('.', 1)
            if source_node in data.get('constraints', {}):
                new_node = rebuilt.get(source_node)
                if new_node:
                    expected.append((new_node + '.' + source_attr, destination))
                continue
            if not cmds.objExists(source_node):
                warnings.append('%s：源属性不存在' % display_plug(source))
                continue
            expected.append((source, destination))
            if not cmds.isConnected(source, destination):
                try:
                    cmds.connectAttr(source, destination, force=True)
                except Exception as exc:
                    warnings.append('%s -> %s：%s' %
                                    (display_plug(source), display_plug(destination), exc))
        missing = [(source, destination) for source, destination in expected
                   if not cmds.isConnected(source, destination)]
        if missing:
            warnings.append('%s：有 %d 条连接未能恢复' %
                            (display_node(node), len(missing)))
        else:
            restored.append(node)
    if not warnings:
        _STATE.clear()
    return restored, warnings


def saved_connection_count():
    return sum(len(data['connections']) for data in _STATE.values())


def saved_connection_summary():
    summary = {'constraint': 0, 'setDrivenKey': 0, 'direct': 0,
               'unknown': 0}
    for data in _STATE.values():
        for source, _destination in data['connections']:
            summary[_connection_kind(source)] += 1
    return summary


def undo_chunk(label):
    class _Chunk(object):
        def __enter__(self):
            cmds.undoInfo(openChunk=True, chunkName=label)
            return self
        def __exit__(self, exc_type, exc_value, traceback):
            cmds.undoInfo(closeChunk=True)
    return _Chunk()
