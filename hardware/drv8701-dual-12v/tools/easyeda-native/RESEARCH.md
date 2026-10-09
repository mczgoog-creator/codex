# 嘉立创 EDA 专业版文件路径与验证研究

更新时间：2026-10-09。仅研究与文件生成，没有调用自动布线。2026-10-08 的 Rev A 探针保留为历史工具验证，当前最终结果为文末的 Rev B 核验。

## 官方来源

- 官方 AI/API SDK：<https://github.com/easyeda/easyeda-api-sdk>
- 官方 API 技能与完整 API 参考：<https://github.com/easyeda/easyeda-api-skill>
- 官方桌面 CLI 文档：<https://github.com/easyeda/easyeda-client-cli>
- 官方当前原生格式、JSON Schema、验证器：<https://github.com/easyeda/easyeda-format-skill>
- 官方 `.eprj3` 格式与真实导出样例：<https://github.com/easyeda/easyeda-pro-eprj3-format>
- 官方 KiCad → 原生 `.eprj3` 转换器：<https://github.com/easyeda/kicad-to-easyeda-eprj3>
- 官方原生工程结构验证器：<https://github.com/easyeda/easyeda-eprj3-skill>
- 旧 V3 格式：<https://github.com/easyeda/easyeda-file-format>

转换器校验版本：`a16545dd7922455e6a20f69adeb234c924af08b5`。
转换器自带测试：2026-10-08 实跑 `npm test`，78/78 通过。零 npm 依赖。

## 格式与客户端要求

`.eprj3` 是原生桌面客户端文件夹工程：索引文件为 JSON，`sch/Schematic1/P1.esch2` 为原理图、`pcb/PCB1.epcb2` 为 PCB，另有 `.ecfg` 和 `.evar`。
必须解压完整工程目录后，用专业版离线／半离线桌面客户端打开索引文件。官方 eprj3 项目说明要求 V4.1+；自动化 CLI 要 V4.1.60+。
它不是标准版 JSON，也不是改名后的 KiCad 文件。
`.epro2` 是专业版 V3+ 使用的 ZIP 工程归档，通常需由真实客户端 `getProjectFile` 导出。当前没有实测的 `.epro2` 编码器，因此不伪造 ZIP 并改名。

