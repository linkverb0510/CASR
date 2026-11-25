# CASR MVP 报告

> 日期：2026-11-26
> 状态：可运行的 Harness + Verifier MVP；结论限于离线合成实验。  
> 开源仓库：https://github.com/linkverb0510/CASR
> 本报告不包含模型 API 调用、真实 Coding Agent Benchmark 结果或统计显著性声称。

## 1. 研究问题

当用户在中途修正、替代或撤销需求时，长程编码智能体应如何只修复受影响的历史工作，同时保留仍然有效的功能？

CASR 的核心假设是：把需求版本、动作、产物和证据组织为可审计的依赖关系，可以比“不修复”更正确，比“整体重建”更少改写保留产物。

## 2. 已实现的最小原型

| 模块 | 能力 | 代码入口 |
|---|---|---|
| Requirement State | ADD / AMEND / SUPERSEDE / REVOKE，保留不可变版本历史 | `src/casr/ledger.py` |
| Provenance Graph | Requirement / Action / Artifact / Evidence 四类节点与受限关系 | `src/casr/provenance.py` |
| Git Recovery | 从两个 revision 提取新增、修改、删除、重命名及 blob 基线 | `src/casr/extraction.py` |
| Selective Repair | Revert / Modify / Revalidate / Retain，沿依赖反向传播 | `src/casr/repair.py` |
| Isolated Execution | 工作区外快照、路径逃逸拒绝、受控 Git patch、blob 恢复 | `src/casr/executor.py` |
| Independent Verifier | argv 执行、超时处理、PASS / FAIL / UNKNOWN 独立判定 | `src/casr/verifier.py` |

安全不变量：未核验的 LLM 关系边保留在图中，但不参与影响传播；验证器不采信 Agent 自述；空验证集合为 UNKNOWN；FAIL 优先于 UNKNOWN，UNKNOWN 优先于 PASS。

## 3. 离线 Demo

`examples/offline_export` 模拟“XML 导出改为 JSON，checksum 和 summary 必须保留”。实际执行结果为：

- 总体 PASS；`model_api_called=false`。
- exporter：Modify。
- xml_helpers 与旧 XML 测试：Revert。
- cli：Revalidate。
- checksum 与 summary：Retain。
- 三组独立测试全部 PASS。

完整证据位于 `results/offline_demo/`，包括账本、图、影响集、计划、执行记录、验证报告和修复前 diff。

## 4. 实验一：修复策略对照

### 设计

- 3 个案例：保留模块数分别为 2、4、6。
- 3 个策略：不修复、整体重建、CASR 选择性修复。
- 共 9 次运行；每个策略使用相同独立验收测试。
- 指标：新需求通过率、保留功能通过率、联合成功率、写入路径数、保留模块重写数。
- 配置：`experiments/mvp_synthetic.json`。

### 实际结果

| 策略 | 联合成功 | 新需求 PASS | 保留功能 PASS | 平均写入路径 | 保留模块重写总数 |
|---|---:|---:|---:|---:|---:|
| no_repair | 0/3 | 0/3 | 3/3 | 1.0 | 0 |
| full_rebuild | 3/3 | 3/3 | 3/3 | 14.0 | 12 |
| casr_selective | 3/3 | 3/3 | 3/3 | 2.0 | 0 |

### 解释

在该模板化设定中，选择性修复达到了与整体重建相同的验收结果，同时没有改写任何保留模块。这是对 Harness 决策机制的支持，不是对自主 Agent 或真实软件项目的性能证明。整体重建还使用了已知正确实现，未模拟重新发现需求和编写代码的成本。

## 5. 实验二：溯源图保真度消融

### 假设

漏记溯源会损害修复正确性；伪依赖主要扩大复核范围，而不一定导致错误。

### 设计

同样 3 个案例，分别使用：

1. `complete`：完整人工图。
2. `missing_provenance`：删除 XML 需求到导出动作的 Motivates 边。
3. `spurious_dependency`：加入 checksum 依赖 exporter 的伪 Depends-on 边。

