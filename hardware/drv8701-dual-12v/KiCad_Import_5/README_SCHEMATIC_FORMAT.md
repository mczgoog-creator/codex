# Rev B：嘉立创专业版网页端 KiCad 5 导入工程

本目录是从冻结的 Rev B KiCad 9 工程转换得到的真实 KiCad 5.1 工程。网页端请使用实际 KiCad 5.1 项目管理器「File → Archive Project」生成的 `DRV8701_12V_KiCad5_Import.zip`，通过「导入 KiCad」入口导入。不要修改后缀或将 `.pro` 当作 `.epro` 导入。

Rev B 有 **45 个实体元件、38 个具名网络、203 个唯一物理脚**；其中 **194 个已连接脚、9 个 NC**。U6 为 TPS25910RSA 主电源开关，新增 SW1、R10/R11/R12 和 C18/C19。原图 38 个元件的值保留；仅按最新授权将 P2.1 从 VM 改为 VM_RAW，插入主电源控制。设计连接以 `../design_netlist.json` 为准，原始 PDF 与原始源网表单独保留。

本目录 `.sch` 为 EESchema Version 4，`.lib` 为 Version 2.4，`.pro` 为 KiCad 5 INI。符号、缓存库和封装库均在工程内，原理图实例 UUID 的前 8 位对应 PCB 组件标识。

已在真实 Eeschema 5.1.9 打开并运行 ERC：**0 错误、0 警告**。实际导出的 `.net` 与设计网表逐脚、逐值一致，NC 脚已验证独立。证据为 `validation/DRV8701_DUAL_12V.erc`、`validation/legacy_net_equivalence.json` 和实际运行截图。

尚未在用户已登录的嘉立创专业版网页端执行最终导入与 DRC。官方导入器会重新铺铜，导入后须核对铜区、制造叠层与规则。
