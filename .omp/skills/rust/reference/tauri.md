# /rust-skills:rust tauri [target] — Tauri v2 应用优化

目的：在有 Tauri 2.x 依赖和相关目标时审查体积、IPC、启动与运行时，以及权限面、命令/事件契约、窗口集成、插件接线与移动端。现行稳定线 **2.11.x**（crates.io 2.11.5，2026-07）；v1 结构（`tauri.allowlist`、`emit_all`、`@tauri-apps/api/tauri`）是迁移债务。`removeUnusedCommands` 从 2.4 起可用，不是新命令门槛。本文件是 owner：先按 TA 清单体检，再按「深入」表只加载命中的 1–2 个 `tauri/` 子 playbook。跨平台差异按需加载 [xplat.md](xplat.md)，签名/公证/updater 发布链走 [ship.md](ship.md)；不因技术栈自动扩到三端发布。
不要读：Cargo.toml、`src-tauri/` 与当前改动都没有 Tauri 证据时停。

## TA 检查单（体检输出：位置｜编号｜问题｜修复）

编号定义在本文件。细节只在命中的 1–2 个子 playbook 里读，不要整目录读 `reference/tauri/`。

**体积 / IPC / 启动（门）**

- TA-01 `src-tauri/Cargo.toml` release profile（官方推荐起步，改动实测定夺 META-02）：`codegen-units = 1`、`lto = true`（内存不足改 `"thin"`）、`opt-level = "s"`、`panic = "abort"`、`strip = true`。
- TA-02 `tauri.conf.json` → `"build": { "removeUnusedCommands": true }`（≥2.4）。
- TA-03 feature 裁剪：tauri 本体与插件按需；`cargo tree -d` 审重复依赖（DEP-06）。
- TA-04 前端包：tree-shaking + 代码分割 + 资产压缩；小 UI 上重框架是 SIMP-01 违例。
- TA-05 度量：各平台 bundle 实物尺寸 + `cargo bloat` 前后对比。
- TA-06 通道选型：小请求-响应 → command；生命周期/小状态广播 → event；**流式/高频/大块数据 → `tauri::ipc::Channel`**。
- TA-07 二进制大块：返回 `tauri::ipc::Response`（raw bytes）绕开 JSON；媒体走 asset protocol。
- TA-08 IPC 负载预算：单条 payload 上限自定并注释（如 ≤256KB），超限改流式/协议方案。
- TA-09 命令默认 `async fn`；重 CPU → `spawn_blocking`（ASYNC-03）；`State<T>` 内锁遵守 ASYNC-02。阻塞原生对话框例外见 TA-41。
- TA-10 感知启动：主窗 `visible: false`、ready 后再 show；重初始化移出启动路径。
- TA-11 事件风暴治理：高频进度类更新后端聚合、前端节流/合帧后再渲染。
- TA-12 权限最小面：capabilities/ACL 只开用到的权限——既是安全加固，也放大 TA-02 的裁剪效果。
- TA-13 前后端类型同步：command 签名用 tauri-specta 生成 TS bindings，前端禁裸字符串 `invoke("cmd", {...})`。

**权限 / 命令 / 窗口 / 插件 / 移动端 — 一句话 + 子 playbook**

