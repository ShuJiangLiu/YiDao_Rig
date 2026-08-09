# -*- coding: utf-8 -*-
"""Lossless-oriented skinCluster weight import/export using Maya API 2.0."""
from __future__ import print_function

import json
import os

try:
    import maya.cmds as cmds
    import maya.api.OpenMaya as om2
    import maya.api.OpenMayaAnim as oma2
except ImportError:
    cmds = None
    om2 = oma2 = None


def _selected_meshes():
    meshes = []
    for node in cmds.ls(selection=True, long=True) or []:
        if cmds.nodeType(node) == 'mesh':
            meshes.append(node)
        else:
            meshes.extend(cmds.listRelatives(node, shapes=True, noIntermediate=True,
                                             type='mesh', fullPath=True) or [])
    result = []
    for mesh in meshes:
        if mesh not in result:
            result.append(mesh)
    return result


def _skin_cluster(mesh):
    history = cmds.listHistory(mesh, pruneDagObjects=True) or []
    clusters = [node for node in history if cmds.nodeType(node) == 'skinCluster']
    if not clusters:
        return None
    return clusters[0]


def _dag(mesh):
    selection = om2.MSelectionList()
    selection.add(mesh)
    return selection.getDagPath(0)


def _dependency(node):
    selection = om2.MSelectionList()
    selection.add(node)
    return selection.getDependNode(0)


def _short(node):
    return node.rsplit('|', 1)[-1]


def _weight_strings(values):
    return [repr(float(value)) for value in values]


def _weight_values(values):
    return [float(value) for value in values]


def _skin_data(mesh, cluster):
    skin_fn = oma2.MFnSkinCluster(_dependency(cluster))
    mesh_path = _dag(mesh)
    influences = skin_fn.influenceObjects()
    influence_names = [path.fullPathName() for path in influences]
    components = om2.MFnSingleIndexedComponent()
    component = components.create(om2.MFn.kMeshVertComponent)
    vertex_count = om2.MFnMesh(mesh_path).numVertices
    components.addElements(list(range(vertex_count)))
    weights, influence_count = skin_fn.getWeights(mesh_path, component)
    rows = []
    width = int(influence_count)
    for vertex in range(vertex_count):
        start = vertex * width
        rows.append(_weight_strings(weights[start:start + width]))
    try:
        blend_weights = skin_fn.getBlendWeights(mesh_path, component)
        blend_values = _weight_strings(blend_weights)
    except Exception:
        # Older Maya builds may not expose blend weights consistently.
        blend_values = []
    return {
        'mesh': _short(mesh),
        'meshPath': mesh,
        'skinCluster': cluster,
        'influences': influence_names,
        'influenceShortNames': [_short(name) for name in influence_names],
        'vertexCount': vertex_count,
        'weights': rows,
        'blendWeights': blend_values,
    }


def _safe_file_name(name):
    return ''.join(char if char.isalnum() or char in '._-' else '_' for char in name)


def export_weights(path, meshes=None):
    """Export one standalone JSON file per selected mesh into a folder."""
    if not cmds:
        raise RuntimeError('该工具必须在 Maya 中运行。')
    meshes = meshes or _selected_meshes()
    if not meshes:
        raise RuntimeError('请选择带有 skinCluster 的网格。')
    if not os.path.isdir(path):
        os.makedirs(path)
    written = []
    for mesh in meshes:
        cluster = _skin_cluster(mesh)
        if not cluster:
            raise RuntimeError('网格没有 skinCluster：%s' % mesh)
        record = _skin_data(mesh, cluster)
        base = _safe_file_name(record['mesh']) or 'mesh'
        filename = base + '.json'
        output = {
            'format': 'YiDaoRigSkinWeights',
            'version': 1,
            'precision': 'decimal-string',
            'mesh': record,
        }
        file_path = os.path.join(path, filename)
        with open(file_path, 'w') as stream:
            json.dump(output, stream, indent=2, ensure_ascii=False)
        written.append(file_path)
    return written


def _resolve_mesh(record):
    path = record.get('meshPath')
    if path and cmds.objExists(path) and cmds.nodeType(path) == 'mesh':
        return path
    matches = cmds.ls(record.get('mesh', ''), type='mesh', long=True) or []
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError('找不到目标网格：%s' % record.get('mesh'))
    raise RuntimeError('目标网格名称不唯一：%s' % record.get('mesh'))


def _scene_joint_candidates(name):
    """Resolve a stored influence by full path first, then unique short name."""
    if cmds.objExists(name) and cmds.nodeType(name) == 'joint':
        return [cmds.ls(name, long=True)[0]]
    return cmds.ls(_short(name), type='joint', long=True) or []


def _cluster_influences(cluster):
    """Query influences and normalize them to long DAG paths."""
    if not cluster:
        return []
    names = cmds.skinCluster(cluster, query=True, influence=True) or []
    result = []
    for name in names:
        long_names = cmds.ls(name, long=True, type='joint') or []
        result.append(long_names[0] if len(long_names) == 1 else name)
    return result


