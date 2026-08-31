# tauri/develop — 开发工作流、调试、资源、sidecar、测试、构建、v1→v2 迁移与规划

目的：用户说「tauri dev 不热更新」「怎么调 Rust 端」「资源找不到」「sidecar 打包」「给 command 补测试」「升级到 v2」「帮我规划一个 Tauri 应用」，或 target 里出现 `bundle.resources`/`externalBin`/`tauri::test`/`tauri migrate` 痕迹时加载。只讲工作流与迁移；体积/IPC/启动规则见 [../tauri.md](../tauri.md)（TA-01..46），平台差异见 [../xplat.md](../xplat.md)，签名/公证/updater/CI 发布见 [../ship.md](../ship.md)（SH-07..15），子进程通则见 [../process.md](../process.md)（PR-01..12），本文不重复。以 Tauri 2.11.x 为准。

## dev/build 工作流

1. `tauri dev` 做三件事：跑 `build.beforeDevCommand` → 等 `build.devUrl` 可达 → `cargo build` 并启动。前端 HMR 是前端工具链的事；Rust 源或 `tauri.conf.json` 变动触发 Rust 重编译 + 进程重启（`--no-watch` 关掉；配合外部调试器附加时必须关）。不配 `devUrl` 只配 `frontendDist`（目录）时，CLI 起内建 dev server 托管该目录并做整页热重载（不是模块级 HMR，也不是从磁盘直读）；它 watch 的是 `frontendDist` 本身——那里放的若是构建产物，改源码仍要重跑 `beforeDevCommand` 才刷新。
2. 参数分界：`tauri dev -- --features x -- --app-flag`——第一个 `--` 后给 cargo，第二个 `--` 后给应用。`--release` 用 release profile 跑 dev（复现只在 release 出现的 bug），`-e/--exit-on-panic` 让 panic 直接退出而不是卡住窗口。
3. `tauri build`：`--debug` 用 debug profile 打包（保留 devtools、`debug_assertions`、符号，排查「release 才坏」的首选）；`--no-bundle` 只出可执行；`-b app,dmg,nsis,msi,deb,rpm,appimage` 选产物；`-t <triple>` 指定目标（`universal-apple-darwin` 需先 `rustup target add` 两个架构）；`--ci` 跳过交互提示；`-c '{"identifier":"com.x.nightly"}'` 或 `-c path.json` 叠加配置（JSON Merge Patch，RFC 7396）做 nightly/beta 渠道变体，平台固定差异放 `tauri.<macos|windows|linux>.conf.json`。
4. `tauri build` 会自动注入 `--features tauri/custom-protocol`（决定「嵌入 `frontendDist`」还是「加载 `devUrl`」）；绕过 CLI 直接 `cargo build --release` 得到的二进制仍去连 dev server——这是调试器配置里 `--no-default-features` 的来历（见下）。
5. `tauri info` 先于任何版本类 issue：一次打出 CLI/`tauri` crate/`@tauri-apps/api`/WebView2/rustc 版本。

## 调试

- devtools：debug 构建默认可用（右键 Inspect / `Ctrl+Shift+I` / mac `Cmd+Option+I`）；release 要 `tauri = { features = ["devtools"] }`，mac 上它走私有 API，App Store 审核拒——只在内部渠道开。代码里 `webview_window.open_devtools()` / `close_devtools()` / `is_devtools_open()`。
- webview 的 `console.log` 不进终端。要么开 devtools，要么 `tauri-plugin-log` 双向：Rust 端 `Target::new(TargetKind::Webview)` 把 `log::*` 推进浏览器控制台（JS `attachConsole()`），JS 端 `@tauri-apps/plugin-log` 的 `info()` 进 Rust 日志与 `TargetKind::LogDir`。`RUST_LOG` 只对 `env_logger`/`tracing_subscriber::EnvFilter` 生效，plugin-log 用 builder `.level()`；`RUST_BACKTRACE=1 cargo tauri dev` 看 panic 栈。
- CrabNebula devtools（`tauri-plugin-devtools`）看 IPC 调用、事件、span：只在 `#[cfg(debug_assertions)]` 下注册且必须是**第一个** `.plugin()`；它和 `tauri-plugin-log` 都抢全局 logger，二选一用 cfg 切换。
- VS Code 断点：codelldb（Windows MSVC 用 `cppvsdbg` 指向 `target/debug/<app>.exe`）。`preLaunchTask` 起前端 dev server（tasks.json 里 `isBackground: true` + problemMatcher 判就绪），否则 webview 连不上 `devUrl` 白屏。调试器直接 `cargo build` 绕过了 CLI：`beforeDevCommand`、平台配置合并、sidecar 复制都不发生，靠 task 补齐或先跑一次 `tauri dev` 生成 `gen/`。

