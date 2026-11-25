# CASR VPN / 代理分流诊断报告

> 测量时间：2026-11-25 21:04:05–21:04:30（UTC+08:00）
>
> 测量方式：Windows PowerShell 5.1 只读查询。
>
> 未修改系统路由、DNS、适配器、防火墙或安全策略；未读取或输出代理密码、VPN 密码、令牌或私钥。

## 1. 结论

1. 测量时 EasyConnect 的 Sangfor SSL VPN 适配器处于 **Disconnected**，没有连接集群内网的 VPN 路由。
2. 唯一 IPv4 默认路由走 WLAN；`<cluster-subnet>` 没有专用路由。
3. 集群域名 `gpu.act.buaa.edu.cn` 当前解析到 `198.18.0.74`，这是常见的本地代理 fake-IP 地址段，说明当前浏览器访问很可能经过本地代理链路。
4. WinHTTP 为直连；WinINET 和当前进程环境分别指向本地代理端口；Sangfor 同时提供一个本地 PAC 服务。
5. **无法据此判定 EasyConnect 本身是全局路由还是分流路由。** 必须取得 VPN 连接后的默认路由、集群网段路由和 DNS 快照进行对比。
6. EasyConnect 登录后复测仍未发现系统级 VPN 隧道；集群访问实际通过浏览器、本地代理/PAC 和平台 ingress 完成。
7. 官方开发作业 SSH 端点传输可达，但用户密钥认证失败；没有据此修改路由或安全设置。

## 2. 连接前快照（VPN 未连接）

### 2.1 适配器

Up 适配器：

| ifIndex | 名称 | 地址 |
|---:|---|---|
| 14 | WLAN | `<local-ip>/16` |
| 24 | VMware Network Adapter VMnet1 | `192.168.154.1/24` |
| 20 | VMware Network Adapter VMnet8 | `192.168.131.1/24` |
| 74 | vEthernet (FSE HostVnic) | Hyper-V 虚拟适配器 |

VPN 相关适配器均为 Disconnected：

| ifIndex | 名称 | 描述 |
|---:|---|---|
| 10 | 以太网 2 | Sangfor SSL VPN CS Support System VNIC |
| 27 | McAfee VPN | TAP-Windows Adapter V9 |
| 21 | 本地连接 | QMTAP Adapter V9 |
| 13 | 以太网 3 | Netease UU TAP-Win32 Adapter V9.21 |

### 2.2 默认路由与集群网段

```text
DestinationPrefix  Interface  NextHop      RouteMetric
0.0.0.0/0          WLAN        <gateway>   0
```

没有发现 `<cluster-subnet>` 或 `<cluster-host>/32` 的专用路由。

`Find-NetRoute` 对以下目标均选择 WLAN：

- `<cluster-host>`
- `219.224.171.1`（官方登录文档给出的 DNS 解析备选地址）

### 2.3 DNS

WLAN DNS：

```text
127.0.0.1
223.5.5.5
223.6.6.6
```

集群域名解析：

```text
gpu.act.buaa.edu.cn  A  198.18.0.74
```

**证据：** 域名没有解析到公开 VPN 门户地址，而是返回 fake-IP 段地址。

**推断：** 当前名称解析被本地代理/DNS 层接管；这不证明 EasyConnect 已连接，也不证明其路由模式。

## 3. 代理配置

| 层级 | 实测配置 |
|---|---|
| WinHTTP | Direct access，无代理 |
| WinINET | `ProxyEnable=1`，`ProxyServer=127.0.0.1:7897` |
| WinINET PAC | `http://127.0.0.1:10086/SangforAppPass.17081.pac` |
| 进程环境 | `HTTP_PROXY` / `HTTPS_PROXY` 指向 `127.0.0.1:7899`；userinfo 已脱敏 |
| 进程环境 | `NO_PROXY=localhost,.localhost,127.0.0.1,127.0.0.0/8,[::1],::1` |
| `ALL_PROXY` | 未设置 |

