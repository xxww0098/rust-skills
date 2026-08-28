# tauri/setup — 环境、脚手架、前端选型与进程模型

目的：用户要「新建 Tauri 项目 / 装环境 / 选前端框架 / dev 能跑 build 白窗 / 解释 Tauri 怎么工作」，或代码证据是 `create-tauri-app`、`cargo tauri info|init|dev` 报错、`tauri.conf.json` 的 `build` 段、`next.config`/`nuxt.config`/`svelte.config`/`Trunk.toml` 时加载。只讲把项目跑起来之前的决策；体积/IPC/启动优化见 [../tauri.md](../tauri.md)（TA-01..46），webview 差异与平台 CI 见 [../xplat.md](../xplat.md)，权限面见 [security.md](security.md)，命令与事件见 [ipc.md](ipc.md)，移动端初始化见 [mobile.md](mobile.md)，日常开发见 [develop.md](develop.md)。

## 平台前置与 `cargo tauri info`

| 目标 | 必装 | 坑 |
|---|---|---|
| 通用 | rustup stable（≥1.85，DEP-08）；Node LTS ≥20（Vite 7 要 20.19+/22.12+）；纯 Rust 前端可无 Node | Tauri 2 自身 MSRV 1.77，本规范仍按 edition 2024 起步 |
| macOS | `xcode-select --install`（CLT 够桌面）；iOS 要完整 Xcode + `brew install cocoapods` + `rustup target add aarch64-apple-ios aarch64-apple-ios-sim x86_64-apple-ios` | 只有 CLT 跑 `tauri ios` 必失败；先 `sudo xcodebuild -license accept` |
| Windows | Visual Studio Build Tools 2022「使用 C++ 的桌面开发」+ Windows 11 SDK；WebView2 Runtime（Win 11 与更新过的 Win 10 自带）；rustup 用默认 msvc 工具链 | GNU 工具链不支持；离线目标机把 `bundle.windows.webviewInstallMode.type` 设 `embedBootstrapper` 或 `offlineInstaller` |
| Linux（Debian/Ubuntu） | `apt install libwebkit2gtk-4.1-dev build-essential curl wget file libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev` | `webkit2gtk-4.0` 是 v1 包名，v2 链 4.1（Fedora `webkit2gtk4.1-devel`、Arch `webkit2gtk-4.1`）；appindicator 只为托盘 |
| Android | Android Studio → SDK Manager 勾 Platform、Platform-Tools、Build-Tools、Command-line Tools、NDK (Side by side)；`JAVA_HOME` 指 Studio 自带 `jbr`，`ANDROID_HOME` 指 sdk 根，`NDK_HOME=$ANDROID_HOME/ndk/<版本号>`；`rustup target add aarch64-linux-android armv7-linux-androideabi i686-linux-android x86_64-linux-android` | 三个变量缺一 `tauri android init` 就报 Gradle/NDK 找不到；`NDK_HOME` 指到版本号目录，不是 `ndk/` 上一层 |
| iOS | 见 macOS 行；真机需 Apple Developer team 与签名 | Apple Silicon 模拟器用 `aarch64-apple-ios-sim`，不是 `x86_64` |

1. 自检只认 `cargo tauri info`（npm 项目 `pnpm tauri info`）：一次列出 OS/webview 版本、rustc、Node、`tauri`/`tauri-build`/`@tauri-apps/api`/`@tauri-apps/cli` 版本与 conf 摘要；报障先贴这份，不要逐个 `--version`。
2. 桌面包在各自 OS 上构建：macOS 包只能在 macOS 出，Windows 签名包在 Windows。mac/Linux→Windows 的 `cargo-xwin` 只出**未签名 NSIS**（SH-14/16），WiX/MSI 与 Authenticode 仍要 Windows。声明几端就要几端 CI（XP-03、SH-07）。WSL2 能跑 `tauri dev`，不能出 Windows 安装包。

3. Linux 黑/白窗（Nvidia、虚拟机）先用 `WEBKIT_DISABLE_DMABUF_RENDERER=1` 复现定位，确认是驱动问题再决定是否在启动代码里按条件设置。

## create-tauri-app：按手头工具选入口（TA-28、TA-29）

```bash
sh <(curl https://create.tauri.app/sh)            # bash/zsh，什么都没装：下载预编译二进制
irm https://create.tauri.app/ps | iex             # PowerShell
pnpm create tauri-app                             # 或 npm create tauri-app@latest / yarn create tauri-app / bun create tauri-app / deno run -A npm:create-tauri-app
cargo install create-tauri-app --locked && cargo create-tauri-app   # 纯 Rust 团队：全程无 Node，之后 cargo install tauri-cli --locked
pnpm add -D @tauri-apps/cli && pnpm tauri init    # 已有前端仓库只补 src-tauri/；四个提问就是 devUrl/frontendDist/beforeDevCommand/beforeBuildCommand
```

