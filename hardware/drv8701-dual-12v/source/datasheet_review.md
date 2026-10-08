# DRV8701 双电机板：手册核对与原样保留风险

用户最新约束：原图连接、元件值严格保留。以下研究不授权修改电气连接或电容/电阻值。封装尺寸与额定耐压/功率可依据实际使用选择。

## 资料状态

- TI 官方原文：SLVSCX5B，2015-03，2015-07 修订。官网 https://www.ti.com/lit/ds/symlink/drv8701.pdf 。
- 官网当前在云机器 CONNECT 返回403；使用 Tinkerforge 官方开源硬件仓库所附 TI 原厂文档镜像：https://github.com/Tinkerforge/performance-dc-bricklet/blob/master/datasheets/drv8701.pdf 。
- 交付包内原厂文档镜像为 `TI_DRV8701_SLVSCX5B.pdf`。PDF SHA256：5993f171a311fa8403ba77d5921534348ffddbbcf0c5d59c00c46b074671d850。
- TPH1R403NL 精确 Toshiba 官方PDF链接已核实（来自现成该器件KiCad原理图Datasheet字段）：https://toshiba.semicon-storage.com/info/TPH1R403NL_datasheet_en_20191030.pdf?did=14296&prodName=TPH1R403NL 。目前仍不能下载，不能标注为已读原厂MOS手册。
- 第三方该器件KiCad工程供交叉核对：https://github.com/CaptainJaja/DRV8701_2Motors 。本机 `mirror-captainjaja/lib/TPH1R403NL.pretty/TPH1R403NL.kicad_mod`。这是第三方封装，不能代替Toshiba机械图。
- 最终 MOS 焊盘几何依据 https://github.com/zdxddmx/smartcar-hardware 内 `eda/ProPrj_DRV8701电机双驱.epro` 的精确型号嘉立创原生封装 `572e0c5f381c446594eedc8b8157fefb`；具体尺寸见交付包 `footprint_geometry.json`。仅复用库几何，布局与每段布线均另行人工规划。

## 原图关键网络复核

根据原始 PDF 高清局部图复核，两芯片均：

- pin6 VREF = pin7 AVDD；pin12 IDRIVE = AVDD。
- pin20 SN = pin21 SP = GND；pin9 nFAULT、pin10 SNSOUT、pin11 SO 标NC。
- pin5、pin16、pin25 EP接GND；pin13 nSLEEP共同由独立3V3稳压与开关控制。
- 独立netlist复核已确证两路DVDD分开：L_DVDD、R_DVDD；AVDD及泵节点也分别独立。

## DRV8701E 引脚

1 VM, 2 VCP, 3 CPH, 4 CPL, 5 GND, 6 VREF, 7 AVDD, 8 DVDD, 9 nFAULT, 10 SNSOUT, 11 SO, 12 IDRIVE, 13 nSLEEP, 14 EN, 15 PH, 16 GND, 17 GH1, 18 SH1, 19 GL1, 20 SN, 21 SP, 22 GL2, 23 SH2, 24 GH2, 25 exposed thermal pad/GND。来源TI pp3–4。

## 原图与TI推荐的差别（保持原样，仅报告）

|项|源图|手册要求/说明|证据与影响|
|---|---|---|---|
|VCP储能 C2/C9|100nF，VCP–VM|1µF / 16V 陶瓷|TI p3/p4 外部无源表，p33布局；源图仅推荐值的1/10，电荷泵纹波/CPUV/栅极驱动应上电验证。|
|AVDD去耦 C5/C12|100nF|1µF、≥6.3V陶瓷|TI p3/p4、p22；不满足推荐去耦，LDO稳定性及调制纹波需测。|
|DVDD去耦 C6/C13|100nF|1µF、≥6.3V陶瓷|同上。|
|CPH–CPL C1/C8|100nF|100nF X7R，耐压≥VM|与手册匹配；12V采用25V/50V额定封装均可。|
|VM旁路 C3/C4/C10/C11|两只并联100nF|近端100nF + 至少10µF bulk|两只并联100nF不能替代bulk；原图共有470µF C15，应在布局中令其至两个H桥高电流回路短，实际电源线及再生下需验证。|
|IDRIVE|直接AVDD|25mA source / 50mA sink且关闭高边VDS OCP|TI p20表5与文字；源图保留，不能宣称高边OCP完整可用。低边OCP仍有。|
|VREF/SP/SN|VREF=AVDD, SP/SN=GND|不使用限流时就是此连接|TI p15 7.3.3；正确禁用电流斩波，无需采样电阻。|
|nFAULT/SNSOUT/SO|NC|nFAULT和SNSOUT为开漏输出，若使用需外部上拉；SO负载电容≤1nF|TI p4；未使用可以NC，设备不能向控制器报告故障/斩波/采样。|
|3V3稳压|VM→10kΩ→BZT52C3V3，另两路10kΩ+红LED及两芯片nSLEEP负载|独立稳压可避免用睡眠时关断的DVDD唤醒自身；低电流齐纳实际电压应验证|12V、假定3.3V时馈入0.87mA；两LED若Vf≈1.9V共耗0.28mA，两nSLEEP最小RPD64kΩ共耗0.103mA，齐纳仅≈0.49mA。BZT52C3V3的测试电流/低电流曲线尚待原厂手册确认；不能假定3.3V±标称公差成立。DRV8701 VIH≥1.5V / VIL≤0.8V（TI p7）。|
|信号4pin|R_EN,R_PH,L_PH,L_EN无GND|外部逻辑需要共同地参考|严格保留；接线说明要求控制器GND与电源接口GND共地，避免悬浮输入。|

