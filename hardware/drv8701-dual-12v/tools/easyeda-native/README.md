# 原生工程生成与审计工具

Node.js 18+。最终工程已生成时，不需要运行这些工具即可用专业版打开工程。

这些脚本使用嘉立创／EasyEDA 官方 KiCad→`.eprj3` 转换器，再做有记录的字段纠正。所有 PCB 走线、过孔、铺铜都来自已完成的源板；脚本不调用自动布线，也不寻找连线路径。

准备字段验证器的依赖：在本目录运行 `npm ci --ignore-scripts`。实际转换器无 npm 依赖。然后运行：

```sh
bash run-native-conversion.sh /path/to/drv8701_board /path/to/new-native-output
```

输出目录必须是新的。源文件包含 `DRV8701_DUAL_12V.kicad_sch` 与 `DRV8701_DUAL_12V.kicad_pcb`；逐物理脚独立网表默认读取 `validation/expected_physical_pin_nets.json`。脚本检查失败会以非零状态停止。

工程必须保留完整目录。解压后，在专业版 V4.1+ 离线／半离线桌面客户端打开 `DRV8701_DUAL_12V.eprj3`，不要单独移动索引文件。实际客户端 CLI 验证需要 V4.1.60+。

验证层次：

- `native-format-validation.json`：外层记录与当前官方字段 schema；真实导出与最新 schema 的已知差异单列，未修改 schema。
- `native-net-equivalence.json`：原生原理图逐脚网络与独立源表一致性。
- `native-pcb-equivalence.json`：原生 PCB 逐脚网络、所有直线走线端点／宽度／层别、过孔几何、铺铜边界和已填多边形与 KiCad 源一致性。
- 该 PCB 报告还独立比较全部181个焊盘的尺寸、世界坐标、角度、圆角、圆孔／长槽、镀孔状态及铜层，并比较13个物理层的厚度。
- 焊盘阻焊／锡膏扩展按源板保存并逐项检查，不沿用官方转换器默认2mil阻焊扩展。
- `native-library-link-equivalence.json`：38个组件的原理图／PCB共用器件、符号、封装、Unique ID；所需库均内嵌。
- `native-conversion-evidence.json`：旋转纠正与焊盘世界坐标逐个验算。
- `native-design-rules.json`：0.15 mm 最小铜间距／线宽、0.20 mm 最小孔径、0.10 mm 环宽、0.45/0.20 mm 默认过孔，以及 VM／电机输出／栅极／信号默认线宽。

文件格式审计不等同于实际客户端打开或其 DRC。本云环境没有安装嘉立创专业版桌面客户端，实际打开与 DRC 尚未运行。叠层 thickness 和 RULE 长度的最新官方字段说明与官方 V4.1.36 真实导出模板单位口径存在差异；生成文件采用与真实导出模板一致的 PCB mil 编码。请在客户端确认 1.6 mm／四层／每层35 µm铜，以及上述规则显示值。详见 `RESEARCH.md`。

官方工具来源与锁定版本记录在 `upstream-versions.json`，对应许可证保留在各供应目录。上游源代码没有修改；本目录顶层脚本是独立后处理和审计代码。
