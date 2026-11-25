# CASR 集群使用手册

> 适用方式：Windows 11 本地开发 + 北航 GPU 集群 Crater 网页平台。
>
> 当前模式：**Agent 自动准备与收集，用户人工确认并提交作业**。
>
> 不假定 Slurm，不调用未文档化的提交 API；本次仅通过网页创建并停止一个 CPU-only 开发作业。

## 1. 前置条件

1. EasyConnect 已登录且 Crater 网页可达。若系统级 VPN 适配器仍 Disconnected，不要据此判定网页或 Jupyter ingress 不可用；需分别验证。
2. Crater 平台已登录当前账号 `panxg27`。
3. 已创建一个运行中的 Jupyter Lab 开发作业；如仅做代码同步和 CPU 测试，应选择页面允许的最小 CPU/内存，GPU 数量设为 0。
4. 开发作业保留平台要求的 `sleep infinity` 启动方式。
5. 从作业详情页的“SSH 连接”取得**该作业实际提供的 IP、端口和用户名**。
6. 选择一把已有私钥，并将对应公钥注册到运行中作业的 `~/.ssh/authorized_keys`。注册前需用户确认；不要读取或输出私钥内容。

本次实际执行前，SSH 用户认证未通过，因此没有配置 `casr-cluster` 别名；代码同步、测试和收集通过官方 Jupyter Lab Terminal/Contents API 完成。若后续要启用 SSH 脚本流程，仍需先确认并注册公钥。

## 2. 配置 SSH 别名

只有在取得实际运行中作业的连接信息后，才编辑 `C:\Users\李世旺\.ssh\config`。以下为模板，不是当前已验证配置：

```sshconfig
Host casr-cluster
    HostName <作业详情页提供的实际 IP 或主机名>
    User panxg27
    Port <作业详情页提供的实际端口>
    IdentityFile ~/.ssh/<已确认使用的现有私钥>
    IdentitiesOnly yes
    BatchMode yes
    StrictHostKeyChecking yes
```

注意：

- `panxg27` 已从作业配置核实；IP 和端口必须来自当前运行中作业，不能使用 PDF 中其他用户的示例。
- 首次连接前应通过官方渠道核对主机密钥指纹，再决定是否加入 `known_hosts`。
- 不要覆盖现有 `os-lab` 配置。
- 如果注册公钥，只上传 `.pub` 内容，不上传私钥。

验证连接只做一次，失败后停止并分析：

```powershell
ssh casr-cluster "printf 'connected\n'; hostname; pwd"
```

## 3. 同步代码

在 CASR 项目根目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/local/sync.ps1
```

默认目标为已核实的 Jupyter 持久目录 `/home/panxg27/CASR`。如果开发作业使用其他挂载路径：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/local/sync.ps1 -RemoteRoot <实际绝对路径>
```

同步行为：

- 只打包 `src`、`scripts`、`tests`、`pyproject.toml`、`uv.lock`、`README.md`、`.env.example`、`.gitignore`。
- 排除 `.env`、私钥、`.venv`、`__pycache__`、`.pytest_cache`、原始数据、日志和结果。
- 使用 `scp` 上传，再通过 `ssh` 解包。
- `BatchMode=yes`、`StrictHostKeyChecking=yes`、连接超时 10 秒；不无限重试。
- 解包失败会返回非零退出码，本地临时包自动清理。

仅查看计划而不连接集群：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/local/sync.ps1 -DryRun
```

## 4. 一条命令运行远程轻量测试

配置好 `casr-cluster` 并完成同步后，在 CASR 项目根目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/local/smoke-test.ps1
```

该命令依次完成：

1. SSH 进入远程 CASR 目录；
2. 执行 `scripts/cluster/prepare.sh` 检查 Python 3.12、Git、tar、SHA-256 和项目依赖；
3. 使用 `.venv/bin/python` 或 `python3` 运行 `pytest -q`；
4. 将输出保存到本地 `logs/smoke-<时间戳>.log`；
5. 成功返回 PASS，失败返回非零退出码。

如果 SSH 尚未配置，但已有运行中的 Jupyter 开发作业，可在官方 Jupyter Lab Terminal 中执行同一入口：

```bash
cd /home/panxg27/CASR
bash scripts/cluster/run_experiment.sh \
  --run-id casr-smoke-001 \
  --root /home/panxg27/CASR
```

远程测试文件包含 Windows PowerShell 测试时，Linux 作业应使用已经平台跳过的测试快照；本次远程快照较早，实际通过 `PYTEST_ADDOPTS` 排除 Windows 专属测试后通过。

SSH 流程默认不会安装依赖。如果确认允许远程依赖下载并安装，再显式执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/local/smoke-test.ps1 -InstallDependencies
```

仅查看将执行的远程命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/local/smoke-test.ps1 -DryRun
```

## 5. 准备并人工提交 GPU 批处理作业

### 5.1 Agent 已准备的内容

- 同步白名单和 SSH/SCP 脚本；
- 远程环境检查脚本；
- 固定离线冒烟实验入口；
- 日志和结果目录规范；
- SHA-256 校验的收集脚本。

