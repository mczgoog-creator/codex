# DRV8701 双电机驱动板 · Rev B

**12 V、39×60 mm、4 层、1.6 mm** 双电机驱动板。Rev B 重新安排了两路半桥、去耦和功率回路，并加入 TPS25910 主电源控制。每段线路、过孔和铜区均按明确坐标人工规划，未使用自动布线或路径搜索。

[网页端 KiCad 导入包](downloads/DRV8701_12V_KiCad5_Import.zip) · [完整工程和资料 ZIP](downloads/DRV8701_12V_EasyEDA_Pro.zip) · [工程说明](hardware/drv8701-dual-12v/README.md)

## 在嘉立创 EDA 专业版中打开

网页端请下载 **`DRV8701_12V_KiCad5_Import.zip`**，在开始页选择 **「导入 KiCad」**，直接选择 ZIP。按[官网指引](https://prodocs.lceda.cn/cn/import-export/import-kicad/index.html)，导入副本采用真实 KiCad 5.1 格式，并通过 KiCad 自带归档功能打包。步骤和导入后检查见[网页导入说明](hardware/drv8701-dual-12v/IMPORT_IN_WEB_PRO.md)。

原始 KiCad 9 工程和自带库也随包保存。`EasyEDA_Pro/DRV8701_DUAL_12V.eprj3` 是另供 V4.1+ 离线／半离线桌面客户端使用的文件夹工程；需保留整个目录，不能当作网页 `.epro` 文件导入。

## 本版变化

- 四组高边源极与低边漏极相邻，通过局部宽铜连接相节点；功率转层采用四孔阵列。公共供电在 C15 正极处汇合并向两路分配。
- 泵和内部电源去耦至芯片的关键连接留在顶层；VM 先到 C3/C10，再到芯片 VM 脚。SH 源参考采用独立细线返回高边源极焊盘。
- 新增 U6 TPS25910、SW1 和五个配套无源件。SW1 控制主电源，原 U5 继续控制 DRV8701 的 nSLEEP。原 38 个元件的取值保留；原有脚网络仅 P2.1 从 VM 改为新增电源入口 VM_RAW。

主电源连续额定 5 A，R12=40.2 kΩ 对应手册限流 4.5–5.5 A。主开关关闭时芯片仍消耗约 2.5 mA 典型／4 mA 最大，分压另约 90 µA；不提供电池物理隔离或反向电流阻断。开启主电源前应保持两路桥关闭，VM 稳定后再使能，详见[首次上电步骤](hardware/drv8701-dual-12v/FIRST_POWER_ON.md)。

![Rev B PCB 顶层预览](hardware/drv8701-dual-12v/pcb_top.png)

## 文件与检查边界

- [原理图 PDF](hardware/drv8701-dual-12v/DRV8701_DUAL_12V_schematic.pdf)、[PCB 各层检查图](hardware/drv8701-dual-12v/PCB_layers_review.pdf)
- [元件清单](hardware/drv8701-dual-12v/components.csv)、[采购约束](hardware/drv8701-dual-12v/procurement_notes.csv)
- [布局与电流路径说明](hardware/drv8701-dual-12v/source/engineering_review.md)、[主电源手册核对](hardware/drv8701-dual-12v/source/tps25910_power_control_review.md)
- [原图保留范围核对](hardware/drv8701-dual-12v/validation/rev_b_original_source_contract.json)、[交付检查记录](hardware/drv8701-dual-12v/validation/final_delivery.json)
- [独立布局几何检查](hardware/drv8701-dual-12v/validation/layout_geometry_audit.json)、[最后丝印与铜线复核](hardware/drv8701-dual-12v/validation/rev_b_final_silk_cleanup.json)、[Rev B 工程审计](hardware/drv8701-dual-12v/validation/rev_b_engineering_audit.json)

Rev B 共 **45 个元件、38 个网络、203 个唯一物理引脚／211 个焊盘实例、592 段线路、151 个过孔、12 个铜区**。冻结后的 KiCad 9 源板 **DRC 0 违规／0 未连接，原理图 ERC 0 错误／0 警告**。独立几何检查通过：14 条关键去耦连接均在顶层，最长 2.9713 mm；丝印与焊盘／过孔碰撞为 0，审核范围内的直角／锐角弯折为 0。

网页导入副本已通过真实 **KiCad 5.1.9：ERC 0 错误／0 警告，PCB DRC 0 错误／0 未连接**；45 个元件、38 网、203 脚逐值逐脚一致。PCB 检查已重填全部铜区并检查走线与填铜。副本的 624 段线路中，新增 32 段完全位于原 MOS 漏极焊盘铜内，新增实际铜面积为 0；原 592 段线路、151 孔、211 焊盘及 12 铜区保留。见[旧版最终等价核对](hardware/drv8701-dual-12v/validation/legacy5_final_pcb_equivalence.json)。

源软件检查不替代专业版实际导入检查。弯折统计排除同网焊盘／过孔内部和真实分支结点，具体范围见几何报告。五页 PCB 检查图、分层 PDF 及顶／底 SVG／PNG 均按冻结源板重新导出，来源 SHA 见[预览导出记录](hardware/drv8701-dual-12v/validation/preview_exports.json)。

桌面原生工程的[静态转换审计](hardware/drv8701-dual-12v/EasyEDA_Pro/native-final-audit.json) 已通过：元件／引脚／线路／过孔及 12 个填充铜区均与冻结源板对应，官方工程结构检查 0 错误／0 警告。未运行真实专业版桌面客户端，网页用户仍使用上面的 KiCad 导入 ZIP。

**真实嘉立创网页导入／DRC、样板通电和温升测试尚未完成。** 导入会重新铺铜，需复核四层各 35 µm 铜、功率铜区和规则。原图的 100 nF 电荷泵／内部电源去耦、较弱齐纳供电、IDRIVE 设置和无 GND 的控制插座仍保留，并在工程说明中列出。MOS 原厂手册已读取，采购需匹配普通 SOP Advance 封装；手册没有提供推荐 PCB 焊盘图。

## 来源与许可证

官方开源转换／校验工具保留各自的 Apache-2.0／MIT 许可证；上游地址与精确版本见[版本记录](hardware/drv8701-dual-12v/tools/easyeda-native/upstream-versions.json)。这些工具许可证不自动覆盖电路设计、第三方封装或厂商 PDF。原图、封装和手册来源见工程说明。
