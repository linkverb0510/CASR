# CASR 集群半自动工作站执行记录

> 日期：2026-11-25
>
> 记录原则：只记录真实执行结果；计划、模板和未执行步骤单独标注。

## 1. 本次实际完成

1. 只读核查 Windows 网络、路由、DNS、代理监听与 VPN 适配器状态。
2. 核查 OpenSSH、SCP、Git、Windows PowerShell 和已有 SSH 公钥指纹。
3. 登录态下核查 Crater 当前账号的交互式作业、自定义作业和历史 Jupyter 作业配置。
4. 从实际作业配置核实账号 `<cluster-user>`、工作目录 `/home/<cluster-user>` 和共享持久卷挂载。
5. 编写五个半自动脚本及平台无关的脚本测试。
6. 在本地真实运行 `prepare.sh` 和 `run_experiment.sh`，不是仅做 dry-run。
7. 创建一个 1 CPU、2 GiB、0 GPU 的 Jupyter 开发作业并确认进入 Running。
8. 通过官方 Jupyter Lab 同源 Terminal 上传白名单同步包、校验 SHA-256、解包并安装远程依赖。
9. 在集群 Pod 内执行两次离线 smoke，记录首次失败和修复测试选择后的通过结果。
10. 通过 Jupyter Contents API 收集两次运行的日志与 `summary.json` 到本地。
11. 确认开发作业已停止，未提交 GPU 作业。
12. 运行完整本地测试、依赖锁检查、脚本 dry-run、Bash 语法检查和文档链接检查。

## 2. 网络实测记录

### 2.1 连接前快照

测量时间：2026-11-25 21:04:05–21:04:30（UTC+08:00）。

| 项目 | 实测结果 |
|---|---|
| WLAN | `<local-ip>/16`，ifIndex 14 |
| 默认路由 | 唯一 `0.0.0.0/0`，WLAN，下一跳 `<gateway>` |
| 集群网段路由 | 未发现 `<cluster-subnet>` 专用路由 |
| Sangfor VPN 适配器 | Disconnected |
| `gpu.act.buaa.edu.cn` | 解析到 `198.18.0.74` |
| WinHTTP | 直连 |
| WinINET | 本地代理 `127.0.0.1:7897` + 本地 PAC `127.0.0.1:10086` |
| 环境代理 | `HTTP_PROXY` / `HTTPS_PROXY` 指向 `127.0.0.1:7899`，userinfo 已脱敏 |
| 7897 监听进程 | `com.vortex.helper` |
| 7899 监听进程 | `Qoder CN` |
| 10086 监听进程 | `SangforCSClient` |

### 2.2 EasyConnect 登录后快照

测量时间：2026-11-25 22:43:04（UTC+08:00）。

| 项目 | 实测结果 |
|---|---|
| EasyConnect 网页登录 | 已登录，浏览器可访问 Crater |
| Sangfor SSL VPN 适配器 | 仍为 Disconnected |
| McAfee VPN / QMTAP / UU TAP | 均为 Disconnected |
| 默认路由 | 仍只有 WLAN，下一跳 `<gateway>` |
| `<cluster-subnet>` 专用路由 | 未发现 |
| 集群域名 DNS | 仍为 `198.18.0.74` |
| 本机 `192.168.5.*` 地址 | 未发现 |
| 实际访问路径 | 浏览器、本地代理/PAC 和平台 ingress 可用 |

结论：本次确认了 EasyConnect 登录态和集群网页可达性，但没有证据表明系统级 VPN 隧道已建立，也不能判定全局/分流模式。没有修改路由、DNS、适配器、防火墙或安全策略。

## 3. 实际开发作业

| 项目 | 实测值 |
|---|---|
| 显示名 | `casr-dev-smoke-20261125` |
| 作业名 | `jpt-<redacted-job-id>` |
| 命名空间 | `crater-workspace` |
| 创建时间 | `2026-11-25T14:11:23Z` |
| 调度器 | `volcano` |
| 节点 | `huawei-cpu-5` |
| CPU | request 1，limit `1001m` |
| 内存 | request `2Gi`，limit `2049Mi` |
| GPU | 0 |
| 镜像 | `gpu-harbor.act.buaa.edu.cn/user-zhangyf/linuxserver/code-server:07182240-cf6d` |
| 工作目录 | `/home/<cluster-user>` |
| 持久卷 | `crater-rw-storage` |
| 子路径 | `sugon-gpu-home-lab/<cluster-user>` |
| 官方 SSH | `ssh <cluster-user>@<job-ip> -p <job-port>` |
| 官方 Jupyter | `https://gpu.act.buaa.edu.cn/ingress/jupyter/jpt-<redacted-job-id>` |
| 最终状态 | 已停止；页面显示完成于约 22:44（UTC+08:00） |