用户采用网页端时，主交付为官方[「导入 KiCad」指引](https://prodocs.lceda.cn/cn/import-export/import-kicad/index.html)对应的 KiCad 5 工程 ZIP。本工程的 `.eprj3` 仅是附加桌面文件夹工程，不能交给网页端要求 `.epro` 的导入入口，也不构成网页导入实测。

官方 API 也明确支持 `SYS_FileManager.importProjectByProjectFile(file, 'KiCad', ..., {operation:'Offline Client Local Path', folderPath:...})`。这是 beta 导入接口。网络类、自定义规则、3D、SPICE 不由转换器迁移。

## 真正打开的验证边界

当前机器存在 KiCad 9.0.2 与 Chromium，但无 `easyeda-pro` 或 `lceda-pro` 客户端，也无已连接的官方桥接服务。
客户端与在线文档下载域名当时受到代理403／上游418、503限制。
因此能验证记录语法、字段格式、文档引用、每个符号脚网络、每个 PCB 焊盘位置和走线几何；不能宣称已在真实嘉立创桌面客户端打开或通过其 DRC。

原生工程文件生成无需登录；官方客户端 CLI 工作时需要实际安装并运行桌面客户端。

## 实测发现与外部修正

不修改官方工具源代码，`finalize-native.js` 对其输出做可审查的修正：

1. 添加官方结构要求的空 NET 记录和原理图 `.ecfg` 两条 TRACK 规则。
2. 统一各文档 `client` 为 `md5(owner_uuid)[:16]`，重排每文档逻辑票据。
3. 将 standalone NETLABEL 转为所属 WIRE 的 NET 属性，逐个检查标注点确实接在线段上。
4. 不连接标记的 X 使用非导电图形，消除转换器的悬空 lineGroup；原理图 NC 引脚网络依然为空。Rev A 为7脚，当前 Rev B 为9脚。
5. 修正 PCB 旋转。实跑 KiCad9 探针：`footprint at(10,10,90)`、`pad at(1,0,90)` 绝对焊盘坐标是 `(10,9)` mm。原转换器的 `angle=270` 会放到 `(10,11)`。修正为组件原角度，局部焊盘角度 `padAngle-footprintAngle`，逐个焊盘验算世界坐标。
6. PCB ATTR 使用父组件 id 加局部 id 的复合 id。
7. 保留源板参考标注位置、文字尺寸和是否隐藏。
8. 将 PCB 的精确封装文档嵌入原理图并绑定组件 Footprint，删除 FOOTPRINT 中无语义的 PART。
9. 对多层板启用对应内部铜层，并按真实导出样例写物理叠层。
10. 将椭圆钻槽由错误的 ROUND 记录纠正为 SLOT，保留槽长／孔径及槽相对焊盘方向；保留 KiCad roundrect 的实际圆角半径。
11. 为每个 symbol＋footprint 组合生成两者齐全的内嵌 DEVICE；原理图和 PCB 使用同一器件与 Unique ID，不依赖云端器件库。
12. PCB 元件添加与源 `Value` 一致的隐藏 `Name` 属性，避免共用同一符号／器件的电阻电容丢失各自实际数值；独立核对原理图与 PCB 全部位号和实际元件值。
13. 保留各铜区的优先级 `POUR.order`，依据源区的网络、层和精确边界独立匹配；写入源板一致的实心填充、最小厚度、孤岛删除及 `DIRECT` 焊盘连接规则。

物理叠层特别说明：当前 `layer_phys` 文档说 thickness 为0.1mm，真实官方 V4.1.36 导出模板则铜层1.379对应0.035mm、介质59.449对应1.510mm，即 mil；当前后处理采用真实导出值的单位。需在真实桌面客户端里确认并按实际厂商层压结构审核。不可把这里的字段级检查说成客户端叠层确认。

源板若有明确 stackup，则保留其铜／介质厚度；若只有板厚与铜层列表，输出的是每层35µm铜、总厚1.6mm的名义FR4叠层，不能将其描述为已选定的厂商介质结构。

规则单位也存在上游差异：当前官方 `t-rule-context.json` 描述 1长度单位=0.254mm，然而真实V4.1.36 PCB导出默认安全间距5.9843、最小线宽5、默认孔径规则12.0079/6.0039，其数值显然采用PCB mil口径；同一真实工程 SCH 规则值为mm。工程保留V4.1.36格式并采用对应真实PCB模板的mil编码；`native-design-rules.json` 写明预期mm数值及这一未解决差异。格式检查无法代替客户端规则显示确认。后处理脚本也提供显式 `internal10mil-current-schema` 选项，只有实际客户端确认对应格式口径后才应使用。

铜区最小填充厚度对应的 `POUR.width` 另有真实导出例外：官方转换器按 mm 写入，当前字段 schema 描述则按 mil。后处理保留该官方 mm 例外；`pourType.fineness` 和 PCB 铜区规则长度使用真实导出模板的 mil。当前源板所有铜区的间距、焊盘连接和热焊盘参数一致，故用四铜层的默认 `COPPER copperRegion` 规则表达，避免猜测未经验证的逐区规则选择器。非一致的逐区连接／间距／热焊盘参数、按面积阈值删除孤岛、hatch 填充及逐焊盘连接覆盖缺少已核验的映射时，适配器明确拒绝转换。当前 Rev B 不含这些特性。

## 验证工具

- `validate-native.js`：使用当前官方 `<DOCTYPE>_<TYPE>` schema，逐行校验外层记录。官方真实导出模板与字段类型差异单独列出，不修改 schema 以制造通过。
- `check-native-nets.js`：直接读取生成的原生符号、WIRE 与 NET 属性，重建逐物理脚网络并和源原理图比较。
- `check-native-pcb.js`：从原生 PCB 的组件／封装／PAD_NET 重建网络，与独立原始逐脚表比较；将所有直线轨迹的端点、宽度、网络、层别，所有过孔的位置、孔径、外径与所有铺铜边界／已填多边形逐一和 KiCad 源比较。
- `audit-native-project.js`：从设计清单与独立物理脚表动态取得元件／脚／网络数量，核对原生 SCH／PCB 实际元件值，汇总字段、网络、几何及库链接审计，并将报告绑定到最终源文件 SHA256。
- 官方 `easyeda-eprj3-skill/scripts/validate.js`：工程引用、逻辑票据、文档uuid、封装及器件链接、NET索引、线路组验证。

**2026-10-08 Rev A 历史原理图工具探针：**38组件、34网络、173物理脚（166已连接、7不连接）逐脚一致；所有1445行外层记录合法；字段验证没有未解释失败；官方结构验证0错误、0警告。这些数量不是当前 Rev B 的结果。

**2026-10-08 历史四层及槽孔工具探针：**90°旋转的0603与 SS12D10G4、7焊盘、4条手画轨迹、1过孔、4层铺铜及4个已填多边形转换前后一致；204行外层记录合法、字段无未解释失败、官方结构验证0错误／警告。该探针为工具校验样例，不是最终电机驱动板，也没有进行自动布线。

## 2026-10-09 Rev B 最终转换核验

入口为 `EasyEDA_Pro/DRV8701_DUAL_12V.eprj3`。聚合报告 `EasyEDA_Pro/native-final-audit.json` 绑定源 PCB SHA256 `daa3c5be68e8667a06f6da7ec5fd3c1238de758fb6982bcae6e130e6b8204989`，源原理图 SHA256 `da70605eba1826030f21ac655e2cb976c7ec27bc7cdd6379871e1fb34a657f04`；转换未改源文件。

- 45 元件的位号／实际值在原生原理图和 PCB 中均与 `design_netlist.json` 严格一致。
- 38 个命名网络、203 个唯一物理脚逐脚一致，其中9脚 NC；PCB 有211个焊盘实例，8个额外实例来自 MOS 同编号暴露焊盘。
- 592 线路段、151 过孔、12 铜区边界、12 已填多边形、4 板框边逐项一致；焊盘的绝对坐标、角度、尺寸、圆角、钻槽、镀孔、阻焊／锡膏扩展逐项一致。
- 39 × 60 mm 板框、四铜层和源板物理叠层一致：各铜层35 µm，含阻焊总厚1.6 mm。
- 4 个 F.Cu 相位铜区和 5 个 In2.Cu VM 铜区保留优先级2；3个 GND 铜区保留优先级0。全部 `DIRECT`、间距0.15 mm、最小填充厚度0.15 mm、删除所有未连接孤岛；源热焊盘间距0.25 mm、辐条宽度0.5 mm仍保存，但直连时不生效。
- 14 个配对器件、13 个封装全部内嵌，外部器件库依赖为0。
- 官方工程结构验证0错误、0警告。4096条记录外层全部合法，1877条直接满足当前字段 schema、164条来自可信官方真实导出模板；5273项已记录的模板／当前 schema 差异按具体字段保留解释，未映射类型0、未解释失败0。这些数量是文件格式审计统计，不是客户端 DRC。

最终代码采用设计清单动态统计，不再固定 Rev A 的38／34／173数量。新增 TPS25910 的标准 roundrect／rect 焊盘和符号引脚进入相同独立几何及逐脚检查，没有跳过新增 IC。

实际专业版桌面客户端打开、重新铺铜和 DRC 仍未实测；首次打开须确认1.6 mm、四铜层各35 µm、0.15 mm最小间距／线宽，以及源铜区优先级、直连、最小填充厚度和孤岛设置。保存的铜几何与源板一致不等于已经验证客户端重新填充行为。网页端主交付的实际 KiCad 5 检查另见 `KiCad_Import_5/validation/`。
