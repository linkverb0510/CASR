# CASR Milestone 2 最小原型 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个无模型调用、可测试的 CASR 最小闭环：应用用户更正，传播影响，生成 Revert / Modify / Revalidate / Retain 决策，在隔离工作区执行修复，并独立验证新需求和保留功能。

**Architecture:** Pydantic 模型保存需求版本、动作、产物和证据；NetworkX 保存它们的关系；Git diff 提供产物基线；规则引擎完成影响分类；受控 executor 只修改隔离工作区；独立 verifier 用 argv 调用可执行测试并输出 PASS / FAIL / UNKNOWN。

**Tech Stack:** Python 3.12、Pydantic 2、NetworkX 3、GitPython、pytest、标准库 `subprocess` / `unittest`。

**Spec:** `docs/research_problem.md`、`docs/experiment_plan.md`、`docs/related_work.md`。

## Global Constraints

- 保持 Harness + Verifier 路线；不实现 DPO、Agentic RL、GUI Agent 或多 Agent 框架。
- 不调用模型 API，不访问外部网络，不下载 Benchmark 或大型数据。
- 所有修复只在临时工作区执行，不修改用户原始仓库。
- Revert / Modify 执行前必须保存工作区快照和 Git diff；快照目录必须位于工作区外，避免递归复制。
- 不允许 shell 字符串执行；测试使用 argv 列表和 `shell=False`。
- 路径必须位于工作区内；拒绝绝对路径、`..`、符号链接逃逸和未知修复操作。
- LLM 候选关系可以保存，但未经规则或人工核验的关系不得参与影响传播。
- 测试缺失、命令无法启动或超时均为 UNKNOWN，不得判为 PASS。
- 总体验证优先级：FAIL > UNKNOWN > PASS。
- 每个生产函数先写失败测试，再实现；每个任务结束运行完整测试套件。
- 不在本计划执行期间自动创建 Git commit；提交需要用户明确授权。

## Review Focus

1. **共享产物同时服务失效与 Active 需求**：不得 Revert；应进入 Modify 或 Revalidate。测试归属 Task 4。
2. **同文件包含有效与无效修改**：M2 只做文件级保守分类；共享文件不得整文件回滚，必须标记 Modify。测试归属 Task 4。
3. **未核验的 LLM 候选边**：不得扩大影响范围。测试归属 Task 2。
4. **缺失测试、超时或命令不存在**：必须 UNKNOWN，不能因其他测试通过而总体 PASS。测试归属 Task 5。
5. **恶意或越界路径与未知操作**：必须拒绝，且不能写出工作区。测试归属 Task 5。

---

## File Structure

- `src/casr/models.py`：Requirement、Action、Artifact、Evidence、Correction 和修复结果模型。
- `src/casr/ledger.py`：需求版本与 ADD / AMEND / REVOKE / SUPERSEDE 状态转换。
- `src/casr/provenance.py`：溯源图、关系校验和 JSON 往返。
- `src/casr/extraction.py`：Git revision 之间的文件级变化与 blob 基线提取。
- `src/casr/repair.py`：影响传播、修复分类和计划生成。
- `src/casr/executor.py`：隔离工作区中的受控 Revert / Modify 和快照。
- `src/casr/verifier.py`：可执行测试与 PASS / FAIL / UNKNOWN 报告。
- `scripts/demo_offline.py`：一个完整离线示例。
- `examples/offline_export/`：示例初始仓库、用户更正和修复 patch。
- `tests/`：每个任务的单元测试与端到端测试。

---

### Task 1: 数据模型与 Requirement Ledger

**Files:**

- Create: `src/casr/models.py`
- Create: `src/casr/ledger.py`
- Test: `tests/test_models.py`
- Test: `tests/test_ledger.py`

**Interfaces:**

