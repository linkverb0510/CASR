# CASR Milestone 1 报告

> 日期：2026-11-25
>
> 状态：Milestone 1 已完成。本文记录环境审计、文献核查和安全初始化；**没有运行模型实验、Benchmark 试跑或付费任务**。

## 1. 完成内容

1. 完整读取并核对两份 V1.0 研究文档，保持冻结方向不变：
   - 面向长程编码智能体的更正感知选择性修复；
   - Harness + Verifier；
   - Requirement State、Execution Provenance Graph、Selective Repair、Independent Verifier 四模块；
   - 当前不开展 DPO / Agentic RL。
2. 审计 Windows 软硬件、Python、Git、uv、Docker、GPU、模型 CLI 和模型配置存在性。
3. 检查父仓库与 CASR 目录，确认 CASR 初始为空，没有改动父仓库中的现有项目。
4. 核查 SWE-Interact、Harbor、StateHarness、AgentRewind、MettleBench、TRACE 的论文与官方仓库，记录许可证和适用边界。
5. 在 CASR 内初始化独立 Git 仓库、Python 3.12 虚拟环境和最小依赖环境。
6. 使用 TDD 实现环境审计脚本，验证 JSON 输出和密钥脱敏。
7. 生成两份原文档的逐字副本，并用 SHA-256 验证与原件一致。
8. 形成 Milestone 2 的最小原型实施计划。

## 2. 实际文件

| 文件 | 作用 |
|---|---|
| [README.md](../README.md) | 项目范围、环境命令、目录和复现规则 |
| [docs/research_problem.md](research_problem.md) | V1.0 研究问题文档逐字副本 |
| [docs/experiment_plan.md](experiment_plan.md) | V1.0 实验设计文档逐字副本 |
| [docs/related_work.md](related_work.md) | SWE-Interact 与相关工作的证据、许可证、差异和未知项 |
| [docs/milestone_1_report.md](milestone_1_report.md) | 本报告 |
| [docs/superpowers/plans/2026-11-25-casr-m2-prototype.md](superpowers/plans/2026-11-25-casr-m2-prototype.md) | Milestone 2 实施计划 |
| [research_log.md](../research_log.md) | 带日期的事实记录，区分已完成与计划工作 |
| [pyproject.toml](../pyproject.toml) | Python 包与最小依赖声明 |
| [uv.lock](../uv.lock) | 可复现依赖锁文件 |
| [.gitignore](../.gitignore) | 排除虚拟环境、密钥、原始数据、日志和结果 |
| [.env.example](../.env.example) | 模型配置模板，不含真实密钥 |
| [src/casr/environment.py](../src/casr/environment.py) | 环境与配置存在性审计 |
| [scripts/check_env.py](../scripts/check_env.py) | 审计 CLI 入口 |
| [tests/test_environment.py](../tests/test_environment.py) | 环境审计与密钥脱敏测试 |

文档副本哈希：

- `docs/research_problem.md`：`2d09436d9fc076838222dcf984cc8a5189b229d1b85300b75f431ca2242d0d1f`
- `docs/experiment_plan.md`：`7cb62d625f28a1a20cc6a26ec3ad42441614570b053afd10330272922ef14308`

两者均与 Downloads 中的原件一致。

## 3. 环境审计与实测结果

### 3.1 硬件与系统

| 项目 | 实测值 |
|---|---|
| OS | Windows 11，10.0.26200，x64 |
| CPU | Intel Core i9-13900H，14 核，20 逻辑处理器 |
| 内存 | 约 15.6 GiB；审计时空闲约 2.36 GB |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU，8188 MiB |
| 驱动 / CUDA | 驱动 595.71；`nvidia-smi` 报告 CUDA 13.2 |
| PyTorch | 2.11.0+cu130；`torch.cuda.is_available()` 为 True |
| 磁盘可用空间 | 约 31.5 GiB |

**判断：** 能满足轻量 Python 原型和小规模 API 实验；8 GB 显存和紧张的空闲内存不适合大模型训练，也不适合并行启动多个大型 Agent。第一阶段优先 API 模型或离线 scripted demo。

### 3.2 开发工具

| 项目 | 实测值 |
|---|---|
| Python | 3.12.0；另装有 3.10；项目固定使用 3.12 |
| Git | 2.56.0.windows.2 |
| uv | 0.11.7 |
| Docker | CLI 29.3.1；审计时 daemon 未运行 |
| Node | Shell 实测 v24.15.0 |
| 模型 CLI | Codex、Claude CLI 已安装 |
| 本地推理运行时 | 未检测到 Ollama、LM Studio、vLLM 命令 |

没有启动 Docker，没有安装 Harbor，没有下载 SWE-Interact 数据或大型模型。

### 3.3 项目虚拟环境

`uv sync` 后的核心版本：

- casr 0.1.0（editable）
- GitPython 3.2.1
- networkx 3.7
- pydantic 2.14.4
- pytest 9.2.0

项目环境没有引入 torch、pandas、LangChain 或 OpenAI SDK，避免最小原型依赖膨胀。

### 3.4 模型配置

只检查环境变量是否存在，未读取或输出值：

- `DEEPSEEK_API_KEY`：present
- `DASHSCOPE_API_KEY`：present
- OpenAI、Anthropic、Gemini、Google、Azure OpenAI、Hugging Face Token：absent

具体模型、网关、计费方式和预算尚未确认，因此没有调用任何模型 API。

### 3.5 Git 状态

- CASR 已初始化为独立嵌套仓库，分支 `main`，无 remote，尚无 commit。
- 父仓库为 `C:\Barsix\Learning_Repo`，其远端为 `https://github.com/linkverb0510/Zero_to_Hero.git`。
- 未修改、提交或推送父仓库内容。
- 按用户尚未明确要求提交的边界，本 Milestone 不自动创建 Git commit。