```json
{
  "version": "0.2.0",
  "configurations": [{
    "type": "lldb", "request": "launch", "name": "tauri dev (lldb)",
    "cargo": { "args": ["build", "--manifest-path=./src-tauri/Cargo.toml", "--no-default-features"] },
    "preLaunchTask": "ui:dev"
  }]
}
```

## 资源与图标（TA-33）

1. `bundle.resources` 两种形：数组 `["assets/*.json", "../data/models/*"]` 会把 `../` 保留为 `_up_/` 前缀；映射 `{"../data/models/": "models/"}` 才能控制目标路径——跨出 `src-tauri` 的资源一律用映射形。
2. 运行时只用 path API 取：Rust `app.path().resolve("models/small.bin", BaseDirectory::Resource)?`（`use tauri::{Manager, path::BaseDirectory}`），JS `resolveResource('models/small.bin')`（`@tauri-apps/api/path`）+ plugin-fs 读取需 `fs:allow-resource-read-recursive`。**禁止** `std::env::current_dir()` 或相对路径：Finder 启动的 CWD 是 `/`，Linux 桌面启动器是 `$HOME`，`tauri dev` 下才碰巧是 `src-tauri`（XP-04）。
3. 小静态数据（几十 KB 的 schema、模板）`include_str!`/`include_bytes!` 进二进制，不走 resources——少一处路径解析和一类「安装后找不到」bug。
4. 图标：`tauri icon ./app-icon.png`（1024×1024 透明 PNG）生成 `src-tauri/icons/` 全套并对应 `bundle.icon` 列表；Windows 必须有 `icon.ico`（也是窗口图标），iOS 不允许透明用 `--ios-color` 填底。运行时托盘/窗口换图标用 `tauri::include_image!("icons/x.png")`（需 `image-png` feature）。

## sidecar（TA-32）

- 文件名规则：`bundle.externalBin: ["binaries/my-node-app"]` 不带后缀；磁盘上每个目标一份 `binaries/my-node-app-<triple>`（Windows 再加 `.exe`：`my-node-app-x86_64-pc-windows-msvc.exe`），triple 用 `rustc -vV | sed -n 's|host: ||p'` 取。universal mac 包需两份架构文件。打包器去掉后缀，运行时 Rust `app.shell().sidecar("my-node-app")` 只写程序名，JS `Command.sidecar('binaries/my-node-app')` 写 externalBin 里的完整路径——两边不一致是首次上线必踩的坑（XP-07）。
- 权限：JS 端 `.execute()` 要 `shell:allow-execute`、流式 `.spawn()` 要 `shell:allow-spawn`，scope 条目 `{ "name": "binaries/my-node-app", "sidecar": true, "args": ["--port", { "validator": "^[0-9]+$" }] }`；`args: true` 等于放开任意参数，只在原型期用；`kill()`/`write()` 另需 `shell:allow-kill`/`shell:allow-stdin-write`。Rust 端 spawn 不过 ACL——默认在 Rust 里起进程、前端只调一个薄 command，前端 scope 就不用开。
- 生命周期（PR-03）：在 `setup` 里 spawn，`CommandChild` 放 managed state，`RunEvent::Exit` 时 kill；`tauri dev` 重编译是直接杀父进程，`Exit` 不会触发——sidecar 自己监听 stdin EOF 退出（Node：`process.stdin.on('end', () => process.exit())`），否则每次重编译留一个孤儿占着端口。端口用 `0` 让 sidecar 自选并从 stdout 第一行回报。

