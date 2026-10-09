# KiCad 5.1 原理图导入兼容文件

本目录的 `.sch`、`.lib` 与 `.pro` 是真正的 KiCad 5.1 格式转换结果，原设计的连接、元件值、符号图形、引脚编号及排布均保留。没有通过仅更改现代文件版本头伪装成旧格式。旧版 PCB 与封装的验证记录由对应转换步骤另行保存。

|文件|真实格式|
|---|---|
|`DRV8701_DUAL_12V.sch`|`EESchema Schematic File Version 4`，KiCad 5.1 使用的 legacy 原理图；坐标为 mil|
|`DRV8701_Custom.lib`|`EESchema-LIBRARY Version 2.4`，含 11 个符号定义|
|`DRV8701_Custom.dcm`|`EESchema-DOCLIB Version 2.0`，符号说明|
|`DRV8701_DUAL_12V-cache.lib`|同格式缓存，符号名称按旧版缓存约定添加库名前缀|
|`DRV8701_DUAL_12V.pro`|KiCad 5 的 INI 工程配置，而不是 KiCad 9 的 JSON|
|`sym-lib-table`|`Legacy` 插件与 `${KIPRJMOD}/DRV8701_Custom.lib` 项目内路径|
|`fp-lib-table`|`KiCad` 封装插件与项目内 `.pretty` 路径|

`U` 行的 timestamp 使用源 KiCad 9 实例 UUID 的前 8 个十六进制字符，转为大写；38 个值已核对互不重复。对应 PCB 元件路径应为 `/` 加该 timestamp，映射见 `validation/component_timestamp_map.json`。

符号的 `DEF/DRAW/X` 表达由源图形逐项转换，使用真实旧版矩形、折线与引脚语法。所有引脚电气类型、端点坐标、方向、长度与编号均保留，未关闭 ERC。173 个实例物理脚包括 166 个连接脚和 7 个 NC；其中八只 MOS 的源极三个脚及漏极四个脚均分别保留。

## 重建与检查

在上一级工程根目录运行：

```bash
python tools/import-kicad/generate_legacy_schematic.py --no-validate
```

从真正加载了本目录 `.sch/.lib` 的 Eeschema 5.1 导出 XML 或 KiCad S-expression 网表后，运行：

```bash
python tools/import-kicad/generate_legacy_schematic.py --legacy-netlist /path/to/DRV8701_DUAL_12V.net
```

检查包含 38 个元件值、34 个命名网络、173 个物理脚的连接或 NC，以及 38 个 timestamp；不以“进程成功退出”替代内容检查。若默认直接使用 KiCad 9 CLI 读取旧版 `.sch`，它的 headless 流程可能没有加载外部 legacy 符号库，生成空网表。重建脚本会对这种结果报错，不能当作检查通过。

`validation/legacy_library_roundtrip.json` 记录由官方 KiCad legacy 库解析器通过 `kicad-cli sym upgrade` 读回的比较结果；该检查可以独立验证 11 个定义、54 个定义脚的名字、编号、电气类型、端点、方向与长度，但不能替代实际 KiCad 5.1 打开和整个原理图的网表检查。实际旧版 Eeschema 打开、网表与 ERC 结果另见最终检查记录。

本次实际 Eeschema **5.1.9+dfsg1-1+deb11u1** 已加载全部自定义符号并导出 `.net`。逐项检查通过：38 个元件及原值、34 个命名网络、173 个物理脚（166 连接脚、7 NC）及 38 个 timestamp。实际输出保存为 `DRV8701_DUAL_12V.net` 与 `validation/eeschema_exported.net`，核对报告为 `validation/legacy_net_equivalence.json`。该旧版本把 NC 导出为 `Net-(U1-Pad9)` 等自动名；检查要求对应网络只含那个单独 NC 脚，不把它计入源图的 34 个真实网络。

同一个真实 5.1.9 Eeschema 已运行 ERC：**0 个错误、0 个警告、0 条消息**，报告为 `validation/eeschema5_actual_erc.erc`，界面结果见 `validation/eeschema5_actual_erc.png`。截图中的“未找到默认编辑器”提示发生在尝试自动打开已经生成的报告时，与 ERC 结果无关。

## 格式依据与边界

- 嘉立创 EDA 专业版官方 KiCad 导入指南：<https://prodocs.lceda.cn/cn/import-export/import-kicad/index.html>，列明 KiCad 5.1 / 5.9 导入版本。
- KiCad 5.1 官方实现：<https://github.com/KiCad/kicad-source-mirror/blob/5.1/eeschema/sch_legacy_plugin.cpp>，其中 `loadSymbol`、`LoadPart`、`LoadPin` 与相关保存函数定义 `.sch/.lib` 实际语法。
- KiCad 9 官方 legacy 解析器：<https://github.com/KiCad/kicad-source-mirror/blob/9.0/eeschema/sch_io/kicad_legacy/sch_io_kicad_legacy.cpp> 与 `sch_io_kicad_legacy_lib_cache.cpp`；用作旧库读回检查，未拿它替代旧版本实际打开。
- INI 项目字段同时参照了 Tinkerforge 2020 年的 KiCad 5 项目 `performance-dc.pro`；只使用相应旧版字段。旧版不能表示的现代制造规则不在 `.pro` 中虚构字段，PCB 导入后应重新检查嘉立创环境的制造规则。

实际 5.1.9 打开时确认：KiCad 5 已通过 `sym-lib-table` 管理符号库，因此 `.pro` 中不放更早版本的 `[eeschema/libraries] LibName1=...` 库列表，避免产生“旧库列表不再支持”的加载警告。库定位由本目录的正规项目库表负责。

尚不能由格式转换证明的事项包括嘉立创实际客户端导入效果、真实板厂叠层和制造公差、器件实物尺寸，以及原图已记录的电气风险。原设计说明仍然适用；转换没有改变那些连接与取值。
