# CASR M2 开发日志

> 开始时间：2026-11-25
>
> 目标：按现有 M2 计划完成 Harness + Verifier 最小闭环，记录问题、成果、决策和实验证据；不调用模型 API，不把 scripted demo 当作科研结论。

## 执行约定

- 开发期间仓库没有首个 Git 提交，因此直接新增文件；用户后续授权开源推送，最终统一提交并发布。
- 使用 TDD：每个生产模块先写失败测试，观察预期红灯，再实现到绿灯。
- 所有修复在临时工作区执行，不修改用户原始仓库。
- 集群复用官方 CPU-only Jupyter 作业，运行与本地相同的测试和 demo；不申请 GPU。
- 本日志同时作为执行 ledger；任务完成后记录真实命令与结果。

## 预检与决策

- 研究文档 SHA-256 未变：`research_problem.md=2d09436d...`，`experiment_plan.md=7cb62d62...`。
- Task 1→2：模型 ID 字段与图节点 ID 前缀一致，无冲突。
- Task 1→4：账本保留所有非 Active 版本，影响分析可定位旧需求促成的工作，无冲突。
- Task 2→4：`Depends-on` 固定为“源产物依赖目标产物”，反向遍历得到下游，无冲突。
- Task 3→5：Artifact 同时保存 baseline/current blob，Revert 可恢复基线或删除新增文件，无冲突。
- Ruling：不创建 Git worktree/commit — 仓库尚无初始提交且用户未授权提交 — 成本：缺少按任务回滚点，依靠测试与开发日志恢复。
- Ruling：账本替换 `RequirementRecord` 对象，调用方通过 `get()` 查询最新状态 — 保持版本快照不可变 — 成本：持有旧对象引用的调用方可能看到旧状态。

## 任务进度

- [x] Task 1：数据模型与 Requirement Ledger
- [x] Task 2：Execution Provenance Graph
- [x] Task 3：Git Diff 与产物基线提取
- [x] Task 4：影响传播与选择性修复计划
- [x] Task 5：受控 Executor 与 Independent Verifier
- [x] Task 6：离线端到端 Demo 与文档
- [~] 集群复验与结果收集（早期 CPU smoke 已通过；M2 作业已停止，最新页面报错）
- [x] MVP 完成审计与独立审查

## 工作记录

### 2026-11-25 — Task 1 开始

- 已读 M2 计划与两份冻结研究文档。
- 当前仅有环境检查和集群脚本，M2 核心模块尚未实现。
- 下一步：先写模型与账本失败测试。

### 2026-11-25 — Task 1 完成

- 红灯：`casr.models` / `casr.ledger` 不存在，测试收集失败，符合预期。
- 实现：不可变需求版本、四类更正、JSON 往返、路径规范化校验。
- 问题：AMEND 初始实现漏标旧版本 Superseded；定向测试发现后修复。
- 验证：定向 28 passed；完整套件 44 passed。
- 成果：`src/casr/models.py`、`src/casr/ledger.py` 及对应测试。

### 2026-11-25 — Task 2 完成

- 红灯：`casr.provenance` 不存在，测试收集失败，符合预期。
- 实现：四类节点、受限关系、JSON 往返、候选边过滤。
- 问题：测试误把排序后的首节点当作需求节点，并误解三元组影响边；修正断言，同时让影响边顺序稳定。
- 验证：定向 7 passed；完整套件 51 passed。
- 关键约束：未核验 LLM 边保留在图中，但不参与影响传播。

### 2026-11-25 — Task 3 完成

- 红灯：`casr.extraction` 不存在，测试收集失败，符合预期。
- 实现：Git revision 比较、四类文件变化、blob 基线、规范化相对路径。
- 验证：定向 7 passed；完整套件 58 passed。
- 边界：重命名使用新路径，同时保留旧 blob 作为恢复基线；非法 revision 拒绝。

### 2026-11-25 — Task 4 进行中

- 红灯：`casr.repair` 不存在，测试收集失败，符合预期。
- Ruling：影响播种按失效需求 ID 聚合所有版本节点 — REVOKE 新增 Revoked 版本，但动作仍关联旧版本，只按非 Active 版本会漏传播 — 成本：可能重新检查同一需求早期版本关联的产物，但不会漏掉失效工作。
- 问题：图节点 ID 与业务 artifact ID 前缀不一致，已在分析边界统一。
- 验证：定向 3 passed；完整套件 61 passed。
- 结果：共享 exporter→Modify、专属 xml_helper→Revert、下游 cli→Revalidate、Active checksum→Retain。

### 2026-11-25 — Task 5 完成

- 红灯：`casr.executor` / `casr.verifier` 不存在，测试收集失败，符合预期。
- 实现：工作区外快照、Git diff、blob 恢复、受控 patch、PASS/FAIL/UNKNOWN。
- 问题：GitPython ODB 需要二进制 SHA；未知决策需绕过 Literal 校验以记录失败，均已修复。
- 验证：定向 7 passed、2 skipped（Windows 符号链接权限）；完整套件 70 passed、2 skipped。
- 安全边界：绝对路径、`..`、符号链接逃逸、工作区内快照、未知操作均拒绝。