### 5.2 用户需在网页确认的参数

| 参数 | 要求 |
|---|---|
| 作业类型 | 自定义单机批处理作业 |
| 账户 | 用户确认的实际可用账户 |
| CPU / 内存 | 满足轻量测试的最小允许值 |
| GPU | 本冒烟脚本不执行 GPU 计算；如只为验证调度，最多申请 1 张，并由用户确认 |
| 镜像 | 已有 Python 3.12 镜像；不为冒烟测试下载大型镜像 |
| 挂载 | 与开发作业选择同一用户空间源目录 |
| 启动命令 | 使用下方模板，并将路径替换为页面中的实际挂载目标 |
| 提交 | 必须由用户人工点击提交 |

启动命令模板：

```bash
cd <实际挂载的 CASR 绝对路径> && bash scripts/cluster/run_experiment.sh --root <实际挂载的 CASR 绝对路径> --run-id casr-smoke-001
```

例如，只有当页面确实把共享目录挂载到 `/home/panxg27` 时，才使用：

```bash
cd /home/panxg27/CASR && bash scripts/cluster/run_experiment.sh --root /home/panxg27/CASR --run-id casr-smoke-001
```

如果自定义作业挂载到 `/mnt/...`，必须使用 `/mnt/...`，不能沿用 Jupyter 的 `/home/panxg27`。

### 5.3 实验脚本行为

`run_experiment.sh` 只做以下事情：

1. 检查 CASR 环境；
2. 运行 pytest；
3. 运行环境审计并只报告配置存在性；
4. 记录 `nvidia-smi` 可见性；
5. 写入：
   - `logs/<run-id>/prepare.log`
   - `logs/<run-id>/pytest.log`
   - `logs/<run-id>/environment.json`
   - `logs/<run-id>/gpu.csv` 或 `gpu-error.log`
   - `results/<run-id>/summary.json`
6. 立即退出。

脚本不提交作业，不循环等待 GPU，不执行 `sleep infinity`，不调用模型 API，不申请额外资源。

## 6. 收集日志和结果

作业执行期间或结束后，只要还有一个挂载同一目录的运行中开发作业，就可执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/local/collect.ps1 -RunId casr-smoke-001
```

默认本地输出到 `results/cluster/<时间戳>-casr-smoke-001/`。也可指定：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/local/collect.ps1 -RunId casr-smoke-001 -OutputDirectory results/cluster/casr-smoke-001
```

收集流程：

1. SSH 将 `logs/<run-id>` 和 `results/<run-id>` 打成远程归档；
2. 返回远程 SHA-256；
3. SCP 下载归档；
4. 校验本地 SHA-256；
5. 解包到本地输出目录。

远程归档保留，便于重复收集；脚本不自动删除远程产物。

如果 GPU 作业已经结束且没有运行中的开发作业：

- 使用 Crater 文件系统下载对应目录的归档；或
- 新建一个 CPU-only 开发作业，挂载同一目录后运行收集脚本。

不要为了收集结果重新申请 GPU。

## 7. 失败处理

| 现象 | 处理 |
|---|---|
| SSH 超时 | 检查 VPN 连接后路由、作业是否仍运行、实际 IP/端口；不要连续重试 |
| Host key verification failed | 通过官方渠道核对指纹；不要关闭主机密钥检查 |
| Permission denied (publickey) | 检查所选私钥、对应公钥注册和 `authorized_keys` 权限 |
| `root does not exist` | 检查同步目标与实际挂载路径 |
| Python 版本错误 | 选择 Python 3.12 镜像或设置 `CASR_PYTHON` |
| 依赖缺失 | 默认失败；确认允许安装后才使用 `-InstallDependencies` 或 `prepare.sh --install` |
| pytest 失败 | 查看 `logs/smoke-*.log` 或作业内 `logs/<run-id>/pytest.log` |
| GPU 长时间待调度 | 不无限等待；由用户决定继续等待、降低资源或停止作业 |
| 收集不到产物 | 检查 run-id、作业是否写入挂载目录、开发作业是否挂载同一源目录 |

## 8. 本地一条命令

不连接集群时，运行完整本地测试：

```powershell
uv run pytest -q
```

## 9. 当前真实状态

- 本地完整测试：16 项通过。
- 本地离线冒烟入口：通过，结果位于 `logs/local-smoke-001/` 和 `results/local-smoke-001/`。
- 集群开发作业：已创建 1 CPU / 2 GiB / 0 GPU 作业，验证后已停止。
- 集群同步与依赖准备：通过官方 Jupyter Terminal 完成。
- 集群远程测试：首次因 Windows 测试未跳过而 FAIL；第二次平台无关测试 5 passed，状态 PASS。
- 日志与结果收集：已完成，保存在 `logs/cluster-smoke-*` 和 `results/cluster-smoke-*`。
- SSH/SCP：端点可达，但已有用户密钥认证失败；未配置 SSH 别名。
- GPU 作业提交、模型 API 和 Benchmark：未执行。