```rust
use std::sync::Mutex;
use tauri::{Manager, RunEvent};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};

struct Sidecar(Mutex<Option<CommandChild>>);

fn spawn_sidecar(app: &tauri::AppHandle) -> Result<(), tauri_plugin_shell::Error> {
    let (mut rx, child) = app.shell().sidecar("my-node-app")?.args(["--port", "0"]).spawn()?;
    app.state::<Sidecar>().0.lock().unwrap().replace(child);
    tauri::async_runtime::spawn(async move {
        while let Some(ev) = rx.recv().await {
            match ev {
                CommandEvent::Stdout(line) => log::info!(target: "sidecar", "{}", String::from_utf8_lossy(&line)),
                CommandEvent::Terminated(p) => { log::warn!("sidecar exited: {:?}", p.code); break; }
                _ => {}
            }
        }
    });
    Ok(())
}

// lib.rs run()：.manage(Sidecar(Mutex::new(None))).setup(|app| Ok(spawn_sidecar(app.handle())?))
//   .build(tauri::generate_context!()).expect("invariant: tauri builder")
//   .run(|app, ev| if let RunEvent::Exit = ev {
//       if let Some(c) = app.state::<Sidecar>().0.lock().unwrap().take() { if let Err(e) = c.kill() { log::warn!("kill sidecar: {e}") } }
//   });
```

- stdout 是字节行（`Vec<u8>`，默认按行切；`set_raw_out(true)` 关掉）；Node 端每条消息 `console.log(JSON.stringify(msg))` 一行一 JSON，避免半行拼接。转发给前端走 `tauri::ipc::Channel`（TA-06），不是 `emit` 风暴。
- Node.js 打包取舍（先问能否直接用 Rust crate——sidecar 给安装包加 40–90MB 且要单独签名）：

| 方案 | 产物与交叉 | 坑 |
|---|---|---|
| `@yao-pkg/pkg`（vercel/pkg 已归档） | 一次 `--targets node20-macos-arm64,node20-win-x64,…` 多平台 | ESM 支持弱；native addon 要随包 |
| `bun build --compile --target=bun-<os>-<arch>` | 单命令交叉出三端 | Bun 非 Node，依赖兼容度逐个验证 |
| `node --experimental-sea-config` | 复制 node 二进制 + postject 注入，只能本机平台 | 官方但步骤多，CI 每平台各跑 |

- macOS 公证：bundler 会签 `externalBin`，但 Node/Bun 的 JIT 需要 entitlements `com.apple.security.cs.allow-jit` + `allow-unsigned-executable-memory`，否则 sidecar 起不来且只在公证版本复现（SH-09）。

## 同二进制 worker（TA-43，优先于 sidecar）

需要隔离崩溃域但不想多一个可执行文件时：同一个 exe 在进入 `tauri::Builder` **之前**按 argv 分发（如 `--app-worker`），打包只产一个二进制。sidecar（TA-32）留给真正的外部运行时（Node/ffmpeg）。

- Windows release 保留 `#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]`（否则每次启动闪黑控制台）。GUI-subsystem 子进程仍能经 STARTUPINFO 继承管道拿到 stdin/stdout，不必再加 `CREATE_NO_WINDOW`；debug（console subsystem）父子共享控制台也不闪窗。从 GUI 父进程再 spawn **别的** console-subsystem 二进制才会闪窗，那时才补 `CREATE_NO_WINDOW`（XP-07、TA-46）。
- Unix 可用 `nice` 降优先级：`nice` exec 原进程（pid、管道、cwd 不变）。spawn 时 `.env_clear()` + `current_dir(control_root)`：worker 不依赖 PATH，脚本只用内建或绝对路径（PR-01）。
- **池规则（PR-03）**：只有协议正常走完（消费了 terminal 行 / `Ok`）的 worker 才回池；超时、强杀、协议错、崩溃一律 drop = kill + wait。超时/取消时 worker 往往仍在处理上一单，回池会让下一单读到上一单的输出。
- `Child::kill` 只杀直接子进程：worker 内不得再派生孙进程（杀不掉、回池后端口仍占）。

## 回环端口（TA-44）