1. 非交互：`pnpm create tauri-app my-app --template react-ts --manager pnpm --identifier com.acme.myapp -y`。`--identifier` 一开始就给真值：默认 `com.tauri.dev` 同时决定 `app_data_dir` 路径与移动端包名，上线后改它等于换应用（用户数据目录搬家）。
2. identifier 只用 `[a-z0-9.]` 反域名：schema 虽允许 `-`，但 Java/Android 包名不接受，CLI 会静默改写掉而不是报错，桌面 / Android / iOS 三端 ID 就此分叉；不以数字开头。
3. 一个项目一个 CLI 来源：npm `@tauri-apps/cli` 与 `cargo tauri` 二选一写进脚本。`tauri`、`tauri-build`、`@tauri-apps/api`、`@tauri-apps/cli` 同 minor 一起升；`tauri-plugin-<x>` 与 `@tauri-apps/plugin-<x>` 成对升——JS 侧比 Rust 侧新会调到不存在的命令（DEP-07）。

## 项目结构与三份入口文件（TA-31）

```
src-tauri/
  Cargo.toml        [lib] crate-type 三项 + name 带 _lib 后缀
  build.rs          fn main() { tauri_build::build() }  —— 缺它 generate_context! 与 capabilities 都不编译
  tauri.conf.json   + 可选 tauri.{macos,windows,linux,android,ios}.conf.json（JSON merge patch 叠加）
  capabilities/     default.json 起步；"$schema": "../gen/schemas/desktop-schema.json" 拿编辑器补全
  icons/            cargo tauri icon app-icon.png 生成全套
  gen/              schemas/ 进 .gitignore；android/ apple/ 是可编辑原生工程，提交入库（mobile.md）
  src/main.rs       只调 run()
  src/lib.rs        Builder 组合根 + 命令
```

```toml
# src-tauri/Cargo.toml
[package]
name = "my-app"
version = "0.1.0"
edition = "2024"                                   # WS-05 / DEP-08

[lib]
name = "my_app_lib"                                # 与 bin 同名在 Windows 产物冲突
crate-type = ["staticlib", "cdylib", "rlib"]       # iOS 用 staticlib、Android 用 cdylib、桌面 bin 用 rlib；删任一项对应平台断

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri = { version = "2", features = [] }           # tray-icon / devtools / protocol-asset / isolation 用到才开（TA-03）
tauri-plugin-opener = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

```rust
// src/main.rs —— 零逻辑（WS-04）。release 隐藏 Windows 控制台后 println! 没有去处 → log 插件（OBS-01）
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
fn main() { my_app_lib::run(); }
```

```rust
// src/lib.rs —— 桌面 main 与移动端原生壳共用的唯一入口；mobile cfg 由 tauri-build 注入
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![greet])
        .run(tauri::generate_context!())
        .expect("invariant: app failed to start, nothing to recover"); // 进程入口，ERR-03 允许
}

#[tauri::command]
fn greet(name: &str) -> String { format!("Hello, {name}!") }
```

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "My App",
  "version": "0.1.0",
  "identifier": "com.acme.myapp",
  "build": {
    "beforeDevCommand": "pnpm dev",
    "devUrl": "http://localhost:1420",
    "beforeBuildCommand": "pnpm build",
    "frontendDist": "../dist"
  },
  "app": {
    "withGlobalTauri": false,
    "windows": [{ "label": "main", "title": "My App", "width": 960, "height": 640 }],
    "security": { "csp": null }
  },
  "bundle": { "active": true, "targets": "all", "icon": ["icons/icon.png"] }
}
```

1. 路径相对 `src-tauri/`，所以是 `../dist`。`dev`：先跑 `beforeDevCommand`，轮询 `devUrl` 可达才起窗口；`build`：先跑 `beforeBuildCommand`，再由 tauri-codegen 把 `frontendDist` 整目录嵌进二进制——目录不存在直接报错，不会出空包。无 `devUrl` 时 dev 直接从磁盘读 `frontendDist`，没有 HMR。
2. 顶层 `"tauri": {...}`、`tauri.allowlist` 是 v1 结构，v2 只有 `app` / `bundle` / `build` / `plugins`；`csp: null` 只许开发期，生产 CSP 见 [security.md](security.md)。
3. 生产里前端从 `tauri://localhost`（Windows 为 `http://tauri.localhost`）加载：`fetch('/api/…')` 这种同源相对调用没有后端接；客户端路由刷新依赖 SPA fallback；文件名大小写按 Linux 处理（XP-04）。