### 2026-11-25 — Task 6 与 MVP 合成实验

- 离线 Demo：PASS；决策为 Revert 2、Modify 1、Revalidate 1、Retain 2；JSON/checksum/summary 三组测试全 PASS。
- 问题：临时 Git 仓库句柄导致 Windows 清理失败；显式关闭 Repo 后修复。fixture 的 checksum 测试曾错误假设顺序无关，已改为真实的稳定性断言。
- 合成实验：3 案例 × 3 策略，共 9 次；不修复 0/3 成功，整体重建 3/3，CASR 3/3。
- 关键结果：整体重建平均写 14 个路径、重写 12 个保留模块；CASR 平均写 2 个路径、重写 0 个保留模块。
- 边界：这是 synthetic harness policy experiment，不是自主 Agent Benchmark；单次运行，不能宣称统计显著或方法普遍优越。
- 产物：`results/offline_demo/`、`results/mvp_experiment/`（本地 ignored，报告中保留摘要与复现命令）。
- 集群同步白名单已加入 `examples` 与 `experiments`，确保远程可运行 Demo 和实验。

### 2026-11-25 — 溯源保真度消融与交付整理

- 新假设：图漏记主要损害正确性，伪依赖主要扩大复核范围。
- 新实验：3 案例 × 3 图条件，共 9 次；完整图 3/3 成功，漏记需求→动作溯源 0/3，加入伪依赖 3/3。
- 机制证据：伪依赖把平均 Revalidate 从 1 增至 2、Retain 从 6 降至 5；漏溯源不产生 Modify/Revert，所以新需求测试失败。
- 修复：ADD 更正不再调用 `ledger.get(None)`；现有 Active 产物保持不受影响。
- Ruling：把本轮小型实验的原始结果、配置、清单和元数据加入 Git 白名单 — 用户要求完整保存复现材料 — 成本：仓库增加约 220 KiB 文本证据。
- 集群：早期 1 CPU/2 GiB/0 GPU smoke 已真实通过；本轮 M2 复验尝试时旧 Jupyter 作业已停止，页面显示 `Something went wrong!`，随后访问平台首页连接超时，未伪造远程 M2 结果。
- 独立审查：已完成一次 fresh-context 只读审查，不重复审查。

### 2026-11-26 — 独立审查集中修复

- 审查发现：快照可能跟随符号链接并复制秘密文件；Revert 未恢复 Git mode/type；artifact 路径可能被当作 patch glob；溯源 JSON 类型校验不足；ADD/AMEND 存在跨版本误播种；整体重建漏计基线文件写入；实验措辞外推过强。
- TDD 红灯：首轮 10 failed、33 passed、3 skipped；集中修复后 5 failed、40 passed、3 skipped，剩余为 Git mode 类型和 provenance 校验顺序。
- 补充红灯：伪造 `impact_eligible=true` 的未核验 LLM 边可绕过 JSON 校验；新增回归测试确认 DID NOT RAISE 后修复。
- 修复：快照保留 symlink 且排除 `.env`/密钥；拒绝 glob 路径；恢复 blob、文件类型和可执行 mode；严格校验 provenance 节点、边来源、bool 与 impact 派生值；ADD 不重新播种历史失效需求；AMEND 只处理目标版本；非 Active 需求不可再次转移；Git mode 的 `0` 映射为 None。
- 验证：`uv run pytest -q --tb=short -o addopts=''` → **82 passed、3 skipped in 53.18s**；日志保存在 `logs/review-fix-20261126/pytest.log`。
- Ruling（deferred minor）：unittest 发现 0 个测试时仍可能判 PASS；当前 TestSpec 由受信配置生成，空 argv 集合已判 UNKNOWN，故本轮不扩大验证器接口，留待真实 Benchmark 验证器契约阶段处理；成本：错误配置的 unittest 命令可能产生假 PASS。
- 公开前脱敏：账号、用户名、内网地址、作业标识、公钥指纹和本机用户路径替换为占位符，保留连接机制与真实执行结论。
- 补充 TDD：验证器原始失败输出会泄露本机用户目录；新增路径脱敏测试观察红灯后，在输出边界将工作区与用户目录替换为 `<workspace>` / `<user-home>`，保留错误类型与相对路径。
- 最终复现：修复提交 `0bf2a02` 上重跑 Demo（PASS）、策略实验（CASR 3/3、整体重建 3/3、不修复 0/3）和溯源消融（完整 3/3、漏溯源 0/3、伪依赖 3/3）；两份实验元数据均绑定该提交且源码脏标记为 false。
- Ruling：实验 `working_tree_dirty` 只检查源码、测试、配置与锁文件，不检查结果自身 — 避免写入结果必然造成脏标记 — 成本：文档或 `.gitignore` 的未提交改动不会反映在该字段中。