def _resolve_influences(names, cluster=None):
    existing = _cluster_influences(cluster)
    result = []
    missing = []
    for name in names:
        exact = [item for item in existing if item == name]
        candidates = exact or [item for item in existing if _short(item) == _short(name)]
        if not candidates:
            candidates = _scene_joint_candidates(name)
        if len(candidates) == 1:
            result.append(candidates[0])
        elif not candidates:
            missing.append(name)
        else:
            raise RuntimeError('影响骨骼名称不唯一：%s（候选：%s）' %
                               (name, ', '.join(candidates)))
    if missing:
        raise RuntimeError('场景中找不到影响骨骼：%s' % ', '.join(missing))
    return result


def _ensure_skin_cluster(mesh, stored_names):
    cluster = _skin_cluster(mesh)
    if cluster:
        return cluster, _resolve_influences(stored_names, cluster)
    influences = _resolve_influences(stored_names)
    if not influences:
        raise RuntimeError('权重文件没有影响骨骼：%s' % mesh)
    # Create a normally normalized skinCluster, then overwrite all vertex
    # weights with the exact values from the file through setWeights.
    # Let Maya assign the default skinCluster name. Never rename existing or
    # newly-created history nodes as part of weight import.
    cluster = cmds.skinCluster(influences, mesh,
                               bindMethod=0, skinMethod=0, normalizeWeights=1,
                               toSelectedBones=True)[0]
    return cluster, influences


def _set_skin_data(record):
    mesh = _resolve_mesh(record)
    vertex_count = om2.MFnMesh(_dag(mesh)).numVertices
    if vertex_count != int(record['vertexCount']):
        raise RuntimeError('顶点数量不一致：%s（文件 %s，场景 %s）' %
                           (mesh, record['vertexCount'], vertex_count))
    stored_names = record['influences']
    cluster, target_influences = _ensure_skin_cluster(mesh, stored_names)
    skin_fn = oma2.MFnSkinCluster(_dependency(cluster))
    all_existing = _cluster_influences(cluster)
    indices = om2.MIntArray([all_existing.index(name) for name in target_influences])
    components_fn = om2.MFnSingleIndexedComponent()
    component = components_fn.create(om2.MFn.kMeshVertComponent)
    components_fn.addElements(list(range(vertex_count)))
    values = []
    for row in record['weights']:
        if len(row) != len(stored_names):
            raise RuntimeError('权重列数不一致：%s' % mesh)
        values.extend(_weight_values(row))
    skin_fn.setWeights(_dag(mesh), component, indices, om2.MDoubleArray(values), False)
    blend_weights = record.get('blendWeights') or []
    if blend_weights:
        if len(blend_weights) != vertex_count:
            raise RuntimeError('blendWeights 数量不一致：%s' % mesh)
        skin_fn.setBlendWeights(_dag(mesh), component,
                                om2.MDoubleArray(_weight_values(blend_weights)))
    return mesh


def _read_weight_records(path):
    files = []
    if os.path.isfile(path):
        files = [path]
    elif os.path.isdir(path):
        files = [os.path.join(path, name) for name in os.listdir(path)
                 if name.lower().endswith('.json')]
    else:
        raise RuntimeError('权重文件或文件夹不存在：%s' % path)
    records = []
    for file_path in sorted(files):
        with open(file_path, 'r') as stream:
            payload = json.load(stream)
        if payload.get('format') != 'YiDaoRigSkinWeights':
            continue
        if 'mesh' in payload:
            records.append(payload['mesh'])
        else:
            records.extend(payload.get('meshes', []))
    if not records:
        raise RuntimeError('没有找到有效的 YiDao Rig 权重 JSON 文件。')
    return records


def import_weights(path, meshes=None):
    if not cmds:
        raise RuntimeError('该工具必须在 Maya 中运行。')
    records = _read_weight_records(path)
    if meshes:
        selected = meshes
        selected_by_name = {}
        for mesh in selected:
            selected_by_name.setdefault(_short(mesh), []).append(mesh)
        records_by_name = {}
        for record in records:
            records_by_name.setdefault(record.get('mesh', ''), []).append(record)
        selected_records = []
        for mesh in selected:
            name = _short(mesh)
            matches = records_by_name.get(name, [])
            if len(matches) != 1:
                raise RuntimeError('选择的网格在权重文件中无法唯一匹配：%s' % mesh)
            record = dict(matches[0])
            record['meshPath'] = mesh
            selected_records.append(record)
        records = selected_records
    changed = []
    for record in records:
        changed.append(_set_skin_data(record))
    return changed


def undo_chunk(label):
    class _Chunk(object):
        def __enter__(self):
            cmds.undoInfo(openChunk=True, chunkName=label)
            return self
        def __exit__(self, exc_type, exc_value, traceback):
            cmds.undoInfo(closeChunk=True)
    return _Chunk()