- Consumes: 无。
- Produces:
  - `RequirementStatus = Literal["Active", "Superseded", "Revoked"]`
  - `CorrectionType = Literal["ADD", "AMEND", "REVOKE", "SUPERSEDE"]`
  - `RequirementVersion(requirement_id: str, version: int, content: str, status: RequirementStatus, created_at: datetime, superseded_by: str | None)`
  - `RequirementRecord(requirement_id: str, versions: list[RequirementVersion])`，属性 `current -> RequirementVersion`
  - `Correction(correction_id: str, correction_type: CorrectionType, target_requirement_id: str | None, new_requirement_id: str | None, content: str | None, created_at: datetime)`
  - `Action(action_id: str, action_type: str, description: str, timestamp: datetime, related_requirements: list[str], affected_artifacts: list[str], execution_result: str | None)`
  - `Artifact(artifact_id: str, path: str, baseline_blob: str | None, current_blob: str | None, produced_by: list[str], dependencies: list[str], evidence_ids: list[str])`
  - `Evidence(evidence_id: str, evidence_type: str, command: list[str], status: Literal["PASS", "FAIL", "UNKNOWN"], timestamp: datetime, related_requirements: list[str], related_artifacts: list[str], detail: str)`
  - `RequirementLedger.add_requirement(requirement_id: str, content: str, created_at: datetime) -> RequirementRecord`
  - `RequirementLedger.apply_correction(correction: Correction) -> RequirementRecord`
  - `RequirementLedger.active_requirements() -> list[RequirementVersion]`
  - `RequirementLedger.invalid_versions() -> list[RequirementVersion]`
  - `RequirementLedger.to_json() -> str`、`RequirementLedger.from_json(payload: str) -> RequirementLedger`

- [ ] **Step 1: 写模型校验的失败测试**

覆盖：空 ID、空需求内容、负数版本、非法状态、非法更正类型、Artifact 路径不是规范化 POSIX 相对路径时拒绝。

- [ ] **Step 2: 运行测试确认红灯**

Run: `uv run pytest tests/test_models.py -v`
Expected: 因模型不存在或校验未实现而失败。

- [ ] **Step 3: 实现 Pydantic 模型**

版本快照不可变；`RequirementRecord.current` 返回最后一个版本。Artifact 路径统一为 POSIX 风格，拒绝空路径、绝对路径和 `..`。

- [ ] **Step 4: 写 Ledger 状态转换的失败测试**

断言：

- ADD 创建新的 Active v1；
- AMEND 保留 `requirement_id`，旧版本标 Superseded，新版本为 Active 且 `version + 1`；
- SUPERSEDE 将目标标 Superseded 并设置 `superseded_by`，新 ID 从 Active v1 开始；
- REVOKE 保留 ID，追加 Revoked 版本；
- 目标不存在、重复 ID、AMEND 无内容、SUPERSEDE 无新 ID 均抛出 `ValueError`；
- JSON 往返后所有版本和状态一致。

- [ ] **Step 5: 运行测试确认红灯**

Run: `uv run pytest tests/test_ledger.py -v`
Expected: 因 Ledger 不存在而失败。

- [ ] **Step 6: 实现 Ledger**

只追加版本，不删除历史；`invalid_versions()` 返回所有非 Active 版本；`active_requirements()` 只返回每个 RequirementRecord 的当前 Active 版本。

- [ ] **Step 7: 运行本任务测试和完整套件**

Run: `uv run pytest tests/test_models.py tests/test_ledger.py -v`
Expected: PASS。
Run: `uv run pytest`
Expected: 全部 PASS。

---

### Task 2: Execution Provenance Graph

**Files:**

- Create: `src/casr/provenance.py`
- Test: `tests/test_provenance.py`

**Interfaces:**

- Consumes: Task 1 的所有模型。
- Produces:
  - `RelationType = Literal["Motivates", "Produces", "Depends-on", "Validates"]`
  - `RelationSource = Literal["git", "test", "manual", "llm"]`
  - `ProvenanceGraph.add_requirement_version(version: RequirementVersion) -> str`
  - `ProvenanceGraph.add_action(action: Action) -> str`
  - `ProvenanceGraph.add_artifact(artifact: Artifact) -> str`
  - `ProvenanceGraph.add_evidence(evidence: Evidence) -> str`
  - `ProvenanceGraph.add_relation(source_id: str, target_id: str, relation: RelationType, source: RelationSource, confidence: float, human_verified: bool) -> None`
  - `ProvenanceGraph.to_dict() -> dict[str, object]`、`ProvenanceGraph.from_dict(payload: dict[str, object]) -> ProvenanceGraph`
  - `ProvenanceGraph.impact_edges() -> list[tuple[str, str, dict[str, object]]]`

