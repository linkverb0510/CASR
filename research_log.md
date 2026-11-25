# CASR 研究日志

> 规则：只记录可复核事实。计划、推断和实验结果分开；未运行的实验不得写成结果。

## 2026-11-25 — Milestone 1：审计与初始化

### 目标

核对冻结研究文档，审计本地资源，核查 SWE-Interact 与相关工作，安全初始化项目并形成第一版技术实施计划。

### 已完成事实

- 读取两份 V1.0 文档并生成逐字副本；SHA-256 与原件一致。
- 实测 Windows 11、Python 3.12.0、Git 2.56.0、uv 0.11.7、RTX 4060 Laptop 8 GB、约 15.6 GiB 内存和约 31.5 GiB 可用磁盘。
- Docker CLI 存在，但审计时 daemon 未运行；未启动 Docker。
- 检测到 DeepSeek 与 DashScope 配置存在；只记录 present/absent，未读取或输出密钥值。
- CASR 初始目录为空；已建立独立嵌套 Git 仓库，分支 main，无 remote，无 commit；父仓库未修改。
- 安装最小依赖：GitPython 3.2.1、networkx 3.7、pydantic 2.14.4、pytest 9.2.0。
- `uv run pytest -v`：3 passed；`scripts/check_env.py` 输出合法 JSON 且不包含秘密值。
- 核查 SWE-Interact 75 任务、Harbor 轨迹恢复边界、StateHarness、AgentRewind、MettleBench、TRACE；证据写入 `docs/related_work.md`。

### 结论与判断

- SWE-Interact 可作为交互与评测骨架，但不能直接视为 CASR 选择性修复基准。
- Harbor 加载 native/ATIF 轨迹不恢复 sandbox 文件，CASR 必须自建快照。
- StateHarness 可作 B3 参照，AgentRewind 可作 B4 参照；二者均不直接等于 CASR。
- 当前硬件适合轻量 API 或离线原型，不适合大模型训练。

### 未完成 / 未知

- 没有运行模型 API、Harbor、Modal、SWE-Interact 或 CASR 方法实验。
- 没有 CASR 成功率、回归率、成本或验证器可靠性数据。
- 未确认 API 模型、预算和付费试跑授权。
- StateHarness 代码许可证未知。
- “Long-Horizon Software Engineering Agents: From Tasks to Projects” 未找到权威匹配，标记 unknown。

### 下一步

执行 `docs/superpowers/plans/2026-11-25-casr-m2-prototype.md`，先完成无模型调用的离线闭环；之后根据用户确认的模型与预算设计真实 Agent 烟雾测试。

## 2026-11-25 — Milestone 2：Harness + Verifier MVP

### 已完成事实

- 实现需求版本账本、执行溯源图、Git 产物提取、影响传播与四类修复规划、隔离执行器和独立验证器。
- 离线 Demo 实际运行 PASS：Revert 2、Modify 1、Revalidate 1、Retain 2；JSON、checksum、summary 三组测试均 PASS。
- 本地完整套件达到 82 passed、3 skipped；跳过项为 Windows 符号链接权限与 POSIX 可执行模式限制。
- 三案例三策略实验实际运行 9 次：不修复 0/3，整体重建 3/3，CASR 3/3；CASR 与整体重建均通过新需求和保留功能验收。
- 同一实验中，整体重建平均写 14 个路径、共重写 12 个保留模块；CASR 平均写 2 个路径、重写 0 个保留模块。
- 新增三案例三图条件消融，实际运行 9 次：完整图 3/3 成功，漏记需求到动作的溯源 0/3，加入伪依赖 3/3。
- 伪依赖条件下平均 Revalidate 从 1 增至 2、Retain 从 6 降至 5；说明该扰动扩大复核范围但未破坏脚本化验收。
- 修复 ADD 更正对空目标调用账本的边界错误，并增加回归测试。
- 实验配置、原始结果、案例清单、CSV、摘要、元数据、Demo 证据已保存在 `results/` 并纳入开源白名单。

### 结论与判断

- 合成结果支持“选择性修复可在保持正确性的同时减少保留产物重写”的工程假设，但不支持普遍性能优越或统计显著结论。
- 构造性消融显示：漏溯源会破坏该设定的修复正确性，伪依赖主要扩大复核范围。这提示下一阶段优先评估真实轨迹的溯源召回，但不能据此宣称真实项目的主要瓶颈已经确定。
- 当前修复补丁与图关系均为脚本化/人工给定，不能据此评价自主 Coding Agent。

### 限制与未完成

- 三个案例共享同一模板，仅改变保留模块数量；单次运行，无统计显著性检验。
- 未调用 DeepSeek 或其他模型 API；未运行 SWE-Interact 真实 Benchmark；未测真实 Agent 的图误差分布。
- 集群早期 CPU-only smoke 已通过；本轮 M2 复验尝试时旧 Jupyter 页面报错，尚无最新 M2 的 Linux 远程结果。
- 独立审查、初始提交与 GitHub 开源在本日志追加时尚未完成。
