# 原生工程生成与审计工具

Node.js 18+。最终工程已生成时，不需要运行这些工具即可用专业版打开工程。

这些脚本使用嘉立创／EasyEDA 官方 KiCad→`.eprj3` 转换器，再做有记录的字段纠正。所有 PCB 走线、过孔、铺铜都来自已完成的源板；脚本不调用自动布线，也不寻找连线路径。

准备字段验证器的依赖：在本目录运行 `npm ci --ignore-scripts`。实际转换器无 npm 依赖。然后运行：

```sh
bash run-native-conversion.sh /path/to/drv8701-dual-12v /path/to/new-native-output
```

输出目录必须是新的。源文件包含 `DRV8701_DUAL_12V.kicad_sch` 与 `DRV8701_DUAL_12V.kicad_pcb`；逐物理脚独立网表默认读取 `validation/expected_physical_pin_nets.json`，器件位号和值读取 `design_netlist.json`。所有数量均从本次源设计计算，适用于新增主电源控制的 Rev B。脚本检查失败会以非零状态停止。

工程必须保留完整目录。这份 `.eprj3` 是可选桌面交付：解压后，在支持该目录格式的专业版 V4.1+ 离线／半离线桌面客户端打开 `DRV8701_DUAL_12V.eprj3`，不要单独移动索引文件。网页端使用主交付 KiCad 5 ZIP 和官方“导入 KiCad”入口，不能把 `.eprj3` 放入 `.epro` 文件选择器。实际客户端 CLI 验证需要 V4.1.60+。

验证层次：

- `native-format-validation.json`：外层记录与当前官方字段 schema；真实导出与最新 schema 的已知差异单列，未修改 schema。
- `native-net-equivalence.json`：原生原理图逐脚网络与独立源表一致性。
- `native-pcb-equivalence.json`：原生 PCB 逐脚网络、所有直线走线端点／宽度／层别、过孔几何、铺铜边界和已填多边形与 KiCad 源一致性；逐区比较 priority→POUR.order、直连／热焊模式、间距、热焊间隙／桥宽、最小细度和孤岛模式。
- 该 PCB 报告还独立比较本次源板全部焊盘的尺寸、世界坐标、角度、圆角、圆孔／长槽、镀孔状态及铜层，并比较物理叠层厚度。
- 焊盘阻焊／锡膏扩展按源板保存并逐项检查，不沿用官方转换器默认2mil阻焊扩展。
- `native-library-link-equivalence.json`：本次全部组件的原理图／PCB共用器件、符号、封装、Unique ID；所需库均内嵌。
- `native-final-audit.json`：动态核验全部位号、原理图与PCB器件值、物理脚与命名网数量，并绑定本次源文件 SHA-256。PCB器件值保存为独立 Name 属性，避免共用同一符号／封装的不同阻容值丢失。
- `native-conversion-evidence.json`：旋转纠正与焊盘世界坐标逐个验算。
- `native-design-rules.json`：0.15 mm 最小铜间距／线宽、0.20 mm 最小孔径、0.10 mm 环宽、0.45/0.20 mm 默认过孔，以及 VM/VM_RAW／电机输出／栅极／信号默认线宽。

文件格式审计不等同于实际客户端打开或其 DRC。本云环境没有安装嘉立创专业版桌面客户端，实际打开与 DRC 尚未运行。叠层 thickness 和 RULE 长度的最新官方字段说明与官方 V4.1.36 真实导出模板单位口径存在差异；生成文件采用与真实导出模板一致的 PCB mil 编码。请在客户端确认 1.6 mm／四层／每层35 µm铜，以及上述规则显示值。详见 `RESEARCH.md`。

Rev B 所有区域采用统一的 0.15 mm 间距和直接焊盘连接，适配脚本用官方默认 COPPER 规则保存该连接模式；thermal_gap=0.25 mm、thermal_bridge_width=0.5 mm 同时保留，但在直连模式下不生效。全部区域移除所有无连接孤岛，面积阈值因此不生效。源区参数若不一致、使用面积阈值移除孤岛或未支持的网格填充，脚本会明确拒绝。POUR.width 保留官方转换器说明的真实导出 mm 特例，SOLID fineness 与热焊长度采用 PCB mil；这些显示和重新铺铜行为仍需实际桌面客户端核验。

官方工具来源与锁定版本记录在 `upstream-versions.json`，对应许可证保留在各供应目录。上游源代码没有修改；本目录顶层脚本是独立后处理和审计代码。
