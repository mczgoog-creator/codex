# DRV8701 双电机驱动板 · Rev B · 12 V

依据用户原始《8701驱动板（无电流检测2.0）.pdf》重建。本版重新安排半桥功率器件、去耦、供电和回流，并按用户后续要求加入主电源控制。**原 38 个元件的取值全部保留；原有引脚唯一授权网络变化是 P2.1 从 VM 改接 VM_RAW。** 原图其余连接保留，新增七件：U6、SW1、R10–R12、C18、C19。核对见 [rev_b_original_source_contract.json](validation/rev_b_original_source_contract.json)。

PCB 每个元件位置、线路、过孔和铜区边界均人工规划，未使用嘉立创自动布线器、其它自动布线器或路径搜索。脚本按明确坐标生成线路；铺铜填充只是按既定边界生成铜区。

## 打开工程与交付文件

用户使用嘉立创 EDA 专业版**网页端**。主要入口为 **`DRV8701_12V_KiCad5_Import.zip`**：在网页开始页选择 **「导入 KiCad」**后直接选择 ZIP。依据[官网指引](https://prodocs.lceda.cn/cn/import-export/import-kicad/index.html)，导入副本采用真实 KiCad 5.1 格式并由 KiCad 自带归档功能打包。步骤见 [IMPORT_IN_WEB_PRO.md](IMPORT_IN_WEB_PRO.md)。

原始 KiCad 9 源文件与库保留。桌面入口 `EasyEDA_Pro/DRV8701_DUAL_12V.eprj3` 由官方转换器及独立后处理生成，另供专业版 V4.1+ 离线／半离线客户端使用，需保留整个目录；不能当作网页 `.epro` 文件导入。

**尚未在真实嘉立创 EDA 专业版完成导入和 DRC。** 导入会重建铜区，需复核板框、叠层、功率铜区和设计规则。桌面文件的 schema／真实导出模板单位差异见 `tools/easyeda-native/RESEARCH.md`；首次打开应确认实际尺寸和规则值。

|文件|用途|
|---|---|
|`DRV8701_DUAL_12V.kicad_sch/.kicad_pcb/.kicad_pro`|Rev B 可编辑原理图、PCB、规则|
|`DRV8701_Custom.kicad_sym`、`DRV8701_Custom.pretty/`|本地符号及封装；配套库表同目录保存|
|`KiCad_Import_5/`|真实 KiCad 5.1 格式的网页导入副本|
|`imports/DRV8701_12V_KiCad5_Import.zip`|专用网页导入 ZIP|
|`EasyEDA_Pro/`|另供新版桌面客户端使用的文件夹原生工程|
|`DRV8701_DUAL_12V_schematic.pdf`|原理图阅读版|
|`PCB_layers_review.pdf`、`pcb_top/bottom.svg/.png`|从源 CAD 导出的各层检查图与顶底预览；底层 PNG/SVG 已镜像，按从底面观察显示|
|`components.csv`、`procurement_notes.csv`|元件值、封装及采购额定参数|
|`source/source_netlist.json`|原始 PDF 独立复核网表，作为原图基准保留|
|`validation/rev_b_original_source_contract.json`|原图取值、连接与授权主电源差异核对|
|`final_drc.json`、`validation/schematic_erc.json`|冻结后的 KiCad 9 DRC 与原理图 ERC|
|`validation/layout_geometry_audit.json`|独立读取实际 PCB 的路径、弯折、过孔与丝印检查|
|`validation/rev_b_final_silk_cleanup.json`|最终丝印调整与唯一最后铜线修改范围|
|`validation/rev_b_engineering_audit.json`|本版功率网络、填铜与工程审计|
|`validation/preview_exports.json`|本版预览与各层 PDF 的源板 SHA／导出记录|
|`source/engineering_review.md`|本版布局与电流路径说明|
|`source/tps25910_power_control_review.md`|主电源芯片手册、启动／限流／关闭状态核对|
|`FIRST_POWER_ON.md`|首次上电和两级开关操作步骤|
|`footprint_geometry.json`、`manual_routes.json`|封装依据及人工规划线路记录|
|`scripts/generate_schematic.py`、`tools/build_board.py`|原理图及明确坐标的 PCB 生成程序|
|`validation/`|本版最终检查记录|

用 KiCad 9 打开 `.kicad_pro` 即可读取同目录库。重建程序会覆盖其负责的设计文件，运行前应保存手工编辑副本。

## 尺寸、电流与布局

仅采用用户电机表格的 **12 V** 条件：每路较高档额定 0.4 A、堵转 1.8 A；电机路径按每路 1.8 A，公共供电／回流按合计 3.6 A 规划。堵转值用于短时最大电流初筛，不表示允许持续堵转。

本版 **39×60 mm、4 层、标称 1.6 mm**，元件全在顶面。四铜层均 **35 µm（1 oz）**，孔电阻计算假设成品孔铜至少 20 µm。名义叠层：两面阻焊各 0.01 mm、四铜层各 0.035 mm、两段半固化片各 0.20 mm、中芯板 1.04 mm，总厚 1.60 mm；板厂应据实际材料匹配成品规格。普通 R/C/LED 为 0603，R8/R9 为 1210，新增 C18 为 0805；没有小于 0402 的贴片。

|通路|本版设计|
|---|---|
|P2 至 U6、U6 至 C15 及两路主供电|外层公共主干 1.80 mm；C15 正极为汇合与分配点|
|In2.Cu 并行供电|4.6 mm VM 公共铜带与局部宽铜支路|
|高边 MOS 漏极|短 1.0 mm 外层支路，并由内层铜和四孔阵列连接裸露漏极焊盘|
|高边源极至低边漏极|相邻封装间的局部顶层宽铜，四组半桥均按相同结构安排|
|电机连接器|0.70 mm 外层主线，每个相节点配四孔功率阵列|
|低边 MOS 源极|短支线接本地宽铜，四孔阵列接地；F.Cu／In1.Cu／B.Cu 地铜提供并行回流|
|U6 IN／OUT|各三个并联引脚，每脚短 0.45 mm 连接接入公共铜；不是单根 0.45 mm 线路承担 3.6 A|
|信号与驱动支路|约 0.20–0.30 mm；这些线路不承担电机主电流|

IPC-2221 经验式 `I=k×ΔT^0.44×A^0.725`（A 为平方 mil）用于初筛。35 µm 铜、约 10°C 温升时，外层 1.8 A／3.6 A 线宽约 0.676／1.758 mm，内层约 1.76／4.57 mm，因此内层公共 VM 铜带取 4.6 mm。该经验式不计算实际板上的电流密度、开关波形或温升，成品仍需测量。

C15 安排在受控 VM 供电汇合处，两路从其正极向外分配。每组高／低边 MOS 旋转后令高边源极紧邻低边裸露漏极，以宽铜连接相节点。泵／内部电源去耦至芯片的关键连接留在顶层，VM 电源先进入 C3/C10 再到 VM 引脚；C4/C11 位于功率母线旁。SH 源参考采用独立细线返回高边源极焊盘，但栅极和参考线仍有转层，14 条关键连接静态路径的最大长度为 2.9713 mm、0 转层；GH1 约 19.22 mm、GH2 约 13.56 mm 且仍有转层，不能宣称全部驱动回路已最小化或开关振铃已验证。

制造规则最小间距／线宽 0.15 mm，普通信号孔 0.45/0.20 mm，最小钻孔 0.20 mm、最小环宽 0.10 mm。具体功率孔阵列和最终几何以本版检查报告为准。

## 主电源与接口

|位号|功能与引脚|
|---|---|
|P2|12 V 电源 XT30：1=VM_RAW 正极，2=GND|
|U6|TPS25910RSAR：IN 1/2/3=VM_RAW；OUT 10/11/12=VM；中心焊盘接 GND|
|SW1|主电源开关：2=PWR_EN，3=GND，1=NC；接通 2–3 时 U6 导通|
|U5|原 DRV8701 使能：2=NSLEEP，3=齐纳 3V3，1=NC；断开 2–3 时为休眠档|
|CN1/CN2|左／右电机 XT30：1=L_A/R_A，2=L_B/R_B|
|CN3|1=R_EN，2=R_PH，3=L_PH，4=L_EN；原图未设置 GND 引脚|

CN3 没有公共地针脚，控制器 GND 必须另外连接 P2 的 GND。SW1 是主供电控制，U5 是驱动芯片睡眠控制，二者不能混用。

TPS25910 工作电压 3–20 V、IN/OUT 绝对最大 22 V；本工程仅按 12 V 使用。连续额定 5 A，R12=40.2 kΩ、1% 对应限流 **4.5 A 最小／5 A 典型／5.5 A 最大**。这只是公共电源故障控制，不是两路电机各自的电流测量或斩波限流。3.6 A 时芯片导通损耗约 0.38 W 典型／0.54 W 最大，需要焊实中心接地焊盘并验证温升。

EN 为低电平有效。SW1 接通将 EN 拉地；断开时 R10=100 kΩ、R11=33 kΩ 分压产生约 2.98 V 高电平关闭。**关闭时 U6 自身仍消耗 2.5 mA 典型／4 mA 最大，分压另约 90 µA**。C15 储能和电机回馈可能使 VM 暂时有电；TPS25910 本身没有反向电流阻断，因此主开关不是电池物理隔离。长期存放应拔掉电源。

C19=10 nF 对 12 V 的理想上升时间约 **11.1 ms 典型**，按手册 8–15 µA 驱动电流初算约 **8.2–15.3 ms**。实际电容、输入电源、限流和热保护会改变或延长启动。手册 12 V 启动最小负载电阻为 12 Ω，接有 C15 时可用启动负载进一步减少；因此**开启 SW1 前保持 U5 休眠并令两路 EN=0，VM 稳定后再使能电机**。不得把典型上升时间当作控制器等待的保证值。

## PWM 与原图保留问题

按用户确认的 **不高于 20 kHz EN PWM** 使用，PH 固定方向。R8/R9=100 Ω、C16/C17=100 nF 串联 RC 保留；电阻采用 **1210、至少 0.5 W**。12 V／20 kHz 充分充放电模型每路约 0.288 W 上界、50% 占空比约 0.244 W。PH 周期翻转会产生更大的跨端阶跃，不能沿用该热假设。

|项目|保留的原图与影响|
|---|---|
|C2/C9 VCP–VM|100 nF，TI 推荐 1 µF；须检查泵纹波与驱动欠压|
|C5/C12 AVDD、C6/C13 DVDD|100 nF，TI 推荐 1 µF；须核查 LDO 稳定性和纹波|
|C1/C8 CPH–CPL|100 nF，与 TI 推荐值一致|
|VM 旁路|保留 100 nF 与公共 C15=470 µF；须测供电／再生电压|
|VREF／IDRIVE|各自接 AVDD；约 25/50 mA 源／灌，关闭高边 VDS 过流检测|
|SP／SN|接 GND；没有电机电流采样及各路可设斩波限流|
|nFAULT／SNSOUT／SO|原图 NC，控制器不能由这些脚接收原驱动器故障或采样信息|
|10 kΩ／齐纳 3V3|12 V 下假定 3.3 V 时总馈电约 0.87 mA；还供 LED 与 nSLEEP，须实测低电流工作点|
|CN3|无 GND 引脚，控制器另行共地|

布局重排和新增主开关没有修正上述原值与原连接。首次验证内容及顺序见 [FIRST_POWER_ON.md](FIRST_POWER_ON.md)。

## 焊接与采购复核

DRV8701 是 4×4 mm RGE24 VQFN、0.5 mm 脚距，中心地焊盘必须焊实。U6 是带中心地焊盘的 RSA16 VQFN。建议焊膏、预热和热风／手动回流；仅烙铁处理外围脚不能保证中心焊接。未填孔热过孔会吸锡，需检查浮高和空洞。

TPH1R403NL：1/2/3=S、4=G、5/6/7/8=D，中心裸露金属同属 D；高边裸露焊盘为 VM，低边为相节点，不能当作接地散热焊盘。原厂 **2026-04-14 Rev.3.0.A** 已读取：VDS 30 V、VGS ±20 V；10 V 下 RDS(on) 典型 1.2 mΩ／最大 1.4 mΩ，Qg 典型 46 nC、Qgd 典型 4.3 nC。引脚与普通 SOP Advance 的机械图已核对，详见 [原厂核对](source/tph1r403nl_manufacturer_review.md)。

该手册 p8 普通 SOP Advance 与 p9 SOP Advance(N) 不同，采购需匹配 p8。手册未提供推荐 PCB 铜焊盘图，外围 0.5×1.2 mm 焊盘是本设计尺寸。典型 Qg／原图 25/50 mA 的估算不替代最坏公差及实测 VGS。

SS12D10G4 的用户实测脚宽 1.3 mm、厚 0.8 mm，使用 2.3×1.1 mm 槽孔。C18 采购目标为 4.7 µF／50 V／X7R／0805，**须按具体料号的 DC 偏压曲线核对 12 V 下有效电容≥1 µF**；当前没有对某个采购料号完成该曲线验证。XT30、XH 实物外形、极性与 U6 钢网要求也应按采购品及厂商图复核。

## 来源与验证边界

- 原始 PDF：用户提供，见 `source/original_schematic.pdf`；原始网表见 `source/source_netlist.json`。
- TI DRV8701：[原厂手册](https://www.ti.com/lit/ds/symlink/drv8701.pdf)，SLVSCX5B，附原厂镜像 PDF `source/TI_DRV8701_SLVSCX5B.pdf`；镜像来自 [Tinkerforge](https://github.com/Tinkerforge/performance-dc-bricklet/blob/master/datasheets/drv8701.pdf)。
- TI TPS25910：`source/TI_TPS25910_SLUSAR6D.pdf` 与 EVM 手册；参数、封装及页码见 [主电源核对](source/tps25910_power_control_review.md)。
- Toshiba：[精确型号原厂 PDF](https://toshiba.semicon-storage.com/info/TPH1R403NL_datasheet_en_20191030.pdf?did=14296&prodName=TPH1R403NL)，本包为 Rev.3.0.A；MOS 封装几何另参考 [zdxddmx/smartcar-hardware](https://github.com/zdxddmx/smartcar-hardware) 的同型号原生库，交叉核对 [CaptainJaja/DRV8701_2Motors](https://github.com/CaptainJaja/DRV8701_2Motors)。未复用其它工程的 PCB 布局或布线。
- 官方转换／验证工具保留原许可证，上游 URL／commit 见 `tools/easyeda-native/upstream-versions.json`。

本版为 **45 个元件、38 个网络、203 个唯一物理引脚／211 个焊盘实例**，592 段人工指定线路、151 个过孔、12 个铜区。源 KiCad 9、KiCad 5 导入副本和桌面原生工程分别核对，各自结果保存于 `validation/`、`KiCad_Import_5/validation/` 和 `EasyEDA_Pro/native-*.json`，不沿用 Rev A 检查成绩。

冻结后的源板 KiCad 9 **DRC 0 违规、0 未连接**，原理图 **ERC 0 错误、0 警告**。独立 [布局几何审计](validation/layout_geometry_audit.json) 通过，14 条关键去耦连接全部顶层且 0 转层，最长 2.9713 mm；丝印与焊盘／过孔碰撞 0，审核范围内直角／锐角弯折 0。弯折分类排除同网焊盘／过孔内以及真实分支结点。最终 PCB SHA256 为 `daa3c5be68e8667a06f6da7ec5fd3c1238de758fb6982bcae6e130e6b8204989`。

[最终丝印复核](validation/rev_b_final_silk_cleanup.json) 确认最后铜修改仅把 C18.1 至 U6 IN 汇流处的一段 VM_RAW 输入颈缩由 0.9 mm 加宽到 1.8 mm；其它焊盘、过孔和铜区边界未在该步骤改变。R10 位号移至底层，其余位号在顶层；主电源／休眠开关说明与板名位于背面，开关 ON 仍对应右侧／pin3。功率铜区和原图差异另见 [Rev B 工程审计](validation/rev_b_engineering_audit.json)。

桌面原生工程 [native-final-audit.json](EasyEDA_Pro/native-final-audit.json) 已通过静态转换检查，源板 SHA 与冻结文件一致。45 件／38 网／203 个唯一脚、592 段线路、151 孔及 12 个实际填充铜区逐项对应；四层、叠层厚度、区优先级及直接焊盘连接参数保留。格式检查 4096 条外层记录有效，未映射类型／未解释失败均为 0；已知 schema 与真实导出差异单列，官方工程结构检查 0 错误／0 警告。**这些是文件级检查，实际专业版桌面打开与 DRC 未执行。**

网页副本已由真实 **KiCad 5.1.9** 检查：原理图 **ERC 0 错误／0 警告**，PCB **DRC 0 错误／0 未连接**。检查已重填全部铜区，并开启全部走线错误及走线与填铜检查。45 件及原值、38 网、203 个唯一脚（194 连接、9 NC）逐项一致。副本保留源板 592 段线路、151 孔、211 焊盘和 12 铜区，另加 32 段完全在 MOS 既有漏极焊盘铜内的连接段，使旧版识别原有铜连通；副本共 624 段、新增实际铜面积 **0.0 mm²**。新旧填铜缓存随软件版本不同，按源区边界／参数在旧版实际重填；审计见 [legacy5_final_pcb_equivalence.json](validation/legacy5_final_pcb_equivalence.json)。

原理图 PDF、五页 PCB 各层检查 PDF、各层独立 PDF 与顶／底 SVG／PNG 均已更新为冻结 Rev B，源板 SHA 与导出方式见 [preview_exports.json](validation/preview_exports.json)。底层预览已镜像；层 PDF 由源 CAD SVG 经矢量转换生成，以保留完整板框。

本交付没有生产下单或 Gerber 制造放行。**真实专业版导入、铺铜／DRC，以及样板启动、开关波形、温升和短时堵转测试未完成。** 静态格式或铜几何核对不能代替这些实测。