- [ ] **Step 1: 写图节点和关系的失败测试**

节点 ID 固定为：

- `requirement:{requirement_id}:v{version}`
- `action:{action_id}`
- `artifact:{artifact_id}`
- `evidence:{evidence_id}`

断言重复节点使用同一 ID 时更新数据；未知节点、非法关系、confidence 超出 `[0, 1]` 均拒绝。

- [ ] **Step 2: 运行测试确认红灯**

Run: `uv run pytest tests/test_provenance.py -v`
Expected: 因模块不存在而失败。

- [ ] **Step 3: 实现图写入与校验**

`Motivates` 只允许 Requirement → Action；`Produces` 只允许 Action → Artifact；`Depends-on` 只允许 Artifact → Artifact；`Validates` 只允许 Evidence → Requirement/Artifact。`Depends-on` 的语义固定为“源产物依赖目标产物”。

- [ ] **Step 4: 写 JSON 往返和候选边测试**

断言：

- 节点、边和边属性往返一致；
- `source="llm", human_verified=False` 的边保留在图中，但不出现在 `impact_edges()`；
- `source in {"git", "test", "manual"}` 或 `human_verified=True` 的边可用于影响传播；
- 序列化结果可用标准库 `json.dumps` / `json.loads` 处理。

- [ ] **Step 5: 实现序列化与影响边过滤**

使用 NetworkX node-link 数据；为保持可读性，JSON 中保存排序后的节点和边。不要使用图数据库。

- [ ] **Step 6: 运行本任务测试和完整套件**

Run: `uv run pytest tests/test_provenance.py -v`
Expected: PASS。
Run: `uv run pytest`
Expected: 全部 PASS。

---

### Task 3: Git Diff 与产物基线提取

**Files:**

- Create: `src/casr/extraction.py`
- Test: `tests/test_extraction.py`

**Interfaces:**

- Consumes: Task 1 的 `Artifact`。
- Produces:
  - `extract_git_changes(repo_path: Path, base_revision: str, correction_revision: str) -> list[Artifact]`
  - `normalize_repo_path(path: str) -> str`

- [ ] **Step 1: 写临时 Git 仓库的失败测试**

在 `tmp_path` 创建 Git 仓库和两个提交：

- 新增 `src/new.py`；
- 修改 `src/shared.py`；
- 删除 `src/removed.py`；
- 重命名 `src/old_name.py` → `src/new_name.py`。

断言返回四个 Artifact；新增文件 `baseline_blob is None`；删除文件 `current_blob is None`；修改文件两者均有值；所有路径为规范化相对路径。

- [ ] **Step 2: 运行测试确认红灯**

Run: `uv run pytest tests/test_extraction.py -v`
Expected: 因模块不存在而失败。

- [ ] **Step 3: 实现 Git 提取**

使用 GitPython 比较两个 revision 的 tree/diff；不调用 shell。重命名使用新路径，并在测试中明确该 M2 行为。无效 revision 抛出 `ValueError`。

- [ ] **Step 4: 写边界失败测试**

断言不存在的 revision 和包含 `..` 的提取结果被拒绝；空 diff 返回空列表。

- [ ] **Step 5: 运行本任务测试和完整套件**

Run: `uv run pytest tests/test_extraction.py -v`
Expected: PASS。
Run: `uv run pytest`
Expected: 全部 PASS。

---

### Task 4: 影响传播与选择性修复计划

**Files:**

- Create: `src/casr/repair.py`
- Test: `tests/test_repair.py`

**Interfaces:**