平台最初返回 `40302 Email not verified`。仅将本作业的邮件通知开关关闭后重新提交成功，没有修改账户验证设置或绕过认证。

## 4. SSH 与 Jupyter 访问结果

### 4.1 SSH

- 官方端点 TCP/SSH 握手可达，并完成主机密钥交换。
- 使用 `StrictHostKeyChecking=accept-new` 记录 ED25519 主机密钥；未通过独立官方渠道核验指纹。
- 现有 RSA 和 ED25519 用户密钥各测试一次，均返回 `Permission denied (publickey,password)`。
- 没有尝试密码，没有读取私钥内容，没有生成新密钥，没有修改 `~/.ssh/config`，没有注册公钥。
- 因此 SSH/SCP 用户认证未通过；后续同步与执行改用已认证的 Jupyter Lab 网页终端。

### 4.2 Jupyter Lab

- 使用现有登录会话访问官方 Jupyter ingress。
- 通过同源 REST 创建 Terminal，并通过 Terminal WebSocket 执行命令。
- 确认 Pod 主机名、`/home/<cluster-user>` 工作目录和默认 Python 3.13.9。
- 未读取浏览器 Cookie、访问令牌或密码。

## 5. 同步与依赖准备

同步包：

- 本地文件：`logs/casr-sync-20261125.tar.gz`
- 远程文件：`/home/<cluster-user>/casr-sync-20261125.tar.gz`
- 大小：16,948 字节
- SHA-256：`3b346cf6f632fa0a016b13bd96bedd0858be6998a7eee7196a4c3d01b352da18`
- 归档条目：27；解包后常规文件：20
- 排除：`.env`、`.venv`、缓存、原始数据、日志和结果

远程校验后解包到 `/home/<cluster-user>/CASR`。显式执行 `prepare.sh --install`，退出码为 0，在 Python 3.12.3 虚拟环境中安装锁定依赖。

发现并修复本地 `prepare.sh` 的 Python 选择问题：默认 `python3` 为 3.13.9 时，应优先选择已有的 `python3.12`。远程同步包产生于该修复之前，但远程 `.venv` 已创建并优先使用，因此两次 smoke 均使用 Python 3.12.3。

## 6. 集群 smoke 结果

### 6.1 首次运行：失败

| 项目 | 结果 |
|---|---|
| run-id | `cluster-smoke-20261125` |
| 开始/结束 | `2026-11-25T14:41:30Z`–`2026-11-25T14:41:31Z` |
| 耗时 | 1 秒 |
| prepare 退出码 | 0 |
| pytest 退出码 | 1 |
| environment 退出码 | 0 |
| 状态 | FAIL |
| GPU 可见性 | unavailable |

失败原因：Linux 作业不存在 `powershell.exe`，而远程同步包中的 Windows 本地自动化测试未做平台跳过。共 8 项失败、7 项通过。这是测试可移植性问题，不是 CASR 运行时代码或集群调度失败。

### 6.2 第二次运行：通过

远程快照尚未包含本地平台跳过补丁，因此通过 `PYTEST_ADDOPTS` 排除 Windows 专属测试，保留环境测试和 Linux Bash 脚本测试。

```bash
cd /home/<cluster-user>/CASR
PYTEST_ADDOPTS='-k "not sync and not smoke_test and not collect and not prepare_prefers"' \
  bash scripts/cluster/run_experiment.sh \
    --run-id cluster-smoke-linux-20261125 \
    --root /home/<cluster-user>/CASR
```

| 项目 | 结果 |
|---|---|
| run-id | `cluster-smoke-linux-20261125` |
| 开始/结束 | `2026-11-25T14:43:12Z`–`2026-11-25T14:43:15Z` |
| 耗时 | 3 秒 |
| prepare 退出码 | 0 |
| pytest 退出码 | 0 |
| pytest | 5 passed |
| environment 退出码 | 0 |
| 状态 | PASS |
| GPU 可见性 | unavailable，符合 0 GPU 作业配置 |
| 主机 | `jpt-<redacted-job-id>-default0-0` |

