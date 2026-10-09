# 嘉立创 EDA 专业版网页端导入 · Rev B

使用用户提供的[官方 KiCad 导入指引](https://prodocs.lceda.cn/cn/import-export/import-kicad/index.html)。该页面列出 KiCad 5.1／5.9 支持范围，要求使用 KiCad 自带归档功能打包，并说明导入后重新铺铜。

## 下载与操作

使用 **`DRV8701_12V_KiCad5_Import.zip`**：

- [从 GitHub 下载网页导入 ZIP](https://github.com/mczgoog-creator/codex/raw/refs/heads/main/downloads/DRV8701_12V_KiCad5_Import.zip)
- 完整工程包中也有同一文件：`imports/DRV8701_12V_KiCad5_Import.zip`。

ZIP 内为 KiCad 5.1 的 `.pro`、`.sch`、`.lib`、`.kicad_pcb`，包含缓存库、本地符号及封装库；保留完整 ZIP 直接导入。

1. 在嘉立创 EDA 专业版**开始页**选择 **「导入 KiCad」**。若文件选择器仅允许 `.epro`，返回开始页改选 KiCad 导入入口。
2. 选择 `DRV8701_12V_KiCad5_Import.zip`。不改后缀，不将 ZIP 中的单个文件取出再导入。
3. 打开导入后的原理图和 PCB，核对以下数据、重新铺铜并运行专业版 DRC。
4. 保存工程；需要专业版原生备份时，由专业版自身的工程导出功能生成。

`.eprj3` 是另供新版桌面客户端使用的文件夹工程，不是当前网页 `.epro` 选择器要求的文件。网页端优先使用上述 KiCad ZIP。

## 导入后核对

|项目|Rev B 预期|
|---|---|
|板框与叠层|39×60 mm，4 铜层，板厚 1.6 mm，各层铜 35 µm|
|元件与网络|45 个元件，38 个网络，203 个唯一物理引脚|
|主电源|P2.1=VM_RAW；U6 的 IN 接 VM_RAW、OUT 接 VM；SW1 仅控制低电平有效的 EN|
|原使能|U5 仍连接原 nSLEEP 网络，作用与 SW1 分开|
|控制插座|CN3：1=R_EN，2=R_PH，3=L_PH，4=L_EN；无 GND 引脚|
|功率线路|外层公共主干 1.80 mm、电机主线 0.70 mm、高边漏极支路 1.0 mm；In2.Cu 公共 VM 铜带 4.6 mm，并有局部功率铜区|
|普通规则|最小铜间距／线宽 0.15 mm，信号孔 0.45/0.20 mm；功率孔阵列按源板核对|
|地与相节点铜|F.Cu、In1.Cu、B.Cu 的 GND 铜；顶层相节点局部宽铜，以及 In2.Cu 的 VM 铜带／支路|

旧格式文件不携带现代详细介质叠层，原叠层另存于 `KiCad_Import_5/stackup-source.kicad-sexpr.txt`。请在专业版设置成品厚度、各层铜厚及板厂实际叠层；导入器可能不迁移全部制造规则。

官方导入会重建铺铜，因此要检查相节点宽铜连接、四孔阵列连接、各层地连续性、VM 铜带与信号间距，以及未连接项。重新填充铜区属于铺铜，不是自动布线。禁止用自动布线替换已经人工规划的线路。

## 核对范围与限制

原图 38 个元件的取值保留；原有 173 个物理引脚中，172 个网络不变，唯一授权变化是 P2.1 从 VM 改接 VM_RAW，以串入主电源控制。新增七件为 U6、SW1、R10–R12、C18、C19。见 [Rev B 原图范围核对](validation/rev_b_original_source_contract.json)。

冻结后的 KiCad 9 源板 DRC 为 **0 违规／0 未连接**，原理图 ERC 为 **0 错误／0 警告**。本版 [独立布局几何检查](validation/layout_geometry_audit.json) 通过：14 条关键去耦路径全在顶层、最长 2.9713 mm，丝印／焊盘／过孔碰撞 0，审核范围内不良弯折 0。检查范围、弯折排除和 [最后修改记录](validation/rev_b_final_silk_cleanup.json) 可逐项查看。

兼容副本已通过真实 **KiCad 5.1.9** 检查：原理图 **ERC 0 错误／0 警告**，PCB **DRC 0 错误／0 未连接**。PCB 已重填所有铜区，并开启全部走线错误、走线与填铜检查。45 个元件及原值、38 个网络、203 个唯一引脚（194 个连接、9 个 NC）全部一致。

旧副本保留源板 592 段线路、151 孔、211 焊盘和 12 铜区，另含 32 段位于 MOS 既有漏极焊盘铜内的连接段，共 624 段；独立几何证明新增实际铜面积 **0.0 mm²**，不改变外部布线。旧版按原铜区边界／参数实际重填，不能以新旧缓存字节相等代替铜几何核对。见 [旧版最终等价报告](validation/legacy5_final_pcb_equivalence.json) 和 `KiCad_Import_5/validation/` 的实际软件记录。功率网络与填铜审计见 [rev_b_engineering_audit.json](validation/rev_b_engineering_audit.json)。

另供桌面客户端的 `.eprj3` 已完成 [静态转换等价审计](EasyEDA_Pro/native-final-audit.json)，仍未在实际专业版桌面打开／运行DRC；它不替代本页网页导入ZIP。

当前没有用户已登录的专业版网页会话，**尚未在真实网页端完成最终导入和 DRC**。格式与源软件检查不替代专业版实际导入检查，也不代表样板通过上电／温升验证。第一次通电请按 [FIRST_POWER_ON.md](FIRST_POWER_ON.md) 操作；原图保留问题和元件采购要求见 [README.md](README.md)。