偏好端口只是起点。`listen(127.0.0.1:pref)` 遇 `AddrInUse` 必须绑 `127.0.0.1:0`、把实际端口写入日志/persisted state，**不要**把绑定失败返回 setup——无单实例插件时双开或端口被占会让整个应用以 panic 启动失败。发现协议（若有）只回端口，不回会话令牌。

## 依赖升级（TA-29）

1. 成对升级：`@tauri-apps/cli` 与 `tauri`/`tauri-build` crate 同 minor；每个插件的 `tauri-plugin-<name>` 与 `@tauri-apps/plugin-<name>` 同 minor——只升一边的症状是 IPC 报 `command not found`/参数反序列化失败。`npm outdated`、`cargo update -p tauri -p tauri-build`（全量 `cargo update` 看 lock diff，DEP-07），`tauri info` 核对。
2. `tauri migrate` 不只做 v1→v2：beta→rc→stable 的权限标识改名（`window:allow-*` → `core:window:allow-*`、`app:default` → `core:default`）也由它改。

## 测试（TA-38）

- 命令做薄：`#[tauri::command]` 只解包参数、调纯函数、映射错误；纯函数用普通 `#[test]`，不需要任何 tauri 夹具（WS-04、TEST-10）。下面的 IPC 测试只用来锁「序列化契约」。
- Rust 端：`[dev-dependencies] tauri = { version = "2", features = ["test"] }`，`mock_builder()` 给出 `MockRuntime`，`mock_context(noop_assets())` 不读 `tauri.conf.json`，`WebviewWindowBuilder` 建的是假 webview，不弹窗、CI 无头可跑；`get_ipc_response` 直接过 invoke handler。`State<T>` 要在 builder 上 `.manage()`；插件命令在 mock 下不解析 capabilities，不要拿它测 ACL。

```rust
#[tauri::command]
fn ping() -> &'static str { "pong" }

#[cfg(test)]
mod tests {
    use tauri::{ipc::{CallbackFn, InvokeBody}, test::{get_ipc_response, mock_builder, mock_context, noop_assets, INVOKE_KEY}};
    use tauri::{webview::InvokeRequest, WebviewUrl, WebviewWindowBuilder};

    #[test]
    fn ping_returns_pong() {
        let app = mock_builder()
            .invoke_handler(tauri::generate_handler![super::ping])
            .build(mock_context(noop_assets()))
            .unwrap();
        let webview = WebviewWindowBuilder::new(&app, "main", WebviewUrl::default()).build().unwrap();
        let res = get_ipc_response(&webview, InvokeRequest {
            cmd: "ping".into(), callback: CallbackFn(0), error: CallbackFn(1),
            url: "http://tauri.localhost".parse().unwrap(), body: InvokeBody::default(),
            headers: Default::default(), invoke_key: INVOKE_KEY.to_string(),
        }).map(|b| b.deserialize::<String>().unwrap());
        assert_eq!(res, Ok("pong".into()));
    }
}
```

- 前端单测：`@tauri-apps/api/mocks` 的 `mockIPC((cmd, args) => …)` 拦 `invoke`，`mockWindows('main', 'settings')` 伪造窗口元数据，`mockConvertFileSrc('windows')` 固定协议前缀；`afterEach(clearMocks)` 否则 mock 串测试（TEST-09）。jsdom 缺 `crypto.getRandomValues` 时在 setup 里把 `node:crypto` 的 `webcrypto` 挂到 `window.crypto`。
- WebDriver 端到端：`cargo install tauri-driver --locked`，监听 4444，capability `'tauri:options': { application: '<编译出的可执行路径>' }`（不是 bundle，先 `cargo tauri build --debug --no-bundle`）。Linux 要 `webkit2gtk-driver`（WebKitWebDriver），CI 里 `xvfb-run --auto-servernum --server-args="-screen 0 1280x720x24" npm run e2e`；Windows 要和已装 WebView2 同版本的 `msedgedriver.exe`（`--native-driver`）；`tauri-driver` 直连只覆盖 Linux/Windows（**macOS 无 WKWebView 驱动**），mac 要跑 e2e 改走 `@wdio/tauri-service` 默认的应用内嵌 WebDriver（由 `tauri-plugin-wdio-webdriver` 提供，各平台都不需要外部驱动）或 CrabNebula 的跨平台 fork（mac 需付费 key）；仍按 TEST-07：驱动缺失要 fail-loud 或 `#[ignore]`，禁静默绿。

