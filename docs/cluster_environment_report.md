# CASR 集群环境核查报告

> 核查日期：2026-11-25
>
> 范围：Windows 11 本地开发端、北航 GPU 集群 Crater 平台、SSH/SCP 与半自动作业流程。
>
> 安全边界：未读取或输出代理密码、VPN 密码、访问令牌或私钥；未修改系统路由、安全策略或 SSH 配置；仅创建并停止本次 CPU-only 开发作业。

## 1. 结论摘要

1. 本地 OpenSSH、SCP、Git、Windows PowerShell 均已安装，可承担脚本化同步与测试。
2. 已登录的 Crater 账号为 `<cluster-user>`。本次创建并运行了一个 1 CPU、2 GiB、0 GPU 的 Jupyter 开发作业，验证结束后已停止。
3. 从已有 Jupyter 作业配置核实，持久目录 `/home/<cluster-user>` 挂载到共享存储 `crater-rw-storage` 的 `sugon-gpu-home-lab/<cluster-user>` 子路径。
4. 实际作业 YAML 使用 `batch.volcano.sh/v1alpha1`，调度器为 `volcano`；没有证据表明用户应使用 Slurm 命令。
5. 官方 CLI 文档明确了 `job ls`、`job exec`、`job ssh`、`job pods` 和账户切换等能力，但没有文档化的作业创建或自动提交命令。
6. 因此采用半自动模式：**Agent 准备代码、脚本和作业参数 → 用户在网页确认并提交 → 作业在持久目录写日志和结果 → Agent 通过运行中的开发作业或文件系统收集**。
7. 已通过官方 Jupyter Lab 终端完成代码同步、远程依赖准备和两次 smoke；第二次平台无关测试通过。SSH 传输可达，但已有用户密钥认证失败，因此未使用 SSH/SCP。

## 2. 本地工具核查

| 工具 | 实测结果 |
|---|---|
| Windows | Windows 11，10.0.26200，x64 |
| OpenSSH / SCP | 9.5.6.4，位于 `C:\Windows\System32\OpenSSH` |
| Git | 2.56.0.windows.2 |
| Windows PowerShell | 10.0.26100.9818 |
| 项目 Python | 3.12.0，位于项目 `.venv` |
| 项目依赖 | GitPython 3.2.1、NetworkX 3.7、Pydantic 2.14.4、pytest 9.2.0 |

### 2.1 已有 SSH 密钥

仅检查公钥指纹，未读取私钥内容：

- `id_rsa.pub`：3072 位 RSA，`<redacted-public-key-fingerprint>`
- `os-lab-ed25519.pub`：256 位 ED25519，`<redacted-public-key-fingerprint>`

已有密钥存在，因此没有触发“无密钥时生成专用密钥”的分支。没有选择或注册其中任何一把钥匙，也没有修改 `~/.ssh/config`。`os-lab` 配置属于其他实验环境，未被复用。

## 3. Crater 平台与账号

### 3.1 直接证据

登录后的平台总览显示当前用户为“<已脱敏用户>”。交互式作业和自定义作业列表中的作业名、详情链接及配置均属于 `<cluster-user>`。

核查的最近一个 Jupyter 作业：

- 作业名：`shp`
- 状态：已释放
- 账户：公共账户；YAML 中账户标识为 `default`
- 工作目录：`/home/<cluster-user>`
- 持久挂载：`/home/<cluster-user>`
- 共享存储卷：`crater-rw-storage`
- 共享存储子路径：`sugon-gpu-home-lab/<cluster-user>`
- 后端 API：`batch.volcano.sh/v1alpha1`
- 调度器：`volcano`

### 3.2 本次实际作业

| 项目 | 实测值 |
|---|---|
| 作业 | `jpt-<cluster-user>-261125-ee9ee` |
| 类型 | Jupyter Lab |
| 资源 | 1 CPU / 2 GiB / 0 GPU |
| 节点 | `<cpu-node>` |
| 状态 | 已停止 |
| 工作目录 | `/home/<cluster-user>` |
| 持久卷 | `crater-rw-storage` / `sugon-gpu-home-lab/<cluster-user>` |

作业详情确认调度器为 `volcano`，后端 API 为 `batch.volcano.sh/v1alpha1`。完整执行证据见 [cluster_execution_record.md](cluster_execution_record.md)。

## 4. 作业机制

### 4.1 开发作业

官方文档和实际页面均支持通过“新建 Jupyter Lab 作业”创建交互式开发作业。可配置 CPU、内存、GPU、镜像、挂载、环境变量和通知；作业详情提供日志、YAML、资源监控、Web Terminal、Jupyter 和 SSH 连接入口。

《集群使用.pdf》要求开发作业保留 `sleep infinity`，以使 Jupyter/SSH 保持存活。CASR 的批处理实验脚本不使用 `sleep infinity`，避免作业结束后仍占用资源。

### 4.2 自定义 GPU 作业

官方文档支持“自定义单机批处理作业”：选择镜像、资源和挂载后，平台在分配资源时执行启动命令。结果写入挂载的用户空间目录后可持久化；仅写入未挂载容器临时目录的文件不会可靠保留。