## IDRIVE表（仅参考，不修改源图）

TI p20：<1kΩ→GND 6/12.5mA；33kΩ±5%→GND 12.5/25mA；200kΩ±5%→GND 25/50mA；悬空或>500kΩ→GND 100/200mA；68kΩ±5%→AVDD 150/300mA；<1kΩ→AVDD 25/50mA。只有最后一项关闭高边OCP。未来另行电气修订可200kΩ→GND维持原驱动电流并恢复高边OCP。原厂tDRIVE≈2.5µs；最终 MOS Qg/Qgd 应按 exact TPH 手册核实是否在时间内充放电。

## PCB布局依据

TI p33：VM–GND 100nF应尽量贴近pin1并以粗线/地平面到IC GND；bulk应靠近外部FET高电流回路；跨层时用多个过孔减小感抗；100nF CPH–CPL贴近pin3/4；VCP–VM电容贴近pin1/2；AVDD/DVDD去耦靠近pin7/8；SH1/SH2是高电流相节点，门极线尽量短，避开不相关控制线。

TI附录RGE0024F：封装4×4mm，0.5mm pitch；PCB端子24个焊盘0.24×0.60mm，对侧端子焊盘中心距离3.8mm；EP为2.8×2.8mm，必须焊接。QFN中心焊盘无法只靠普通烙铁充分焊接，建议焊膏+热风/预热或手动回流。焊膏开窗采用分区，防漂浮/锡珠；可选0.2mm热孔，若非填孔会吸锡，应设计钢网开口绕开。

Toshiba MOS pin map暂由第三方符号/行业SOP-Advance常见定义交叉核对：pin1/2/3 source、pin4 gate、pin5/6/7/8 drain，中心裸露焊盘也是drain。必须与Toshiba PDF最后确认。不得将FET裸露焊盘默认当GND；高边FET裸露D属VM，低边裸露D属电机相节点。

## 线宽与电流

只考虑12V 370电机：额定0.3/0.4A，每路最大堵转1.8A，两路公共电源3.6A。以更高12V档做设计；不为24V档加大线宽。

IPC-2221近似公式 I=k ΔT^0.44 A^0.725，A[平方mil]；外层k=0.048，内层k=0.024。35µm≈1oz铜厚。

|电流|外层10°C温升|外层20°C温升|内层10°C|内层20°C|
|---|---:|---:|---:|---:|
|0.4A|0.085mm|0.056mm|0.221mm|0.145mm|
|1.8A|0.676mm|0.444mm|1.758mm|1.154mm|
|3.6A|1.758mm|1.154mm|4.573mm|3.003mm|

建议外层每电机电流通路0.70mm，公共VM/GND1.80mm或等效宽度连续铺铜；若长线改为内层需按内层数值，不能复用外层宽度。芯片/FET焊盘出口短颈缩与过孔是局部限制，宜短颈缩、铜皮包覆、多个并联过孔；电流线不能经QFN窄焊盘传输。此经验式提供温升初筛，不替代实板验证或IPC-2152对具体堆叠的分析。

## 原图RC吸收功率（保持值，选合适封装）

两组电机跨端串联100nF+100Ω，τ=10µs。若标准DRV8701E EN-PWM慢衰减，电机端电压每周期0↔12V，频率20kHz、50%占空比：P_R=C V² f·tanh(T/(4RC))≈0.244W；充分充放电上界0.288W。高频极限约V²/(4R)=0.36W，故R8/R9建议1210且额定≥0.5W（原100Ω不变）。0603/0805一般0.1/0.125W额定不足。若PH每周期强制翻转产生−12↔+12V，功率约4倍，需要不同功率封装并实测；原4pin正常使用应PH固定方向、EN输入PWM。

## 仍需完成

1. 下载并读TPH1R403NL Toshiba 2019-10-30 PDF，核实VDS、VGS、Qg/Qgd、导通电阻与SOP-Advance制造焊盘图；当前厂家域名网络阻断。
2. 在真实嘉立创 EDA 专业版客户端中确认打开、尺寸、叠层和规则单位，重建铺铜并运行 DRC。
3. 上述核实完成后制作样板；冷启动、睡眠/唤醒、1.8A瞬时负载下测AVDD/DVDD/VCP与3V3/nSLEEP；记录nFAULT可用临时测量，不添加板上连接。
4. 按实际PWM频率和模式测试R8/R9温升及MOS开关波形，检查原图电容值下是否CPUV触发。制造完成不等于电气规格已实测通过。