## 构建产物与平台（TA-28）

| 平台 | 产物 | 必知 |
|---|---|---|
| macOS | `.app`、`.dmg`；`-t universal-apple-darwin` 双架构 | `bundle.macOS.minimumSystemVersion` 默认 10.13；universal ≈ 双体积（TA-05）；必须在 mac 上打 |
| Windows | NSIS `.exe`（默认，可从 Linux/mac 交叉）、MSI（WiX，仅 Windows 上打） | `bundle.windows.webviewInstallMode`：`downloadBootstrapper`（默认，装机需联网）/`embedBootstrapper`（+1.8MB）/`offlineInstaller`（+127MB）/`fixedRuntime`；`nsis.installMode` `currentUser`/`perMachine`/`both` |
| Linux | `.deb`、`.rpm`、`.AppImage` | deb/rpm 依赖 `libwebkit2gtk-4.1-0`、`libgtk-3-0`，托盘再加 `libayatana-appindicator3-1`；在**最老的**目标发行版上打（glibc 下限，CI 用 `ubuntu-22.04`）；AppImage 不带 gstreamer 除非 `bundleMediaFramework` |

- `identifier`（反域名）决定应用数据目录、updater、深链、签名 bundle id——发布后改等于用户数据「丢失」+ 更新链断裂，规划期定死。`version` 可省略回退 Cargo.toml，避免两处漂移（SH-11）。
- 三端 CI 用 tauri-action（SH-07）；签名、公证、updater 密钥与 `latest.json` 闭环全按 SH-08..SH-12，本文不展开。

## v1→v2 迁移（TA-39）

`cargo install tauri-cli --version '^2' --locked`（或 `npm i -D @tauri-apps/cli@latest`）→ `cargo tauri migrate` → 读 diff → 手工项 → `tauri dev` 冒烟每个窗口与每条 IPC。Tauri 2 自身 MSRV 1.77.2，本规范仍按 edition 2024 / ≥1.85 起步（DEP-08）。

| v1 | v2 | migrate 自动? |
|---|---|---|
| `tauri.*`（`windows`/`security`/`systemTray`） | `app.*`（`app.windows`/`app.security`/`app.trayIcon`） | ✓ |
| `package.productName/version`、`tauri.bundle.identifier` | 顶层 `productName`/`version`/`identifier`；`tauri.bundle` → 顶层 `bundle` | ✓ |
| `build.distDir`/`build.devPath`/`build.withGlobalTauri` | `build.frontendDist`/`build.devUrl`/`app.withGlobalTauri` | ✓ |
| `tauri.allowlist.*` | 删除 → 生成 `src-tauri/capabilities/migrated.json` | ✓ 生成；收敛到最小权限（TA-12）✗ |
| `tauri.updater` | `plugins.updater` + `bundle.createUpdaterArtifacts`（`"v1Compatible"` 沿用旧签名格式） | ✓ |
| `@tauri-apps/api/tauri` | `@tauri-apps/api/core`（`invoke`、`convertFileSrc`） | ✓ |
| `@tauri-apps/api/{fs,shell,dialog,http,os,process,notification,clipboard,globalShortcut,updater,cli}` | `@tauri-apps/plugin-*` + `tauri-plugin-*` + `.plugin(init())` + capability 权限 | ✓ 装依赖/注册/改 import；scope 与权限收敛 ✗ |
| `appWindow`、`WebviewWindow` 自 `api/window` | `getCurrentWindow()`；`WebviewWindow`/`getCurrentWebviewWindow()` 自 `api/webviewWindow` | 部分 |
| CSP `connect-src` | 加 `ipc: http://ipc.localhost` | ✓ |
| `tauri::api::path::app_data_dir(&config)` | `app.path().app_data_dir()`（`Manager::path`） | ✗ |
| `tauri::api::{process, shell::open, dialog, http}` | `tauri_plugin_shell` / `tauri_plugin_opener` / `tauri_plugin_dialog` / `tauri_plugin_http`（或直接 reqwest） | ✗ |
| `Window`/`WindowBuilder`、`app.get_window` | `WebviewWindow`/`WebviewWindowBuilder`、`get_webview_window` | ✗ |
| `app.emit_all`/`window.emit`/`listen_global` | `app.emit`（`use tauri::Emitter`）/`emit_to(label, …)`/`listen_any`（`use tauri::Listener`） | ✗ |
| `tauri::SystemTray`/`tauri::Menu`/`CustomMenuItem` | `tauri::tray::TrayIconBuilder`（feature `tray-icon`）/`tauri::menu::{MenuBuilder, MenuItem}` | ✗ |
| `tauri::Icon` | `tauri::image::Image`/`include_image!`（feature `image-png`） | ✗ |
| `register_uri_scheme_protocol(\|app, req\| …)` | `register_uri_scheme_protocol(\|ctx, req\| …)` 或 `register_asynchronous_uri_scheme_protocol`；Windows/Android 下 URL 是 `http://<scheme>.localhost/`，前端取路径走 `convertFileSrc` | ✗ |
| 单 `main.rs` | `lib.rs` `#[cfg_attr(mobile, tauri::mobile_entry_point)] pub fn run()` + `main.rs` 转调，`crate-type = ["staticlib","cdylib","rlib"]`（移动端前提） | ✗ |
| `tauri-build = "1"` | `tauri-build = "2"`（与 `tauri` 同 minor） | ✗ |
| beta/rc：`window:allow-*`、`app:default` | `core:window:allow-*`、`core:default` | ✓（beta→stable 同样跑 migrate） |