- TA-14 capability 条目与前端实际调用一一对应；禁用 `*:allow-all`、堆 `<plugin>:default`、`windows: ["*"]` 挂 fs/shell/http。详见 [tauri/security.md](tauri/security.md)。
- TA-15 fs/http/shell/opener 权限用带 scope 的对象形式；写 scope 禁 `$RESOURCE`/`$EXE`，读 scope 禁 `$HOME/**` 与裸 `**`；`shell:allow-execute` 的 `args` 写数组 validator，`args: true` 只许内部工具。详见 [tauri/security.md](tauri/security.md)。
- TA-16 远程内容默认零 IPC；禁回到 v1 `dangerousRemoteDomainIpcAccess`。详见 [tauri/security.md](tauri/security.md)。
- TA-17 生产 `app.security.csp` 禁止为 null：`connect-src` 必含 `ipc: http://ipc.localhost`；开发期放宽只写 `devCsp`。详见 [tauri/security.md](tauri/security.md)。
- TA-18 ACL 不校验命令参数：收路径的应用命令 canonicalize 后与 app 目录比对（XP-05、API-08）。详见 [tauri/security.md](tauri/security.md)。
- TA-19 `.invoke_handler()` 只能调一次；`async fn` 命令禁借用参数。详见 [tauri/ipc.md](tauri/ipc.md)。
- TA-20 命令错误类型必须 `Serialize`；前端 `catch` 到的是 `unknown`，禁 `err.message`。详见 [tauri/ipc.md](tauri/ipc.md)。
- TA-21 `manage` 按类型唯一且重复 manage 静默失败；`State<'_, T>` 不能 move 进 `spawn`。详见 [tauri/ipc.md](tauri/ipc.md)。
- TA-22 v2 的 `emit` 在 `AppHandle` 与 `WebviewWindow` 上都是广播，定向必须 `emit_to`/`emit_filter`。详见 [tauri/ipc.md](tauri/ipc.md)。
- TA-23 新建窗口的 label 必须进某个 capability 的 `windows`。详见 [tauri/window.md](tauri/window.md) 与 [tauri/security.md](tauri/security.md)。
- TA-24 托盘常驻必须双保险：`CloseRequested` hide + `ExitRequested { code: None }` `prevent_exit`。详见 [tauri/window.md](tauri/window.md)。
- TA-25 托盘/菜单平台语义逐平台验收（XP-09）。详见 [tauri/window.md](tauri/window.md)。
- TA-26 启动路径上的插件：window-state 去掉 `VISIBLE`；single-instance 必须是 Builder 上第一个 `.plugin()`。详见 [tauri/window.md](tauri/window.md) 与 [tauri/plugins.md](tauri/plugins.md)。
- TA-27 `beforeDevCommand`/`devUrl`/`beforeBuildCommand`/`frontendDist` 四项来自同一框架文档并一起改；dev server 必须 `strictPort`。详见 [tauri/setup.md](tauri/setup.md)。
- TA-28 `identifier` 一开始就给 `[a-z0-9.]` 反域名真值（禁 `-`、禁 `.app` 结尾、禁默认 `com.tauri.dev`）。详见 [tauri/setup.md](tauri/setup.md)。
- TA-29 版本成对升级：`tauri`/`tauri-build`/`@tauri-apps/api`/`@tauri-apps/cli` 同 minor。详见 [tauri/develop.md](tauri/develop.md) 与 [tauri/plugins.md](tauri/plugins.md)。
- TA-30 插件四件缺一不可：Cargo + npm + `.plugin(init())` + capability。详见 [tauri/plugins.md](tauri/plugins.md)。
- TA-31 `src-tauri` 三件不可动：`[lib] crate-type` + `_lib` 后缀、`build.rs` 里 `tauri_build::build()`、`main.rs` 只调 `lib.rs` 的 `run()`。详见 [tauri/setup.md](tauri/setup.md) 与 [tauri/mobile.md](tauri/mobile.md)。
- TA-32 sidecar 命名两端不对称：`externalBin` 不带后缀、磁盘文件必须带 target triple。详见 [tauri/develop.md](tauri/develop.md) 与 [tauri/plugins.md](tauri/plugins.md)。
- TA-33 平台文件 `tauri.<os>.conf.json` 按 JSON Merge Patch 叠加且**数组整体替换**。详见 [tauri/setup.md](tauri/setup.md) 与 [tauri/develop.md](tauri/develop.md)。
- TA-34 `tauri-plugin-sql` 内部是 sqlx 池、连接不固定，`BEGIN/COMMIT` 跨 IPC 无效。详见 [tauri/plugins.md](tauri/plugins.md) 与 [sqlx.md](sqlx.md)。
- TA-35 真机调试：vite `server.host`/`hmr.host` 读 `TAURI_DEV_HOST`；禁止把 `devUrl` 硬编码成局域网 IP。详见 [tauri/mobile.md](tauri/mobile.md)。
- TA-36 `gen/android`、`gen/apple` 入库；密钥与 `build/` 必须 ignore。详见 [tauri/mobile.md](tauri/mobile.md)。
- TA-37 WASM 前端必须 `app.withGlobalTauri: true`；shared crate 必须能在 `wasm32-unknown-unknown` 编译。详见 [tauri/mobile.md](tauri/mobile.md)。
- TA-38 command 做薄：逻辑用普通 `#[test]`；`tauri::test::mock_builder` 不能拿来测 ACL。详见 [tauri/develop.md](tauri/develop.md)。
- TA-39 `tauri migrate` 生成的 `capabilities/migrated.json` 必须人工收敛到最小权限；见到 `tauri.allowlist` / `emit_all` 即迁。详见 [tauri/develop.md](tauri/develop.md) 与 [tauri/security.md](tauri/security.md)。
- TA-40 `app.path().app_data_dir()` 与 `app_local_data_dir()` 在 Windows 不是同一个目录（Roaming `%APPDATA%` vs Local `%LOCALAPPDATA%`）；手拼 env 必须与所用 API 逐字节一致，混用 = 锁/库分裂。详见 [xplat.md](xplat.md)。
- TA-41 同步 command 内联在事件循环（主线程）：阻塞原生对话框合法；`async fn` / `#[tauri::command(async)]` 跑在 tokio，禁 `rfd::FileDialog` 阻塞版。详见 [tauri/ipc.md](tauri/ipc.md)。
- TA-42 无托盘时 macOS 关窗 ≠ 退出：`CloseRequested` 要 `hide` + `prevent_close`，并接 `RunEvent::Reopen` 才 `show`+`set_focus`；Windows 关主窗默认退出，保持。详见 [tauri/window.md](tauri/window.md)。
- TA-43 同二进制 worker（argv 分发）优先于 sidecar；`Child::kill` 只杀直接子进程；协议未完成（超时/强杀）的 worker 禁回池。详见 [tauri/develop.md](tauri/develop.md) 与 [process.md](process.md)。
- TA-44 偏好端口 `listen` 遇 `AddrInUse` 必须回退 `127.0.0.1:0` 并记录实际端口，禁把绑定失败扩成 setup panic。详见 [tauri/develop.md](tauri/develop.md)。
- TA-45 原子替换：临时文件与目标同卷（否则 `EXDEV`）；Windows 不能 rename 覆盖已存在项，先 `remove` 或 move-aside。详见 [xplat.md](xplat.md)。
- TA-46 桌面打包：无 GUI 会话打 DMG 必须 `CI=true`（create-dmg `--skip-jenkins`）；mac 上 cargo-xwin 只出未签名 NSIS；GUI 父进程禁派 console 子进程除非 `CREATE_NO_WINDOW`。详见 [ship.md](ship.md)。

