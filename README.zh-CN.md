# Repro Flightdeck：实验复现与证据回放

**让 Agent 的“完成了”能够被检查。**

[交互演示](https://FertayLageeze.github.io/repro-flightdeck/) · [English](README.md) · [方法与边界](docs/methodology.md)

输入一份经过人工审阅的实验清单，执行程序、寻找生成文件、恢复文件路径与字段对应关系，再用冻结的真实标签独立计算指标。全过程可以逐步回放。

## 当前能做什么

- 命令行运行真实 Python 实验，保存原始输出、协议、输入哈希和逐步记录。
- 找回改名的 CSV 文件，修复预测列与指标输入之间的对应关系。
- 独立计算 accuracy、二分类 NLL、RMSE、区间覆盖率。缺样本、重复 ID、NaN、无效区间均不能通过。
- 提供离线可打开的交互回放页，以及重新检查文件和指标的 `audit` 命令。
- 支持规则基线、Jev、Ollama 和低置信度转交 Ollama 的混合策略。

**版本边界：**v0.1 是受限动作空间的研究原型。演示来自真实 CPU 实验，决策由规则基线完成；Jev／LLM 接口通过响应样例测试，但还没有真实模型效果对比。当前不会自动阅读任意论文、安装环境、修改源码或复现完整论文表格。三个例子是公开方法在其他小数据集上的迁移实验。

## 开始使用

```bash
python -m pip install -e ".[demo,dev]"
python examples/prepare.py --out runs/cards
repro-flightdeck run runs/cards/temperature/manifest.json --out runs/first --allow-local-exec
repro-flightdeck audit runs/first
```

用浏览器打开 `runs/first/report.html`。页面中可以检查“执行 → 报错 → 发现文件 → 重新绑定 → 验收”的每一步。完整安装说明和模型接入命令见英文 README。

`--allow-local-exec` 表示执行你已审阅的本地代码。运行器不是沙箱，不能把陌生仓库直接当成安全输入。建议使用隔离的一次性环境。

## 已实测的结果

九次运行覆盖温度缩放、split conformal 和 SVM 的三个示例：两个输出协议故障可以恢复，三个故意生成的错误结果都被拒绝通过。规则恢复不修改验收阈值、不重新挑数据、不修改训练程序。

这些是工程回归检查，不是新算法或大规模科学评测。尤其是 conformal 示例的实际覆盖率为 83.8%，低于名义的 90%；通过较宽的工程检查范围不代表验证了 90% 覆盖率。

## Jev 与 FDE

Jev 适合在已定义的动作集合中选择下一步，低置信度时可以停止或转交 LLM。其结构化输出不等于判断一定正确。

本项目参考 FDE 的交付视角：需要验收的是可检查的结果，而不只是程序成功退出。FDE 存在多种用法，这里特指 Forward Deployed Engineering，不声称复现某个同名算法。来源、竞品和选题边界见[调研记录](docs/research-notes.md)。

后续研究需要补上真实模型对照实验，以及作者仓库中具体结果表的复现案例。欢迎贡献经过审阅、可重现的失败案例。当前代码使用 MIT 许可证，引用入口见 CITATION.cff。