迁移后必查：`migrated.json` 是 allowlist 的 1:1 翻译，通常放开了远超需要的 `fs`/`shell` 面（TA-12）；async command 里 `State<'_, T>` 生命周期必须显式写；`Emitter`/`Listener`/`Manager` 三个 trait 不 `use` 进来方法就「不存在」。

## 规划（写码前一页纸）

Rust 端仍先答 [../shape.md](../shape.md) 的四问（落点/类型/错误/并发）；Tauri 项目在其上叠加下面 8 行，产出一页设计小结，不写码：

1. 需求 → 能力清单 + **不做**清单（哪些留给系统浏览器/外部工具）。
2. 平台集合要有证据（发布目标、用户、CI）：是否含 mobile 在 day 0 定——mobile 没有 shell/sidecar/tray/menu/global-shortcut，入口必须是 `lib.rs`；CI 矩阵只覆盖声明平台（XP-03）。
3. 前端：按三引擎交集开发（XP-01），框架体积对得起 UI 复杂度（TA-04）。
4. 插件清单：每项 = Cargo crate + npm 包同 minor + `.plugin(init())` + capability 权限；能用 Rust crate 直接实现的不上 sidecar。
5. capabilities 草案：按窗口 label 分文件、只开用到的 `allow-*` + scope（TA-12）；`identifier` 一次定终身。
6. 窗口拓扑：label 表、谁创建谁、首窗 `visible: false` ready 后 show（TA-10）、关闭语义（隐藏到托盘 vs 退出）。
7. 状态归属：跨窗口/需持久化/需鉴权的状态以 Rust `manage` 为单一真相，event 只发「失效通知」让前端重新 invoke；纯视图状态留前端；通道按 TA-06 选。
8. 任务清单：先竖切「一个 command + 一个窗口 + 一个权限 + `tauri build --debug` 出包」跑通三端，再铺功能。

## 验证

dev：改一行 Rust 看到重编译重启、改一行前端只有 HMR；资源：`tauri build --debug` 后从 Finder/资源管理器/桌面启动器（非终端）启动能读到资源；sidecar：`tauri dev` 连续改两次 Rust 后 `pgrep -f my-node-app` 只剩一个（PR-12）；测试：`cargo test` 无窗口环境通过，Linux e2e 在 xvfb 下通过；迁移：每个窗口、每条 IPC、每个插件权限各冒烟一次并记录 `migrated.json` 收敛前后权限条数。
