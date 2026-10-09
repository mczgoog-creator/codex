# TPH1R403NL 原厂手册核对

读取日期：2026-10-09。本记录核对MOS器件资料与封装，本次资料核对没有改变原图MOS连接或取值。Rev B的布局重排及授权主电源新增另见工程README；不把资料核对范围表述为整块PCB从Rev A起未变。

- Toshiba官网URL成功下载并可读取： https://toshiba.semicon-storage.com/info/TPH1R403NL_datasheet_en_20191030.pdf?did=14296&prodName=TPH1R403NL 。
- 尽管URL文件名含20191030，服务器目前实际返回 **2026-04-14 Rev.3.0.A、10页** 的官方 TPH1R403NL 手册；依据PDF内容记录版本。
- 交付文件：`Toshiba_TPH1R403NL_Rev3_0_A.pdf`。SHA256 `12a06e5d86ab4f4fd7d9dc543e2c7d85796f29c18ecd32b010ac4c99267ede17`。
- LCSC已知精确镜像仍HTTP403： https://atta.szlcsc.com/upload/public/pdf/source/20220830/C277A7BCA37DB7348B2C95BA2E6DA6BE.pdf 。TLS验证保持开启。

## 核对结论

|项目|原厂数据|页码|
|---|---|---|
|引脚|1/2/3 Source；4 Gate；5/6/7/8 Drain，裸露大金属亦属Drain|p1内部电路、p8底视机械图|
|VDS绝对最大|30V|p2|
|VGS绝对最大|±20V|p2|
|RDS(on)|VGS=10V、ID=30A：典型1.2mΩ、最大1.4mΩ；VGS=4.5V、ID=30A：典型1.7mΩ、最大2.1mΩ|p3|
|Qg|典型46nC（VGS10V），典型20nC（VGS4.5V）；VDD≈15V、ID60A，无最大值保证|p3|
|Qgd|典型4.3nC；VDD≈15V、VGS10V、ID60A|p3|
|SOP Advance|Toshiba2-5Q1S：body5±0.2×5±0.2mm；lead span6±0.3mm；pitch1.27mm；lead width0.4±0.1mm；height0.95±0.05mm|p8|
|裸露Drain金属|4.25±0.2×3.5±0.2mm|p8|

当前PCB所用SOP Advance库为5×5mm、1.27mm pitch、source1–3/gate4/drain5–8，裸露drain pad4.25×3.5mm，关键尺寸与p8原厂 **封装金属图** 相符。PCB外围引脚铜焊盘0.5×1.2mm、中心±2.77mm为设计焊盘，不应将其声称为本手册给出的推荐land pattern；此PDF没有提供推荐PCB铜焊盘图。手焊toes与裸露底部焊接仍须实际工艺验证。

新版手册也列出SOP Advance(N)/2-5W1A（p9），其body、height和裸露金属不同；现有库针对p8普通SOP Advance。采购时必须匹配实际供货封装，不能凭“TPH1R403NL”型号忽略封装版本。

原图IDRIVE直连AVDD严格保留，TI定义25mA源/50mA灌且关闭高侧VDS OCP。以Toshiba典型Qg=46nC做一阶估算，充/放电约1.84µs/0.92µs，均小于TI tDRIVE≈2.5µs；Qgd/IDRIVE对应Miller阶段约172ns/86ns。该比较支持原驱动设置可用的典型参数初筛，**不代表最大公差保证或实际VGS波形测试**，尤其不消除原图小电荷泵/去耦值的验证需求。

本记录仅完成官方资料与封装的静态核对，不授权改原值。实际通电、堵转／温升／EMI和真实嘉立创EDA客户端测试仍未进行。Toshiba精确原厂PDF已读取；“官方推荐PCB焊盘图／实板工艺均已验证”仍不能声称。