- Consumes: Task 1–3 的 Ledger、ProvenanceGraph、Artifact。
- Produces:
  - `RepairKind = Literal["Revert", "Modify", "Revalidate", "Retain"]`
  - `ImpactAnalysis(seed_artifacts: set[str], active_supported_artifacts: set[str], exclusive_invalid_artifacts: set[str], shared_artifacts: set[str], downstream_artifacts: set[str], unaffected_active_artifacts: set[str])`
  - `RepairDecision(kind: RepairKind, artifact_id: str, reason: str)`
  - `RepairPlan(correction_id: str, decisions: list[RepairDecision])`
  - `analyze_impact(graph: ProvenanceGraph, ledger: RequirementLedger, correction: Correction) -> ImpactAnalysis`
  - `RepairPlanner.plan(analysis: ImpactAnalysis, graph: ProvenanceGraph) -> RepairPlan`

- [ ] **Step 1: 写影响传播失败测试**

构造：

- 失效需求 R-old 促成 Action A-old；
- A-old 产生专属产物 `xml_helper`、共享产物 `exporter`；
- Active 需求 R-keep 也促成 `exporter` 和 `checksum`；
- `cli` 依赖 `exporter`；
- `unrelated` 依赖 `checksum`；
- 一个未核验 LLM 边连接 `unrelated`。

断言 seeds 为 `xml_helper` 和 `exporter`；shared 为 `exporter`；exclusive 为 `xml_helper`；downstream 包含 `cli`；未核验边不会把 `unrelated` 纳入下游。

- [ ] **Step 2: 运行测试确认红灯**

Run: `uv run pytest tests/test_repair.py::test_impact_propagation -v`
Expected: 因模块不存在而失败。

- [ ] **Step 3: 实现影响传播**

只沿 `impact_edges()` 遍历：

1. 从 `ledger.invalid_versions()` 的 Requirement 节点沿 `Motivates → Produces` 找 seed artifacts；
2. 从当前 Active 需求沿相同关系找 active-supported artifacts；
3. `exclusive = seeds - active_supported`；`shared = seeds & active_supported`；
4. 从 seeds 沿 `Depends-on` 的反向边找下游；
5. 未受影响且 active-supported 的产物进入 Retain 候选。

- [ ] **Step 4: 写修复分类失败测试**

断言：

- exclusive 且 `baseline_blob is None` 的新增产物 → Revert（删除）；
- exclusive 且有 baseline 的修改/删除产物 → Revert（恢复基线）；
- shared → Modify，绝不 Revert；
- downstream 且非 exclusive → Revalidate；
- unaffected active → Retain；
- exclusive 但缺少基线元数据 → Revalidate，不得猜测回滚；
- 同一产物只产生一个决策，优先级为 Modify > Revert > Revalidate > Retain。

- [ ] **Step 5: 运行测试确认红灯**

Run: `uv run pytest tests/test_repair.py::test_repair_classification -v`
Expected: 因 Planner 不存在而失败。

- [ ] **Step 6: 实现 Planner**

每个决策保存可解释 reason。M2 只做文件级保守分类；同文件多需求共享时必须 Modify，不尝试自动 hunk 级回滚。

- [ ] **Step 7: 运行本任务测试和完整套件**

Run: `uv run pytest tests/test_repair.py -v`
Expected: PASS。
Run: `uv run pytest`
Expected: 全部 PASS。

---

### Task 5: 受控 Executor 与 Independent Verifier

**Files:**

- Create: `src/casr/executor.py`
- Create: `src/casr/verifier.py`
- Test: `tests/test_executor.py`
- Test: `tests/test_verifier.py`

**Interfaces:**

- Consumes: Task 1 的 Artifact、Task 4 的 RepairPlan、Task 2 的 ProvenanceGraph。
- Produces:
  - `ExecutionRecord(decision_kind: RepairKind, artifact_id: str, status: Literal["applied", "skipped", "failed"], detail: str)`
  - `RepairExecutor(workspace: Path, graph: ProvenanceGraph).execute(plan: RepairPlan, patches: dict[str, bytes], snapshot_dir: Path) -> list[ExecutionRecord]`
  - `TestSpec(test_id: str, argv: tuple[str, ...], requirement_ids: list[str], retention: bool, timeout_seconds: float)`
  - `TestResult(test_id: str, status: Literal["PASS", "FAIL", "UNKNOWN"], return_code: int | None, duration_seconds: float, stdout: str, stderr: str, reason: str)`
  - `VerificationReport(results: list[TestResult])`，属性 `overall -> Literal["PASS", "FAIL", "UNKNOWN"]`
  - `IndependentVerifier().run(workspace: Path, specs: list[TestSpec]) -> VerificationReport`

