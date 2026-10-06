# 游戏内导出器（0.2.0）

已针对本机 0.8.7d 日志版本对应的程序集编译通过；尚未在游戏内加载验证。读取初始化后的原型数据库，不注册新产品或修改配方，不写入游戏存档。仅在模组目录 `exports` 创建带时间戳的 JSON，错误记录到游戏日志。

## 构建和使用

```powershell
powershell -ExecutionPolicy Bypass -File .\build-exporter.ps1 -GameDirectory "<游戏目录>"
```

需要 .NET SDK。输出在 `build/exporter/BalancerDataExporter`，仅包含原创 DLL、manifest 和 MIT 许可，不包含游戏 DLL。

1. 将整个 `BalancerDataExporter` 文件夹放入 `%APPDATA%/Captain of Industry/Mods`。
2. 启动游戏，在 MOD 列表启用它。使用新的原版测试地图，禁用其他第三方 MOD；不要用重要存档进行首次测试。
3. 等待地图初始化，查看模组目录 `exports/game-data-*.json`。没有生成时检查游戏 `Logs` 中的 `BalancerDataExporter` 信息。
4. 转换导出文件：

```powershell
python import_game_data.py "<导出 JSON>" --output build/data-source/vanilla-scene.json
```

5. 查看旁边的 `.report.json`；通过计算器“导入 JSON”加载场景。不会覆盖现有目录或用户方案。

## 核验

在游戏中无加速、无科技产量修正的基础条件下，记录冶炼、装配、炼油的建筑 ID、配方 ID、周期、输入输出和 UI /60。再核对一个共享配方在两种等级建筑上的速率。导入结果应等于 `基础数量 × 建筑倍率 × 60 / 建筑周期`。

导出器记录原型所属 MOD，但尚未枚举完整 MOD 管理器，不能据此证明没有不注册原型的 MOD。必须人工确认测试环境。版本无法识别或任何绑定导出错误时转换器拒绝生成场景。

维护目前仅保留原始描述，不能作为计算器预算；运行含未知维护值的配方时结果显示“未知”。特殊原型单独报告，转换器只自动导入确切为 `MachineProto` 的普通建筑。其余类型需要单独适配。首次游戏核验之前不会标记“已交叉验证”。

原始导出、完整游戏文档和 DLL 保留本地，不提交到 GitHub。官方 API 可能随版本变化，升级后应重新编译和核验。

0.2版新增结构化维护字段（物料、月消耗、最大消耗、游戏月秒数），并按 EntityProto 枚举特殊建筑的公开数据字段，包含农场和能源设备等原先命名空间筛选遗漏的类型。字段提取错误或深度截断会显式记录。尚需重新加载游戏验证0.2版导出；旧包不会凭空补出维护或特殊参数。
