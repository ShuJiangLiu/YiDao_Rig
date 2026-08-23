# YiDao Rig Maya Module

YiDao Rig 是一个面向 Maya 2022-2026、Python 3 和 PySide2/PySide6 的 Rig 工具模块。

## 正式目录结构

```text
YiDao_Rig/
├── README.md
├── installer/
│   └── install_yidao_rig.py       # 拖拽安装入口
├── module/
│   └── YiDao_Rig.mod              # 模块模板
└── 1.0/
    ├── data/
    │   ├── controller_shapes.json
    │   └── controller_icons/
    ├── plug-ins/
    │   └── YiDao_Rig_plugin.py
    └── scripts/
        └── yidao_rig/
            ├── __init__.py
            ├── launcher.py
            ├── userSetup.py
            ├── core/
            │   ├── __init__.py
            │   ├── controller_ops.py
            │   ├── icon_renderer.py
            │   ├── joint_mirror_ops.py
            │   └── shape_data.py
            ├── ui/
            │   ├── __init__.py
            │   ├── controller_window.py
            │   └── mirror_joints_window.py
            └── tools/
                ├── __init__.py
                ├── controller_tool.py
                └── mirror_joints_tool.py
```

## 支持版本

目标支持版本：

```text
Autodesk Maya 2022
Autodesk Maya 2023
Autodesk Maya 2024
Autodesk Maya 2025
Autodesk Maya 2026
```

Qt 绑定会自动选择：

- Maya 2022-2024：PySide2
- Maya 2025-2026：PySide6（如果当前 Maya 环境提供）

核心 Maya 控制器逻辑使用统一实现，不复制多套代码。正式验证仍需在每个 Maya 版本中执行安装、加载、创建、编辑和卸载测试。

## 安装

1. 启动 Maya 2022、2023、2024、2025 或 2026。
2. 将 [installer/install_yidao_rig.py](installer/install_yidao_rig.py) 拖入 Maya 主窗口或视口。
3. 安装器会把模块安装到：

```text
C:\Users\你的用户名\Documents\maya\modules\YiDao_Rig.mod
C:\Users\你的用户名\Documents\maya\modules\YiDao_Rig\1.0\
```

安装器会自动生成当前电脑对应的 `.mod` 路径，并在升级时保留已有 `1.0/data` 自定义数据。

## 通过 Plug-in Manager 加载

重新启动 Maya 后，打开：

```text
Windows > Settings/Preferences > Plug-in Manager
```

找到：

```text
YiDao_Rig_plugin.py
```

勾选：

```text
Loaded
Auto load
```

加载后，Maya 顶部会出现：

```text
YiDao Rig > Tools > Joint > Mirror Joints
YiDao Rig > Tools > Joint > Joint Match

Joint Match 仅通过骨骼短名称匹配，不再使用 Search / Replace。源、目标骨骼名称应保持一致，通过 UI 的“目标 Namespace”（例如 `charB`）指定目标骨骼链；留空则自动查找，若存在多个候选会警告跳过。
YiDao Rig > Tools > Controller > Controller Tool
YiDao Rig > Tools > Attribute > Attribute Cleanup
YiDao Rig > Tools > Attribute > Attribute Connection
YiDao Rig > Tools > Skin > Skin Weight Import / Export
YiDao Rig > Tools > Skin > Select Weight Joints
YiDao Rig > Tools > Naming > Naming Tool
YiDao Rig > Developer > Reload All YiDao Rig Tools
```

## 完整重载

开发菜单中的：

```text
Developer > Reload All YiDao Rig Tools
```

会执行 YiDao Rig 包级完整重载，而不是只重载 ControllerTool。流程包括：

1. 关闭 YiDao Rig 已打开的 Qt 工具窗口。
2. 自动发现 `yidao_rig` 包下已经导入的所有模块。
3. 按兼容层、核心模块、UI、工具和包入口的依赖顺序重新加载。
4. 图标渲染颜色等共享常量会从核心数据模块重新导入，避免旧模块缓存导致图标预览错误。
5. 重载过程不会自动打开、关闭或重建任何工具窗口，也不会修改 YiDao Rig Maya 菜单。
4. 不自动打开任何工具窗口，用户可以从菜单手动打开需要的工具。

以后新增工具只要放在 `yidao_rig` 包内并被导入，就会自动纳入这个重载流程，不需要再修改 reload 的硬编码模块列表。

旧的脚本入口仍然兼容：

```python
import yidao_rig
yidao_rig.reload_controller_tool()
```

它现在等价于完整重载全部 YiDao Rig 工具。

## 控制器图标界面

ControllerTool 的形状列表现在只显示控制器图标，不显示形状名称。双击任意图标即可创建控制器。

添加自定义形状时不再弹出名称输入框，工具会自动生成内部保存编号；该编号只用于数据管理，不会显示在界面中。保存的自定义形状图标继续使用 Qt 线稿渲染，但投影视角会读取当前 Maya 视口的摄像机方向，因此图标会与当前视口看到的控制器方向一致。

## 控制器左右形状镜像

ControllerTool 的“镜像”按钮会根据当前选中控制器的名称自动寻找另一侧控制器，并将源控制器的曲线形状沿所选轴镜像后复制到目标控制器。

支持以下左右标记：

```text
_l / _r
_L / _R
_l_ / _r_
_L_ / _R_
```

例如选择 `arm_l_ctrl`，工具会寻找 `arm_r_ctrl`。控制器名称和变换不会被修改，只替换目标控制器的曲线形状。如果目标名称不唯一，建议通过不同的上层组区分。

## 镜像关节工具

镜像关节工具保留精确镜像算法，支持：

- XY / YZ / XZ 镜像平面
- Behavior 行为镜像
- Orientation 位置镜像
- Search / Replace 命名替换
- 交换左右命名字符串
- 是否镜像整个层级
- 保持 Maya 本地属性精度，减少矩阵分解造成的浮点误差
- 如果镜像目标骨骼链已存在，不复用原链，而是只给镜像链根骨骼添加 `_001`、`_002` 后缀，子骨骼保持镜像后的原名称
- 属性清理支持普通骨骼旋转烘焙，以及保持连接的单目标 `orientConstraint` / `parentConstraint` 旋转烘焙

也可以通过脚本调用：

```python
import yidao_rig
yidao_rig.show_mirror_joints()
```

## 数据位置

自定义形状和图标位于：

```text
Documents/maya/modules/YiDao_Rig/1.0/data/
```

代码位于 `1.0/scripts`，插件入口位于 `1.0/plug-ins`，资源数据位于 `1.0/data`，三者互不混杂。

## 卸载

1. 在 Plug-in Manager 中取消 `Loaded` 和 `Auto load`。
2. 关闭 Maya。
3. 删除：

```text
Documents/maya/modules/YiDao_Rig.mod
Documents/maya/modules/YiDao_Rig/
```

## 版本升级

后续可以新增：

```text
2.0/
```

并更新 `module/YiDao_Rig.mod` 的版本号和安装器目标版本。当前 `1.0/data` 会作为用户资源目录单独保留。