- [ ] **Step 1: 写 Executor 失败测试**

在临时 Git 工作区中构造新增文件、修改文件和共享文件，断言：

- Revert 新增文件会删除；
- Revert 修改文件会恢复 baseline blob；
- Modify 只应用对应 patch；
- Retain / Revalidate 不修改文件；
- 执行前在 `snapshot_dir` 保存工作区文件和 `pre_repair.diff`；
- `../outside.txt`、绝对路径、符号链接逃逸和未知 decision kind 均拒绝，工作区外文件不变。

- [ ] **Step 2: 运行测试确认红灯**

Run: `uv run pytest tests/test_executor.py -v`
Expected: 因模块不存在而失败。

- [ ] **Step 3: 实现 Executor**

所有目标路径 resolve 后必须仍在 workspace 内。Revert 通过 Git ODB 读取 baseline blob；新增文件 baseline 为 None 时删除。Modify 使用 `git apply --check` 后应用，`shell=False`。任何失败写入 ExecutionRecord，不假装成功。

- [ ] **Step 4: 写 Verifier 失败测试**

断言：

- 返回码 0 → PASS；
- 返回码非 0 → FAIL；
- 命令不存在 → UNKNOWN；
- 超时 → UNKNOWN；
- stdout/stderr 限制最大 8000 字符；
- 有空 specs → UNKNOWN；
- 任一 FAIL 时 overall 为 FAIL；无 FAIL 但有 UNKNOWN 时为 UNKNOWN；全部 PASS 才为 PASS；
- 分别保留 `requirement_ids` 和 `retention` 字段，不能把新需求通过误报为保留功能通过。

- [ ] **Step 5: 运行测试确认红灯**

Run: `uv run pytest tests/test_verifier.py -v`
Expected: 因模块不存在而失败。

- [ ] **Step 6: 实现 Verifier**

使用 `subprocess.run(argv, cwd=workspace, shell=False, capture_output=True, timeout=...)`。测试命令视为可信实验配置，不经过 shell 拼接。超时和启动失败均为 UNKNOWN。

- [ ] **Step 7: 运行本任务测试和完整套件**

Run: `uv run pytest tests/test_executor.py tests/test_verifier.py -v`
Expected: PASS。
Run: `uv run pytest`
Expected: 全部 PASS。

---

### Task 6: 离线端到端 Demo 与文档收尾

**Files:**

- Create: `examples/offline_export/initial_repo/README.md`
- Create: `examples/offline_export/initial_repo/data/input.csv`
- Create: `examples/offline_export/agent_work/src/exporter.py`
- Create: `examples/offline_export/agent_work/src/xml_helpers.py`
- Create: `examples/offline_export/agent_work/src/cli.py`
- Create: `examples/offline_export/agent_work/src/checksum.py`
- Create: `examples/offline_export/agent_work/src/summary.py`
- Create: `examples/offline_export/agent_work/tests/test_xml_export.py`
- Create: `examples/offline_export/agent_work/tests/test_checksum.py`
- Create: `examples/offline_export/agent_work/tests/test_summary.py`
- Create: `examples/offline_export/correction.json`
- Create: `examples/offline_export/repair.patch`
- Create: `examples/offline_export/tests/test_json_export.py`
- Create: `scripts/demo_offline.py`
- Test: `tests/test_demo_offline.py`
- Modify: `README.md`

**Interfaces:**

- Consumes: Task 1–5 的全部接口。
- Produces:
  - `scripts/demo_offline.py --output-dir <path>`，默认 `results/offline_demo`；
  - 输出 `ledger.json`、`graph.json`、`impact.json`、`repair_plan.json`、`execution.json`、`verification.json`、`pre_repair.diff`；
  - 进程退出码：overall PASS 为 0，FAIL/UNKNOWN 为非 0。

- [ ] **Step 1: 写端到端失败测试**

测试调用脚本并断言：