CASR 不直接调用平台内部 API，也不使用 `sbatch`。GPU 作业需由用户在网页确认资源、账户、镜像、挂载和启动命令后提交。

### 4.3 开发作业与 GPU 作业是否共享存储

**已确认：** 已有 Jupyter 作业的 `/home/<cluster-user>` 是共享持久卷。

**文档确认：** 自定义作业可挂载用户空间文件夹；作业结果写回所选源文件夹。

**仍需按实际作业确认：** 只有开发作业和 GPU 作业选择同一用户空间源目录时，才能保证二者访问同一份 CASR 代码和结果。挂载目标路径可能不同，例如 Jupyter 使用 `/home/<cluster-user>`，自定义作业可能按页面配置挂载到 `/mnt/...`。脚本通过 `RemoteRoot` 参数兼容实际路径，不硬编码自定义作业的挂载位置。

### 4.4 官方 API / CLI / Scheduler

- 实际 YAML 证明后端使用 Volcano，但这不是用户可直接提交作业的 CLI 证据。
- 已核查官方 CLI 文档，记录到：
  - `crater job ls`
  - `crater job exec JOB`
  - `crater job ssh JOB`
  - `crater job pods JOB`
  - `crater account ls/current/use`
- 未发现文档化的 `job create`、`job submit` 或无人值守提交命令。
- `job exec` 的 API v7 后端要求是**作业内执行**的前提，不等同于公开作业提交 API。

结论：当前采用网页人工提交，不猜测 API。

### 4.5 SSH 连接与公钥

官方流程是在运行中作业详情页点击“SSH 连接”，使用页面提供的真实 IP、端口和用户名；首次连接需把本地公钥加入作业容器的 `~/.ssh/authorized_keys`，并设置：

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

未知项：新建作业是否自动继承旧作业容器的 `authorized_keys`。在验证前，应为每个新开发作业检查公钥注册状态。

### 4.6 作业结束后的数据与监控

- 网页作业详情保留状态和日志入口。
- 持久结果必须写入挂载目录。
- GPU 作业运行期间可通过网页资源监控、Web Terminal 或 SSH 查看；脚本只记录 `nvidia-smi` 可见性，不申请或占用 GPU。
- 作业结束后，原作业 SSH 通常不可用。收集方式为：
  1. 通过仍有权限的开发作业 SSH/SCP；或
  2. 通过平台文件系统下载归档；或
  3. 新建一个 CPU-only 开发作业，挂载同一目录后收集。

## 5. 当前限制与未执行项

| 项目 | 状态 | 说明 |
|---|---|---|
| EasyConnect 全局/分流路由判定 | 未确认 | 登录后 Sangfor 适配器仍 Disconnected，无 `<集群内网网段>` 专用路由 |
| 开发作业 SSH IP/端口 | 已验证 | `<作业内网地址>:<端口>`，用户 `<cluster-user>` |
| SSH 用户认证、SCP | 未通过 | 已有 RSA 和 ED25519 密钥均返回 publickey 失败 |
| Jupyter 终端远程执行 | 已完成 | 使用官方登录会话，不读取令牌 |
| 远程环境检查与轻量测试 | 已完成 | 第二次平台无关 smoke 为 PASS |
| GPU 作业准备/提交/执行 | 未提交 | 需用户确认资源、挂载和启动命令 |
| 日志与结果收集 | 已完成 | 两次运行产物已保存到本地 |

## 6. 已实施的半自动脚本

| 文件 | 职责 |
|---|---|
| `scripts/local/sync.ps1` | 打包白名单代码，SCP 到持久目录，SSH 解包；排除 `.env`、缓存和虚拟环境 |
| `scripts/local/smoke-test.ps1` | SSH 执行远程环境检查和 pytest；保存本地日志；失败即停 |
| `scripts/local/collect.ps1` | 归档指定 run 的日志/结果，SCP 下载，校验 SHA-256 后解包 |
| `scripts/cluster/prepare.sh` | 检查 Python 3.12、命令和依赖；只有显式 `--install` 才允许安装 |
| `scripts/cluster/run_experiment.sh` | 在已分配作业内运行离线冒烟实验，写日志和 `summary.json`，随后退出 |

脚本不包含作业提交逻辑，不包含无限等待，不读取凭据，不自动删除远程产物。

## 7. 官方资料

- [交互式作业](https://raids-lab.github.io/crater/zh/docs/user/quick-start/interactive/)
- [自定义单机批处理作业](https://raids-lab.github.io/crater/zh/docs/user/quick-start/batchprocess/)
- [文件系统](https://raids-lab.github.io/crater/zh/docs/user/file/file/)
- [登录与 VPN](https://raids-lab.github.io/crater/zh/docs/user/quick-start/login/)
- [Crater CLI](https://raids-lab.github.io/crater/zh/docs/user/toolbox/cli/)
- [SSH 功能](https://raids-lab.github.io/crater/zh/docs/user/toolbox/ssh/ssh-func/)
- [用户与账户](https://raids-lab.github.io/crater/zh/docs/user/quick-start/user-account/)
- [作业模板](https://raids-lab.github.io/crater/zh/docs/user/quick-start/jobtemplate/)

以上页面于 2026-11-25 核查。集群实际配置以作业详情页和 YAML 为准。