## 4. 验证结果

### 4.1 自动化测试

```text
uv run pytest -v
collected 3 items
tests\test_environment.py ... [100%]
3 passed
```

测试覆盖：

1. 本机运行时和依赖版本可读取；
2. 模型密钥只报告 present，不泄露值；
3. CLI 输出为合法 JSON 且不包含密钥值。

### 4.2 审计 CLI

```bash
uv run python scripts/check_env.py
```

实测输出包含 Python 3.12.0、CPU count 20、依赖版本和 present/absent 配置状态，没有输出任何秘密值。

### 4.3 实验状态声明

- 已完成：文档核对、环境审计、代码初始化、单元测试、文献核查。
- 正在进行：无。
- 计划中：Milestone 2 离线原型、10–15 个案例、B0–B4/Ours 对照、消融和验证器评测。
- **没有 CASR Benchmark 性能数据，也没有模型修复成功率数据。**

## 5. 文献与基准核查结果

详细证据见 [docs/related_work.md](related_work.md)。

| 资源 | 核查结论 | CASR 用途 |
|---|---|---|
| SWE-Interact | 75 个多轮任务；Apache-2.0；Harbor + Modal；原任务 verifier 验收 | 交互与评测骨架，不是现成选择性修复基准 |
| Harbor | Apache-2.0；支持 native/ATIF 轨迹；加载轨迹不恢复 sandbox 文件 | 轨迹和 verifier；CASR 需自建快照 |
| StateHarness | 项目状态、关系记录、影响候选检索；代码许可证未知 | B3 参照；不能自动假定需求版本传播 |
| AgentRewind | context + 工作区检查点恢复；MIT | B4 参照；整体回退不是选择性修复 |
| MettleBench | 82 个长程任务、640 条可执行验收；Apache-2.0 | 有序验收和部分进展的参考 |
| TRACE | 能力诊断 + LoRA/MoE 训练；MIT | 后续训练阶段参考，当前不使用 |

按 SWE-Interact 论文多轮 $6.10–$11.80/trial 外推，15 案例 × 6 组 × 3 次约为 $1,647–$3,186，另加 Modal。该估算未获报价确认，当前没有运行。

## 6. 问题与风险

1. **Docker daemon 未运行。** 当前不阻塞离线原型，但阻塞 Harbor/Modal 容器试跑。
2. **内存资源紧张。** 审计时空闲约 2.36 GB，不适合并行大型 Agent 或大型数据构建。
3. **本地推理运行时缺失。** 当前优先 API 或离线脚本，不启动本地大模型。
4. **API 模型和预算未确认。** 已存在的密钥不等于获得付费调用授权。
5. **StateHarness 代码许可证未知。** 只能作为论文和方法参照，不复制其代码。
6. **Harbor 轨迹加载不恢复文件。** 必须实现 CASR 自己的快照、Git revision 和恢复边界。
7. **SWE-Interact 不是完整 CASR 标注。** 需要补充四类更正、需求版本、影响范围、保留功能和 collateral edit 标注。
8. **一篇文献标题未确认。** “Long-Horizon Software Engineering Agents: From Tasks to Projects” 暂标 unknown。
9. **尚无真实 Agent 实验。** 当前测试只验证环境工具，不验证 CASR 方法有效性。

## 7. 技术选择与理由

| 选择 | 理由 | 潜在风险 |
|---|---|---|
| 独立嵌套 Git 仓库 | 与父仓库解耦，避免污染其他学习项目 | 用户可能希望改为 monorepo 子目录 |
| Python 3.12 + uv + lock | 环境可复现，依赖轻量 | 后续 Harbor 可能需要独立环境 |
| Pydantic | 明确数据边界和 JSON schema | 需防止模型字段过度膨胀 |
| NetworkX + JSON | 足以表达中小规模溯源图，易检查 | 大规模任务需要性能和索引优化 |
| GitPython + Git diff | 直接利用版本历史提取产物 | 同文件多需求需要 hunk 级标注 |
| 可执行测试优先 | 不依赖 Agent 自述 | 测试缺失时必须输出 UNKNOWN |
| 先离线 demo | 无 API 费用，先验证闭环和接口 | scripted demo 不能证明自主 Agent 效果 |

## 8. 下一步

按 [Milestone 2 实施计划](superpowers/plans/2026-11-25-casr-m2-prototype.md)：

1. 实现需求账本与四类更正；
2. 实现 Requirement–Action–Artifact–Evidence 图和 JSON 往返；
3. 从 Git diff 提取产物与基线；
4. 实现影响传播和四类修复决策；
5. 实现受控 executor 与 PASS/FAIL/UNKNOWN verifier；
6. 完成一个离线、无模型调用的端到端示例；
7. 验证后再设计 10–15 个真实案例和付费烟雾测试。

## 9. 待用户确认的决策

1. 是否保留当前**独立嵌套 Git 仓库**结构；目前没有 commit，也没有 remote。
2. 初步实验使用 **DeepSeek 或 DashScope** 的哪一个具体模型、网关和预算。
3. 是否批准 SWE-Interact + Harbor + Modal 的付费试跑；预计先做 1–3 个案例的烟雾测试，而不是直接启动 270 runs。
4. 是否接受“**先离线 scripted demo，再真实 Agent 实验**”的顺序。
5. 补充 “Long-Horizon Software Engineering Agents: From Tasks to Projects” 的链接或 PDF。

在这些决策确认前，可以安全推进的工作是 Milestone 2 的离线代码、测试和文档，不涉及付费调用或外部项目修改。
