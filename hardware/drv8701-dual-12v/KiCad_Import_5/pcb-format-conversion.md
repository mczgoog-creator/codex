# PCB 旧格式兼容副本

此目录的 PCB 采用 KiCad 5.1 的真实 `20171130` S-expression 格式，并非修改版本号。原始 KiCad 9 设计保留在上一级目录。

转换依据：KiCad 官方源码镜像 `5.1` 分支，固定提交 `2758acfd4265f295c14a5bf009fa742e4abad131` 中 `pcbnew/pcb_parser.cpp`、`pcbnew/kicad_plugin.cpp`、`pcbnew/kicad_plugin.h` 与 `pcbnew/class_zone.cpp`。

- 层编号转换为 KiCad 5 的编号；已声明但无图形使用的 User.1–4 从声明表中移除。
- `footprint` 转 `module`；Reference/Value 转 `fp_text`；`stroke (width …)` 转 `width`；矩形转四条等宽线。
- 不受旧格式支持的 UUID、生成器、默认空字段和 THT 默认属性转换或移除。长槽孔尺寸、roundrect 比例、位置、旋转、尺寸及网络保持。
- 元件 timestamp 采用原理图实例 UUID 的前 8 个十六进制字符（38 个均唯一）；PCB path 使用 `/timestamp`，与旧原理图 U 行关联。
- 叠层材料和铜厚在 `stackup-source.kicad-sexpr.txt` 保留。5.1 的 PCB 语法没有现代 stackup 字段；铜层数量和板厚保留。

源 KiCad 9 的填充缓存使用 `filled_areas_thickness no`；KiCad 5 不支持该语义。直接复制边界将使旧版沿边缘额外扩铜。因此转换时清除缓存，保留三个铜区的原边界、GND 网络、0.15 mm 最小铜宽、0.15 mm clearance、直接连接方式和热焊盘参数，随后应由真实 KiCad 5 原生重建铺铜及检查。清除缓存后的读回检查不等于填充后 DRC 通过。

`pcb-geometry-equivalence.json` 记录加桥前基础转换副本的独立读回检查；它不是最终加桥成品的报告。`footprint-library-equivalence.json` 记录 11 种独立封装的焊盘几何等价。

真实 KiCad 5 的旧连接检测没有识别 MOS 大 D 焊盘与四个小 D 焊盘的微小重叠，因此只在旧副本中为 Q1–Q8 各加 4 条 0.25 mm 短铜桥。最终为 290 段走线，原始 258 段多集完全保留，原始 76 过孔、181 实际焊盘、3 铜区边界参数、元件位置旋转与板框均保持。`validation/legacy5_final_pcb_equivalence.json` 是最终成品对应的独立报告。

每条新增铜桥的完整胶囊形铜（含圆端帽）均使用 1 nm 最大误差的保守外包；原小 D roundrect 焊盘与大 D rect 焊盘使用保守内包。布尔差集证明 32 条铜桥全部包含在原焊盘铜并集内，新增实际铜面积为 0.0 mm²。此修复只提供旧版本连接检测所需的显式段，源 KiCad 9 PCB 未修改。

重新转换会清除已有的旧版铺铜缓存；完成真实 KiCad 5 重填后请勿直接覆盖该成品：

```sh
/usr/bin/python3 tools/import-kicad/convert_pcb_legacy.py
/usr/bin/python3 tools/import-kicad/audit_legacy_pcb.py
# 对加桥后的最终旧版成品检查：
/usr/bin/python3 tools/import-kicad/audit_legacy_bridges.py
```

审计命令需安装 KiCad 9 的 `pcbnew` Python 模块。第一条只有 Python 标准库依赖。原始设计布线不变，整个过程没有使用自动布线。

嘉立创官方 [KiCad 导入说明](https://prodocs.lceda.cn/cn/import-export/import-kicad/index.html) 提醒导入后会自动重建铺铜，结果可能有差异。真实嘉立创客户端导入后仍需检查铜区、网络连接和 DRC。