这次运行验证的是集群 Pod 内的离线环境、Linux 脚本和产物落盘，不是模型实验或 Benchmark 性能。

## 7. 收集的产物

通过 Jupyter Contents API 读取并保存到本地：

- `logs/cluster-smoke-20261125/`
- `results/cluster-smoke-20261125/summary.json`
- `logs/cluster-smoke-linux-20261125/`
- `results/cluster-smoke-linux-20261125/summary.json`

每个运行目录包含 `prepare.log`、`pytest.log`、`environment.json` 和 `summary.json`。`nvidia-smi` 不可用，因此没有生成 `gpu.csv` 或 `gpu-error.log`，摘要记录为 `unavailable`。

## 8. 本地测试修复

- `prepare.sh` 优先选择 `python3.12`，再回退 `python3`。
- 新增回归测试，验证默认 `python3` 不兼容时仍选择 Python 3.12。
- Windows PowerShell 测试在非 Windows 平台跳过；Linux 仍执行 Bash 语法、路径校验和帮助文本测试。
- 修复回归测试在 Windows 上误调用 WSL `bash` 的问题，显式使用 Git Bash 和基础 Python 可执行文件。

## 9. 最终本地验证

| 命令 | 结果 |
|---|---|
| `uv run pytest -q` | 16 passed |
| `uv lock --check` | Resolved 16 packages in 2ms |
| `sync.ps1 -DryRun` | PASS，输出同步计划 |
| `smoke-test.ps1 -DryRun` | PASS，输出远程检查命令 |
| `collect.ps1 -DryRun` | PASS，输出收集计划 |
| `bash -n scripts/cluster/prepare.sh` | PASS |
| `bash -n scripts/cluster/run_experiment.sh` | PASS |
| 文档相对链接检查 | PASS，25 个链接，0 缺失 |
| 冻结研究文档 SHA-256 | 与初始化时一致 |

## 10. 端到端状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| EasyConnect 登录与集群网页访问 | 已完成 | 系统级 VPN 隧道未确认 |
| CPU-only 开发作业创建与运行 | 已完成 | 1 CPU / 2 GiB / 0 GPU |
| SSH 传输与主机密钥交换 | 已完成 | 端点可达 |
| SSH 用户认证与 SCP | 未通过 | 已有密钥均 publickey 失败 |
| Jupyter 网页终端同步与执行 | 已完成 | 使用官方同源 Terminal |
| 远程依赖准备 | 已完成 | Python 3.12.3，退出码 0 |
| 远程轻量测试 | 已完成 | 首次 FAIL，第二次 PASS |
| 日志与结果收集 | 已完成 | 已保存到本地 |
| 开发作业停止 | 已完成 | 页面状态“已停止” |
| GPU 作业提交/执行 | 未执行 | 未申请或占用 GPU |
| 模型 API / Benchmark | 未执行 | 不属于本次 smoke |

## 11. 未执行的敏感或高影响操作

- 未生成新 SSH 密钥；
- 未修改 `~/.ssh/config`；
- 未注册集群公钥；
- 未读取或输出代理密码、VPN 密码、访问令牌或私钥；
- 未修改系统路由、DNS、防火墙或安全策略；
- 未删除远程产物或用户文件；
- 未提交 GPU 作业；
- 未调用模型 API；
- 未创建 Git commit 或推送。

## 12. 后续建议

1. 若要启用 `sync.ps1`、`smoke-test.ps1` 和 `collect.ps1`，先由用户确认已有公钥注册方式，再配置 `casr-cluster` 别名；不要复用其他实验的 `os-lab` 配置。
2. 若继续仅使用网页终端，可把 Jupyter Contents/Terminal 流程封装为可选半自动入口，但不应读取或持久化浏览器令牌。
3. GPU 作业仍需用户在网页确认资源、账户、镜像、挂载和启动命令后人工提交。

## 13. M2 复验尝试（2026-11-25 晚间）

- 尝试重新打开已停止的官方 Jupyter ingress；页面仅显示 `Something went wrong!` / `Show Error`。
- 尝试访问平台首页，浏览器返回 `ERR_CONNECTION_TIMED_OUT`。
- 因此本轮没有新建作业、没有远程同步最新 M2 代码，也没有产生 M2 Demo 或两组合成实验的 Linux 结果。
- 早期第 6 节的 CPU-only smoke 结果仍然有效，但只能证明当时的轻量环境与脚本闭环，不能冒充最新 M2 集群复验。