- 初始需求为 XML 导出、checksum、summary；
- 更正 SUPERSEDE XML 为 JSON；
- 计划包含 Revert、Modify、Revalidate、Retain 四类决策；
- `exporter.py` 是 Modify，不是 Revert；
- `xml_helpers.py` 和 `test_xml_export.py` 被删除；
- `cli.py` 被 Revalidate；
- `checksum.py` 和 `summary.py` 被 Retain；
- JSON、checksum、summary 三个测试组均 PASS，overall 为 PASS；
- 原始 fixture 未被修改。

- [ ] **Step 2: 运行测试确认红灯**

Run: `uv run pytest tests/test_demo_offline.py -v`
Expected: 因脚本和 fixture 不存在而失败。

- [ ] **Step 3: 创建离线 fixture**

示例数据只使用 CSV 和标准库。`initial_repo` 只包含 README 和输入 CSV；`agent_work` 覆盖层产生 XML 导出、checksum、summary 和 CLI。用户更正为：“不再输出 XML，改为标准库 JSON；checksum 和 summary 必须保留。” 修复 patch 只修改 `exporter.py` 并加入 JSON 测试。

- [ ] **Step 4: 实现脚本**

脚本必须：

1. 将 `initial_repo` 复制到临时工作区并创建 base commit；
2. 将 `agent_work` 覆盖层复制到同一工作区并创建 pre-correction commit；
3. 从 base 到 pre-correction 提取 Artifact；
4. 构建需求、动作、产物和人工核验关系图；
5. 应用 SUPERSEDE 更正；
6. 生成影响分析和修复计划；
7. 在另一个隔离副本中先快照，再执行 Revert / Modify；
8. 用 `python -m unittest` 分别运行 JSON 新需求和 checksum/summary 保留测试；
9. 写出全部 JSON 和 diff；
10. 在输出中明确标记 `demo_type="scripted_harness_demo"`，不得称为自主 Agent 实验。

- [ ] **Step 5: 运行端到端测试**

Run: `uv run pytest tests/test_demo_offline.py -v`
Expected: PASS。

- [ ] **Step 6: 手动运行并检查产物**

Run: `uv run python scripts/demo_offline.py --output-dir results/offline_demo`
Expected: 退出码 0；`verification.json` 的 overall 为 PASS；四类决策均出现。

- [ ] **Step 7: 更新 README 并运行最终验证**

在 README 增加离线 demo 命令、输出说明和“scripted demo 不等于 CASR 实验结论”的声明。

Run: `uv run pytest`
Expected: 全部 PASS。
Run: `uv run python scripts/check_env.py`
Expected: 合法 JSON，无秘密值。
Run: `git status --short --branch`
Expected: 只包含本计划新增或修改的文件，没有 `.env`、密钥、大型数据或意外生成物。

---

## Acceptance Criteria

- [ ] 四类更正均有单元测试和明确状态转换。
- [ ] 图可 JSON 往返；未核验 LLM 候选边不参与传播。
- [ ] Git diff 能提取新增、修改、删除和重命名产物及基线。
- [ ] 共享产物不会被 Revert；下游影响会触发 Revalidate。
- [ ] Executor 只能操作隔离工作区，越界路径和未知操作被拒绝。
- [ ] Verifier 明确区分 PASS / FAIL / UNKNOWN，并分别记录新需求和保留功能。
- [ ] 离线 demo 完整展示 Revert / Modify / Revalidate / Retain。
- [ ] 完整测试套件通过，环境审计不泄露密钥。
- [ ] 没有调用模型 API，没有运行付费任务，没有修改用户原始仓库。
- [ ] 文档明确：M2 只证明最小闭环可运行，不证明方法优于基线。

## Explicit Non-Goals

- 不实现自主模型调用或用户模拟器。
- 不实现跨文件 AST 级依赖分析或同文件 hunk 级自动修复。
- 不实现 Harbor / Modal 集成。
- 不构建 10–15 个真实案例或运行 B0–B4/Ours。
- 不实现 DPO / Agentic RL。
- 不把 scripted demo 的结果写成 Benchmark 性能或科研结论。