## 前端选型：默认 Vite，SSR 框架只能当 SPA 用（TA-27、TA-17）

Tauri 只加载一个静态目录：没有 Node 服务端、没有 API route、没有服务端渲染。SSR/全栈框架必须配成纯客户端静态导出；做不到就用 Vite。

| 框架 | 必需配置 | devUrl → 产物目录 | 坑 |
|---|---|---|---|
| Vite（React/Vue/Svelte/Solid/vanilla，默认） | `server: { port: 1420, strictPort: true, host: TAURI_DEV_HOST \|\| false, watch: { ignored: ["**/src-tauri/**"] } }`；`envPrefix: ["VITE_", "TAURI_ENV_*"]`；`build.target: TAURI_ENV_PLATFORM == "windows" ? "chrome105" : "safari13"` | `:1420` → `../dist` | 不设 `strictPort` 端口被占会自动 +1，Tauri 仍等 1420 → 白窗；不忽略 `src-tauri` → 每次 Rust 编译触发全量 reload |
| Next.js | `output: 'export'`；`images: { unoptimized: true }`；开发期 `assetPrefix: 'http://localhost:3000'`（真机用 `TAURI_DEV_HOST`） | `:3000` → `../out` | 产物是 `out/` 不是 `dist/`；API routes、middleware、服务端组件取数、无 `generateStaticParams` 的动态路由全部失效；`invoke` 只能在 `'use client'` + `useEffect` 里调（预渲染没有 `window`） |
| Nuxt | `ssr: false`；`devServer: { host: TAURI_DEV_HOST }`；`vite: { server: { strictPort: true } }` | `:3000` → `../dist` | 构建命令是 `nuxt generate`，`nuxt build` 出的是 Node server；`server/api` 不存在于包内 |
| SvelteKit | `@sveltejs/adapter-static` + `adapter({ fallback: 'index.html' })`；`src/routes/+layout.ts`：`export const ssr = false; export const prerender = true;` | `:1420` → `../build` | 默认 `adapter-auto` 不能用；`+page.server.ts`、`+server.ts` 端点不会跑 |
| Qwik | `pnpm qwik add static`（Qwik City 静态适配器）；vite `strictPort: true` | `:5173` → `../dist` | 没装静态适配器 `build` 不产出 `index.html` |
| Leptos/Yew/Sycamore（Trunk） | `rustup target add wasm32-unknown-unknown`；`Trunk.toml`：`[watch] ignore = ["./src-tauri"]`、`[serve] port = 1420, open = false, ws_protocol = "ws"`；`withGlobalTauri: true` | `trunk serve` `:1420` → `../dist`，`beforeBuildCommand: "trunk build"` | 没有 npm 包，IPC 走 `window.__TAURI__.core.invoke`（wasm-bindgen extern），不开全局对象就调不到；两个 `target/`（根与 src-tauri）互相不能 watch |

1. 四个 `build` 字段来自同一页框架文档，别混抄：`beforeDevCommand` 起 dev server，`devUrl` 给 Tauri 去连，`beforeBuildCommand` 出静态文件，`frontendDist` 告诉 codegen 去哪嵌。换框架后四项一起改。
2. `build.target` 跟 webview 下限走（Windows `chrome105`，其余 `safari13`），禁 `esnext`；这是 XP-01 交集纪律在构建配置上的落点。
3. `withGlobalTauri` 只在没有打包器时开（Trunk/wasm-bindgen、CDN 页面、纯 `<script>` 原型）；有 npm 的项目保持 `false`，从 `@tauri-apps/api/core` 按需 import——全局对象不可 tree-shake，且任何注入脚本都直接拿到 `invoke` 句柄。
4. 选型标准：已有 web 团队 → 沿用其栈的 Vite 模板；「需要 SEO/SSR」说明做的是网站不是桌面应用，壳里 SSR 收益为零；Rust-only 团队 → Leptos/Dioxus，接受 wasm 包体与调试成本。小 UI 上重框架违 TA-04/SIMP-01。

## 进程模型：为什么小、为什么要隔离（TA-16）

