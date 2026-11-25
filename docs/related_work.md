# CASR 相关工作与基准核查

> 核查日期：2026-11-25。本文区分论文/官方仓库可核实的事实、对 CASR 的适用性判断和仍未知的事项。未运行这些系统的实验，也未复现其论文结果。

## 1. 结论摘要

- **SWE-Interact** 适合提供交互式任务、用户模拟器、轨迹和可执行验收的骨架，但不是现成的 CASR 选择性修复基准。
- **StateHarness** 与 B3 最接近：维护项目状态、关系记录和变更影响候选，但没有以用户更正为中心的需求版本传播和 Revert/Modify/Revalidate/Retain 决策。
- **AgentRewind** 与 B4 最接近：对齐恢复 Agent 上下文和工作区检查点，但主要是失败后的整体回退，不是保留有效工作的选择性修复。
- **TRACE** 属于能力诊断与训练方向，不是当前 Harness + Verifier 阶段的直接基线；只有在验证器和数据可靠后才考虑相关训练路线。
- CASR 需要补充的关键能力是：**显式需求状态、跨动作/产物/证据的溯源、按依赖分类的选择性修复，以及新需求与保留功能的同时验证**。

## 2. SWE-Interact

### 可核实事实

- 论文：[SWE-Interact: Reimagining SWE Benchmarks as User-Driven Long-Horizon Coding Sessions](https://arxiv.org/abs/2606.30573)，arXiv:2606.30573，2026-06-29。
- 官方仓库：[scaleapi/SWE-Interact](https://github.com/scaleapi/SWE-Interact)，Apache-2.0。
- 论文和仓库均说明共有 **75 个多轮任务**：DeepSWE 25、SWE Atlas Refactoring 25、SWE-bench Pro 25。
- 用户模拟器从模糊或不完整任务开始，检查工作区，逐步提供反馈、修订和新约束。
- 任务在 Harbor + Modal 的容器沙箱中执行；Agent 通过 `ask_user` 与用户模拟器交互。
- Agent 需要保存初始计划、响应用户反馈的实现修订和最终测试 patch；最终成绩由原任务 verifier 判定，而不是由模拟用户批准。
- 论文 Table 1 中，多轮任务的已报告 `cost/trial` 为 $6.10–$11.80，具体取决于模型；该表没有把 Modal 费用作为单独报价。
- 论文说明首版用户模拟器只能使用 `git`、`grep`、`sed`、`find` 等只读检查命令，不能修改代码或运行测试。

### 对 CASR 的适用性

**适合复用：**

1. Harbor 的任务、用户模拟器和 verifier 接口；
2. 多轮用户消息、实现修订和测试 patch；
3. 原任务的可执行验收测试；
4. 轨迹中的工具调用、观察结果和成本记录。

**不能直接假定：**

1. 每次反馈都是显式的 ADD / AMEND / REVOKE / SUPERSEDE；
2. 已有完整的 Active / Superseded / Revoked 需求状态；
3. 能恢复任意用户更正前的工作区；
4. 已有跨文件或同文件 hunk 级的影响标注；
5. 已有“仍然适用的旧功能”保留测试；
6. 已有旧计划复发、不必要修改和修复成本的统一标注。

### Harbor 轨迹与恢复边界

- Harbor 官方 ATIF 文档说明 `agent/trajectory.json` 记录消息、推理、工具调用、观察结果和指标，可用于渲染、校验和加载会话：[ATIF](https://docs.harborframework.com/agents/atif)。
- Harbor 官方加载文档明确说明：原生加载恢复原生会话，ATIF 加载恢复可移植的对话内容，**两者都不恢复 sandbox 文件**：[Loading trajectories](https://docs.harborframework.com/jobs/loading-trajectories)。
- Harbor 示例 verifier 会把基线提交到当前工作区的二进制 diff 写入 `/logs/artifacts/model.patch`。这说明 patch 可作为产物证据，但不能替代 CASR 的工作区快照和状态恢复。
- 因此，CASR 若采用 Harbor，必须额外记录 Git revision、工作区快照、需求版本和每轮测试证据。

### 成本与准入判断

以论文多轮 `cost/trial` 的量级外推：

- 15 案例 × 6 组 × 3 次 = 270 runs；
- 仅模型费用约为 **$1,647–$3,186**，另加 Modal、重试和本机开销。

这只是基于论文数字的量级估算，不是供应商报价，也不是已发生费用。当前不批准也不启动该付费试跑；先完成离线原型和少量单案例烟雾测试，再决定是否扩大。

## 3. StateHarness

- 论文：[StateHarness: Maintaining Evolving Project State for Long-Horizon Coding Agents](https://arxiv.org/abs/2610.17616)，arXiv:2610.17616，2026-10-13。
- 论文给出的代码入口：[anonymous.4open.science/r/StateHarness](https://anonymous.4open.science/r/StateHarness)。
- **许可证：未知。** 本次没有从可验证的官方许可证文件确认代码许可，不能据此复制或再分发代码。

论文明确描述：

- 持久记录包括 task state、event log、relation notes、procedure guidance，并生成 compact working brief；
- 对签名变更、整文件替换和源文件删除等操作检索 caller、test、documentation 等候选位置；
- 检索结果是候选，不是自动确认的依赖；工作 Agent 需要判断并记录后续处理；
- 完成前要求重新检查关系、原复现命令和相关测试；
- 任务结果由 benchmark tests 或外部 verifier 判定，而不是 Agent 自述。

**与 CASR 的关系：** 可作为 B3 的状态维护和影响检索参照。差异在于 StateHarness 以“随执行演进的项目理解”为中心，而 CASR 以“用户更正导致的需求状态变化”为触发器，并要求将影响分类为 Revert、Modify、Revalidate、Retain。

**风险：** 论文也报告状态维护带来运行时开销，并在 ChainSWE 上出现 pass-to-pass regression 增加。这说明仅增加状态记录不能自动保证功能保留。

## 4. AgentRewind

- 论文：[AgentRewind: Recoverable Execution for Long-Horizon LLM Agents](https://arxiv.org/abs/2608.14380)，arXiv:2608.14380，2026-08-14。
- 官方代码：[Futuresis/replay-agent-recorder](https://github.com/Futuresis/replay-agent-recorder)，MIT。
- 数据集：[Kelvin-Coffee/MettleBench](https://github.com/Kelvin-Coffee/MettleBench)，Apache-2.0。

论文明确描述：

- 在 Agent context 和受控环境状态之间记录对齐检查点；
- 回退时恢复早先上下文和工作区文件，并注入 rewind memory；
- 可恢复工作区文件修改、删除和新增；
- 网络请求、外部服务调用和外部运行时状态不能撤销；
- MettleBench 使用有序、相互依赖的可执行验收条目评价任务完成和部分进展。

**与 CASR 的关系：** 可作为 B4 Checkpoint Rewind 和快照组件的参照，但整体回退可能丢弃仍然有效的工作。CASR 的选择性修复需要进一步判断哪些历史产物应撤销、修改、重验或保留。

## 5. TRACE

- 论文：[TRACE: Capability-Targeted Agentic Training](https://arxiv.org/abs/2604.05336)，arXiv:2604.05336，v2 2026-07-02。
- 官方代码：[ScalingIntelligence/TRACE](https://github.com/ScalingIntelligence/TRACE)，MIT。

论文明确描述：对比成功和失败轨迹以识别能力缺口，合成针对性训练环境，训练 LoRA adapter，再组合为 MoE。它没有以需求版本、用户更正影响传播或选择性工作区修复为核心问题。

**与 CASR 的关系：** 不是当前阶段直接基线。其失败轨迹分析思路可在后续 Verifier-Guided DPO / Agentic RL 阶段参考；当前不开展训练。

## 6. 对照定位

| 方法 | 需求状态 | 动作/产物溯源 | 工作区恢复 | 用户更正触发选择性修复 | 对新旧需求的同时验证 |
|---|---|---|---|---|---|
| SWE-Interact | 渐进披露，但无显式状态机 | 有会话、修订和轨迹 | Harbor 轨迹加载不恢复文件 | 不是主要贡献 | 原任务 verifier；无系统化保留验证 |
| StateHarness | 项目状态记录，非需求版本状态机 | 有关系记录和候选影响检索 | 论文未以此为核心 | 未形成 CASR 四类修复决策 | 外部测试，但论文报告仍有回归 |
| AgentRewind | 无专门需求账本 | 有 context/environment 对齐检查点 | 有工作区文件级回退 | 失败恢复，不是用户更正选择性修复 | MettleBench 可执行验收 |
| TRACE | 训练能力诊断 | 轨迹对比 | 不是核心恢复框架 | 不是核心问题 | 以环境和任务指标为主 |
| CASR（计划） | Active / Superseded / Revoked + 版本 | Requirement–Action–Artifact–Evidence 图 | 自建快照；选择性应用修复 | 核心问题 | 新需求 + 保留功能 + UNKNOWN |

> “不是主要贡献”或“未形成”表示在本次核查的论文描述中未找到对应机制，不等于断言作者代码在任何版本都绝对没有该功能。

## 7. 待确认文献

原始研究文档提到 “Long-Horizon Software Engineering Agents: From Tasks to Projects”。本次精确标题检索未找到可确认的权威论文、DOI 或 arXiv 条目，因此标记为 **unknown**，不作为已核实参考文献，也不据此形成技术结论。需要作者提供链接或 PDF 后再补录。

## 8. CASR 的最小差异化定位

CASR 不以“增加 Memory、Ledger 或依赖图”本身作为充分创新，而是检验一个更具体的闭环：

1. 用户更正使哪些需求版本失效；
2. 失效需求通过哪些历史动作影响哪些产物；
3. 哪些产物同时仍服务 Active 需求，不能直接回滚；
4. 下游产物哪些只需重新验证；
5. 修复后是否同时满足新需求和保留功能；
6. 与 Full History、Requirement Ledger、State/Impact Harness、整体回滚相比，是否减少回归和不必要修改。

该定位仍是待实验检验的假设，不是已证明的贡献。