## 深入（按信号加载）

一次只加载 1–2 个；跨平台差异仍走 [xplat.md](xplat.md)，签名/公证/updater 发布链仍走 [ship.md](ship.md)。

| 用户信号/代码证据 | 加载 |
|---|---|
| 「新建项目 / 装环境 / 选前端框架 / dev 能跑 build 白窗」；`create-tauri-app`、`cargo tauri info\|init` 报错、`tauri.conf.json` 的 `build` 段、`next.config`/`nuxt.config`/`svelte.config`/`Trunk.toml` | [tauri/setup.md](tauri/setup.md) |
| `src-tauri/capabilities/*.json`、`app.security`、ACL 报错（`not allowed by ACL`）、自写插件 `permissions/`、persisted-scope、上线安全审计 | [tauri/security.md](tauri/security.md) |
| `#[tauri::command]`、`invoke(`、`listen(`、`app.emit`、`State<'_, T>`、`tauri::ipc::Channel`、tauri-specta、错误契约 | [tauri/ipc.md](tauri/ipc.md) |
| `app.windows`、`WebviewWindowBuilder`、`decorations: false`、`TrayIconBuilder`、`MenuBuilder`、window-state/positioner/single-instance；「白屏 / 启动页 / 托盘 / 多开」 | [tauri/window.md](tauri/window.md) |
| `tauri-plugin-*`、`@tauri-apps/plugin-*`、`<plugin>:allow-*`；「读文件 / 弹对话框 / 调外部命令 / 自动更新 / 扫码」 | [tauri/plugins.md](tauri/plugins.md) |
| `gen/android\|apple`、`#[cfg(mobile)]`、`mobile_entry_point`、`TAURI_DEV_HOST`、Trunk/Leptos/Yew/Dioxus、`wasm-bindgen` 调 `window.__TAURI__` | [tauri/mobile.md](tauri/mobile.md) |
| 「dev 不热更新 / 怎么调 Rust 端 / 资源找不到 / sidecar 打包 / 给 command 补测试 / 升级到 v2 / 规划一个 Tauri 应用」；`bundle.resources`、`externalBin`、`tauri::test`、`tauri migrate`；同 exe worker、`AddrInUse` | [tauri/develop.md](tauri/develop.md) |
| 「路径分裂 / LOCALAPPDATA / app_data_dir / EXDEV / Windows 覆盖 rename」 | [xplat.md](xplat.md) |
| 「rfd / FileDialog / 同步还是异步 command」 | [tauri/ipc.md](tauri/ipc.md) |
| 「关窗变隐形 / Dock 点不回来 / Reopen」 | [tauri/window.md](tauri/window.md) |
| 「DMG Finder 忙 / cargo-xwin / makensis / 交叉打 Windows」 | [ship.md](ship.md) |

## 验证（PERF-01，全部同机）

体积：前后 bundle 尺寸表；IPC：大负载往返计时前后对比；启动：冷启动到首帧毫秒数。权限：dev 下每个功能点走一遍 Console 无 `not allowed`，再删一条 allow 确认确实被拒；窗口/托盘/菜单按 XP-09 逐平台冒烟；命令契约用 `tauri::test` 锁定（TEST-10）。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

只读调用：各战场一节“现状 → 候选（TA 编号 + 关联全局规则号）→ 所需数据”。`--apply` 或明确“修/改/实现”时才落改动并给前后数据。残余只输出 RUST.md 债务候选，显式 `--record` 才写入。