本地监听端口对应进程：

| 端口 | PID | 进程 |
|---:|---:|---|
| 7897 | 9660 | `com.vortex.helper` |
| 7899 | 20264 | `Qoder CN` |
| 10086 | 61776 | `SangforCSClient` |

PAC 服务返回 200，内容长度 14070 字符。只检查了结构和指令计数，没有输出原始 PAC 内容：未识别到普通 `PROXY`、`DIRECT`、`HTTPS`、`SOCKS` 关键字或常见域名 token。其编码/压缩方式和实际分流语义仍未知。

## 4. VPN 登录后快照

测量时间：2026-11-25 22:43:04（UTC+08:00）。EasyConnect 已登录，Crater 网页可访问。

| 对比项 | 连接前 | 登录后 |
|---|---|---|
| Sangfor 适配器 | Disconnected | Disconnected |
| McAfee / QMTAP / UU TAP | Disconnected | Disconnected |
| 默认路由 | 仅 WLAN | 仅 WLAN，下一跳 `<gateway>` |
| `<cluster-subnet>` 路由 | 无 | 无 |
| 本机 `192.168.5.*` 地址 | 无 | 无 |
| 集群域名 DNS | `198.18.0.74` | `198.18.0.74` |
| 浏览器访问 Crater | 可用 | 可用 |
| 全局/分流结论 | 无法判定 | 仍无法判定 |

结论：确认了 EasyConnect 登录态和平台可达性，但没有证据表明系统级 VPN 隧道已建立。后续集群操作使用现有浏览器认证和平台 ingress；SSH 端点虽可达，但用户认证未通过。

## 5. 如何完成只读复测

用户连接 EasyConnect 后，在 Windows PowerShell 中执行以下只读查询，并与第 2 节比较：

```powershell
Get-NetAdapter |
    Where-Object { $_.InterfaceDescription -match 'Sangfor|VPN|TAP' } |
    Select-Object Name, InterfaceDescription, ifIndex, Status

Get-NetRoute -AddressFamily IPv4 |
    Where-Object { $_.DestinationPrefix -eq '0.0.0.0/0' } |
    Select-Object ifIndex, InterfaceAlias, DestinationPrefix, NextHop, RouteMetric

Get-NetRoute -AddressFamily IPv4 |
    Where-Object { $_.DestinationPrefix -like '192.168.5.*' } |
    Select-Object ifIndex, InterfaceAlias, DestinationPrefix, NextHop, RouteMetric

Get-DnsClientServerAddress -AddressFamily IPv4 |
    Where-Object { $_.ServerAddresses.Count -gt 0 } |
    Select-Object InterfaceIndex, InterfaceAlias, ServerAddresses

Resolve-DnsName gpu.act.buaa.edu.cn -Type A
Find-NetRoute -RemoteIPAddress <cluster-host>
```

判定原则：

- 若 VPN 连接后新增更具体的 `<cluster-subnet>` 路由，而默认路由仍主要由 WLAN 承担，支持**分流路由**判断。
- 若 VPN 接管默认路由或大量非集群网段，支持**全局/大范围接管**判断。
- 若 DNS 仍返回 fake-IP，需同时检查本地代理规则；不能把代理 fake-IP 当作 VPN 路由证据。
- 若 Sangfor 适配器仍为 Disconnected，则根本没有可比较的 VPN 连接后状态。

## 6. 对 CASR 的影响

- 本次实际远程执行通过 Jupyter Lab 官方 Terminal 完成；该路径不依赖本地 `HTTP_PROXY` 环境变量。
- 标准 OpenSSH/SCP 仍受 VPN 路由和用户密钥认证影响；在公钥注册完成前，不反复尝试 SSH。
- 不使用 `route add`、`netsh` 修改、关闭安全软件或更改代理密码来“修复”网络。
- 真实 SSH 测试的前置条件是：运行中的开发作业 + 页面提供的实际 IP/端口/用户名 + 已注册并验证的公钥。
