# DRV8701 双电机驱动板

依据原始原理图绘制的 **12 V、48×36 mm、4 层**双电机驱动板，严格保留原图连接与元件值。布局、每段铜线及过孔由人工规划，未使用自动布线或路径搜索。

[下载完整工程 ZIP](downloads/DRV8701_12V_EasyEDA_Pro.zip) · [工程说明](hardware/drv8701-dual-12v/README.md) · [专业版打开方法](hardware/drv8701-dual-12v/EasyEDA_Pro/OPEN_IN_PRO.md)

## 打开工程

下载并解压完整 ZIP，保留文件夹结构。在嘉立创 EDA 专业版 **V4.1+ 离线／半离线桌面客户端**打开：

`EasyEDA_Pro/DRV8701_DUAL_12V.eprj3`

从本仓库克隆时，入口为 `hardware/drv8701-dual-12v/EasyEDA_Pro/DRV8701_DUAL_12V.eprj3`。入口依赖同目录的 `sch/`、`pcb/` 和配置文件，不能单独下载入口文件。符号、封装与器件映射均已内嵌。

## 工程内容

- [嘉立创 EDA 专业版原生工程](hardware/drv8701-dual-12v/EasyEDA_Pro/)
- [可编辑 KiCad 工程及自带库](hardware/drv8701-dual-12v/)
- [原理图 PDF](hardware/drv8701-dual-12v/DRV8701_DUAL_12V_schematic.pdf) 与 [PCB 各层检查图](hardware/drv8701-dual-12v/PCB_layers_review.pdf)
- [元件清单](hardware/drv8701-dual-12v/components.csv) 与 [采购约束](hardware/drv8701-dual-12v/procurement_notes.csv)
- [最终检查记录](hardware/drv8701-dual-12v/validation/final_delivery.json)、[独立工程审查](hardware/drv8701-dual-12v/source/engineering_review.md) 与 [原生转换审计](hardware/drv8701-dual-12v/EasyEDA_Pro/native-final-audit.json)

![PCB 顶层铜与丝印预览](hardware/drv8701-dual-12v/pcb_top.png)

## 检查状态

源板 KiCad DRC 为 **0 违规、0 未连接**；原理图 ERC 为 **0 错误、0 警告**。38 个元件、34 个网络及原生转换后的焊盘、走线、过孔、铜区与源设计已核对。

**尚未在真实嘉立创 EDA 专业版客户端中打开或运行其 DRC，也未进行样板通电和温升测试。** 当前官方字段说明与实际导出模板存在单位口径差异，首次打开须确认尺寸、1.6 mm 板厚、四层各 35 µm 铜及 0.15 mm 最小间距。TPH1R403NL 原厂 PDF 未成功读取，精确型号封装已交叉核对，但电气参数仍需原厂手册复核。

原图的 100 nF 充电泵／内部电源去耦、齐纳供电、IDRIVE 配置和无 GND 的控制接口按用户要求保留；问题及验证步骤见工程说明。本仓库的静态检查结果不代表硬件制造放行。

## 来源与许可证

工程内使用的官方开源转换与校验工具保留各自的 Apache-2.0／MIT 许可证；上游地址与精确版本见 [版本记录](hardware/drv8701-dual-12v/tools/easyeda-native/upstream-versions.json)。这些工具的许可证不自动覆盖整块电路设计、第三方封装或所附厂商 PDF。详细原理图、封装和手册来源见工程说明。