共 9 次运行。记录修复成功率、Modify/Revert 是否发生、Revalidate/Retain 数量和写入路径数。配置：`experiments/graph_ablation.json`。

### 实际结果

| 图条件 | 联合成功 | 平均决策数 | 平均 Revalidate | 平均 Retain | 平均写入路径 |
|---|---:|---:|---:|---:|---:|
| complete | 3/3 | 9.0 | 1.0 | 6.0 | 2.0 |
| missing_provenance | 0/3 | 7.0 | 0.0 | 7.0 | 1.0 |
| spurious_dependency | 3/3 | 9.0 | 2.0 | 5.0 | 2.0 |

### 解释与负面结果

漏溯源案例没有产生 Modify 或 Revert，因此旧实现继续存在，新需求测试失败。伪依赖案例仍通过测试，但把 checksum 从 Retain 推到 Revalidate，扩大了复核范围。

这给出一个可检验的研究方向：**在该构造性合成设定中，修复正确性对溯源漏记敏感，而伪依赖主要增加复核范围。** 这提示应优先检验真实轨迹中的溯源召回，但当前结果不能证明其在真实项目中是主要瓶颈。

## 6. 复现

环境要求：Python 3.12、Git、`uv`。最终本地验证为 **82 passed、3 skipped**；3 项跳过均为 Windows 平台限制。最终实验元数据绑定代码提交 `0bf2a02c9350f71469ffdcbcd8402ca39dd095c1`，源码与配置范围 `working_tree_dirty=false`。

```bash
uv sync
uv run pytest -q
uv run python scripts/demo_offline.py --output-dir results/offline_demo
uv run python scripts/run_mvp_experiment.py \
  --config experiments/mvp_synthetic.json \
  --output-dir results/mvp_experiment
uv run python scripts/run_graph_ablation.py \
  --config experiments/graph_ablation.json \
  --output-dir results/graph_ablation
```

保存的原始结果：

- `results/offline_demo/`
- `results/mvp_experiment/raw_results.json`、`case_manifests.json`、`results.csv`、`summary.json`、`run_metadata.json`、`config.json`
- `results/graph_ablation/raw_results.json`、`results.csv`、`summary.json`、`run_metadata.json`、`config.json`

集群方面，早期 1 CPU / 2 GiB / 0 GPU Jupyter smoke 已通过；本轮 M2 复验尝试时旧作业已停止，页面显示 `Something went wrong!`。因此没有声称最新 M2 已在 Linux 集群复验。

## 7. 限制

1. 案例共享同一模板，只改变保留模块数量；没有真实项目多样性。
2. 修复补丁和图关系由脚本或人工给定，不是自主 Agent 的产出。
3. 单次运行，无统计显著性检验；Revalidate 的实际人工成本未测量。
4. 没有调用 DeepSeek API，没有运行 SWE-Interact 或其他真实 Benchmark。
5. Windows 跳过 3 项平台相关测试（符号链接与 POSIX 可执行模式）；Linux 集群未完成最新 M2 复验。
6. 当前结果不能支持“CASR 普遍优于整体重建”或“可替代训练”的结论。

## 8. 下一步研究优先级

1. 在真实长程 Agent 轨迹上测量需求→动作→产物溯源召回，区分可恢复错误与不可恢复错误。
2. 加入多模板、多更正类型和独立保留测试，重复运行并报告区间或显著性。
3. 对 UNKNOWN/Revalidate 引入实际复核成本，比较“少改写”与“多复核”的权衡。
4. 只有在数据和验证器可靠性达标后，才考虑使用轨迹训练或强化学习改进策略。

## 9. 结论

CASR MVP 已形成可运行、可复现的闭环，并在合成实验中同时得到正面结果和明确的失败条件。当前最有价值的发现是：选择性修复的收益依赖高质量溯源；漏溯源会直接破坏正确性，而伪依赖首先消耗复核预算。下一步应优先验证真实轨迹上的溯源召回，而不是急于扩大模型或训练规模。