1. Core 进程 = 你的 Rust 二进制：事件循环、窗口/托盘/菜单、全部 OS 能力、ACL 裁决。WebView 进程 = 系统 webview（WKWebView / WebView2 / WebKitGTK）渲染的每个窗口，只能经 IPC 向 Core 要能力。栈：`tauri` → `tauri-runtime-wry` → `wry`（webview）→ `tao`（窗口）；`tauri-build` + `tauri-codegen` 在编译期把 conf、capabilities、`frontendDist` 嵌进二进制。
2. 体积小只有一个原因：不捆绑 Chromium/Node，渲染引擎借系统的。代价一并接受：三套引擎、版本由用户 OS 决定（发行版 WebKitGTK 最老、WebView2 常青自动更新、WKWebView 跟系统版本），前端按交集开发（XP-01）；体积优化本身是 TA-01..05。
3. IPC 两种原语：event（单向广播，无返回）与 command（`invoke` → `#[tauri::command]`，`Result` 映射到 Promise），负载 JSON 过界（TA-06..08）；机制与类型同步见 [ipc.md](ipc.md)，多窗口拓扑见 [window.md](window.md)。
4. **Brownfield（默认）**：webview 像普通浏览器一样跑你的前端，兼容一切 web 代码，安全边界完全靠 capabilities/ACL（TA-12）。**Isolation**：在前端与 Core 之间插一个沙箱 iframe 里的「隔离应用」，每条 IPC 先过它的 hook（校验/改写）再加密转发给 Core。

```json
"app": { "security": { "pattern": { "use": "isolation", "options": { "dir": "../dist-isolation" } } } }
```

```js
// dist-isolation/index.js（由同目录 index.html 引入）——零依赖、几十行、人能审完；Cargo 需开 tauri 的 isolation feature
window.__TAURI_ISOLATION_HOOK__ = (payload) => {
  if (!looksLegit(payload)) return sanitize(payload); // 契约只有「返回什么就过界什么」，没有拒绝出口：拦截 = 改写成无害内容 + 记日志
  return payload;                                     // 返回值 = 实际过界内容
};
// 抛异常不等于拒绝：消息不再转发，主窗口的 invoke 只是永远 pending，前端 catch 不到
```

5. 何时上 Isolation：前端含第三方/不可信脚本、依赖树大到供应链 XSS 可信、或加载远程内容——它是 ACL 之外最后一道可审计闸门，不是替代品。代价：每条 IPC 多一跳加解密；隔离应用必须零依赖。内部工具 Brownfield + 最小 capabilities 即可；远程域名访问 IPC 走 capability 的 `remote.urls`（security.md），不要回到 v1 的 `dangerousRemoteDomainIpcAccess`。

## 新项目决策清单（按序回答，答案落进 RUST.md facets；TA-30）

1. 平台集合：桌面哪几端？要不要移动端？→ 决定 identifier 合法性、`crate-type` 三项、CI 矩阵（XP-03）、webview 下限与 `build.target`。Tauri 能跨端不等于要声明三端；每多一端多一套冒烟（XP-09）。
2. 前端：按上表；SSR 框架必须能纯静态导出，否则 Vite。
3. 插件：只加用到的官方插件，三件套缺一不可——`cargo add tauri-plugin-<x>`、`pnpm add @tauri-apps/plugin-<x>`、`.plugin(tauri_plugin_<x>::init())`，再加 capability 的 `<x>:default`；缺 Rust 侧报 command not found，缺权限报 not allowed by ACL。桌面专属（global-shortcut、window-state、single-instance、autostart、updater、cli、positioner）与移动端专属（barcode-scanner、biometric、nfc、haptics）在 `lib.rs` 用 `#[cfg(desktop)]` / `#[cfg(mobile)]` 分支注册（XP-10）；清单见 [plugins.md](plugins.md)。
4. capabilities：`capabilities/default.json` 从 `core:default` + 各插件 `<x>:default` 起步，`windows` 只写真实 label；平台差异用 `"platforms": [...]` 拆文件，不是给大权限（TA-12，[security.md](security.md)）。
5. 发布链：签名/公证/updater 第一周就打通（SH-09..11），不是上线前；见 [../ship.md](../ship.md)。

## 验证

- `cargo tauri info` 声明平台对应行无红；`cargo tauri dev` 出窗口且 `greet` 往返成功 = 环境 + IPC 通；`cargo tauri build --debug` 在 `src-tauri/target/debug/bundle/` 出包 = `beforeBuildCommand`/`frontendDist` 对得上。
- 换前端框架后专门验 release 包而不是 dev：dev 走 `devUrl` 会掩盖静态导出失败。装到干净机器/VM，确认深层路由刷新不 404、`invoke` 可用、资源大小写无误。
- 移动端首跑 `cargo tauri android init && cargo tauri android dev`（iOS 同理）过即可，细节见 [mobile.md](mobile.md)。
