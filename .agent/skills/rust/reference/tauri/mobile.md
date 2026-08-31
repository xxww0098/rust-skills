# tauri/mobile — Android / iOS 与 WASM 前端

目的：代码里出现 `src-tauri/gen/android|apple`、`#[cfg(mobile)]`、`tauri::mobile_entry_point`、`TAURI_DEV_HOST`、Trunk/Leptos/Yew/Dioxus 或 `wasm-bindgen` 调 `window.__TAURI__`，或用户要跑 Android/iOS 时加载。只讲移动端与 WASM 前端特有的坑：体积/IPC/启动通则见 [../tauri.md](../tauri.md)（TA-01..46），桌面三 webview、路径与 CI 矩阵见 [../xplat.md](../xplat.md)（XP-01..12）。

## 工具链与初始化（TA-36）

| 目标 | 必装 | 环境变量 / rustup target |
|---|---|---|
| Android（三端宿主均可） | Android Studio → SDK Manager：Platform、Platform-Tools、Build-Tools、Command-line Tools、NDK (Side by side) | `JAVA_HOME`=Studio 自带 JBR；`ANDROID_HOME`；`NDK_HOME`；`aarch64-linux-android armv7-linux-androideabi i686-linux-android x86_64-linux-android` |
| iOS（仅 macOS 宿主） | 完整 Xcode（不是只装 CLT）+ `brew install cocoapods` | `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`；`aarch64-apple-ios aarch64-apple-ios-sim x86_64-apple-ios` |

```bash
# macOS 路径；Linux：/opt/android-studio/jbr 与 ~/Android/Sdk；Windows：%LOCALAPPDATA%\Android\Sdk
export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
export ANDROID_HOME="$HOME/Library/Android/sdk"
export NDK_HOME="$ANDROID_HOME/ndk/$(ls -1 "$ANDROID_HOME/ndk" | sort -V | tail -n1)"
cargo tauri android init        # 生成 src-tauri/gen/android（Gradle 工程）
cargo tauri ios init            # 生成 src-tauri/gen/apple（project.yml 驱动的 Xcode 工程）
```

1. `gen/android`、`gen/apple` **入库**：AndroidManifest、`build.gradle.kts` 签名段、Info.plist、图标是你的代码，CI 也靠它们。init 自带的 `.gitignore` 已排除 `build/`、`.gradle/`、`local.properties`、`xcuserdata/`；必须另外确认 `gen/android/keystore.properties` 与 `*.jks` 被忽略。
2. init 不覆盖已存在文件：升级 tauri-cli 后模板变化不会进你的 gen/。要同步时：备份手改 → 删 `gen/android` → 重新 init → `git diff` 合回；不手抄模板。
3. 宿主 `cargo check` 不编译 `target_os = "android"|"ios"` 分支；声明支持的移动端在 CI 至少 `cargo check --target aarch64-linux-android` / `aarch64-apple-ios`（XP-03），缺 NDK/Xcode 时把「未编译」列为缺口。

## identifier、入口与平台门控（TA-28、TA-30、TA-31）

1. `identifier` 是 `tauri.conf.json` **顶层键**（v1 的 `bundle.identifier` 是迁移债务）：反域名；只含字母数字和点；每段不以数字开头、不是 Java 关键字（`com.new.app` 在 Android 是非法包名）；禁 `-`（Android 侧会改成 `_`，与 iOS Bundle ID 不一致）；禁以 `.app` 结尾；默认值 `com.tauri.dev` 会被 CLI 警告。
2. 它同时是 Android 包名、iOS Bundle ID、桌面 `app_data_dir` 目录名：发布后改 = 用户数据「消失」+ 商店视为新应用；`android init` 之后改要删 gen/android 重建（包目录随之变）。移动端配置键：`bundle.android.minSdkVersion`（默认 24，Tauri 2 下限）、`bundle.iOS.developmentTeam`、`bundle.iOS.minimumSystemVersion`（Tauri 2.9.x 实际默认 "14.0"，官方 config 文档仍写 13.0 已过时；以生成工程的 `IPHONEOS_DEPLOYMENT_TARGET` 为准）。

```toml
# src-tauri/Cargo.toml —— 三种 crate-type 缺一不可：staticlib 给 iOS、cdylib 给 Android、rlib 给 main.rs 与测试
[lib]
name = "app_lib"
crate-type = ["staticlib", "cdylib", "rlib"]

[target.'cfg(not(any(target_os = "android", target_os = "ios")))'.dependencies]
tauri-plugin-global-shortcut = "2"   # 桌面专属：updater、autostart、single-instance、window-state、positioner、cli 同理
[target.'cfg(any(target_os = "android", target_os = "ios"))'.dependencies]
tauri-plugin-barcode-scanner = "2"   # 移动端专属：biometric、nfc、haptics 同理
```

```rust
// src-tauri/src/lib.rs；main.rs 只剩 fn main() { app_lib::run() }——写进 main.rs 的逻辑移动端根本不执行
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            #[cfg(desktop)]
            app.handle().plugin(tauri_plugin_global_shortcut::Builder::new().build())?;
            #[cfg(mobile)]
            app.handle().plugin(tauri_plugin_barcode_scanner::init())?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

```json
// src-tauri/capabilities/mobile.json —— 单独文件 + platforms；写进无 platforms 的 default.json 会让桌面构建报 permission not found
{
  "$schema": "../gen/schemas/mobile-schema.json",
  "identifier": "mobile",
  "platforms": ["android", "iOS"],
  "windows": ["main"],
  "permissions": ["barcode-scanner:allow-scan", "barcode-scanner:allow-cancel"]
}
```

3. `mobile`/`desktop` cfg 由 `tauri-build` 在 src-tauri 的 build.rs 注入，**别的 crate 里不存在**（shared crate 用 `target_os`）。`platforms` 取值 `linux`/`macOS`/`windows`/`android`/`iOS`，大小写照抄。
4. 前端调桌面专属插件前用 `@tauri-apps/plugin-os` 的 `platform()` 分流，否则移动端运行期 `plugin X not found`。移动端没有 sidecar（iOS 禁止 spawn 子进程），子进程方案要改成 command 内实现（XP-07）。
5. 最小权限（TA-12）在移动端多一层：iOS 用途字符串写 `src-tauri/Info.ios.plist`（CLI 合并进生成的 Info.plist；`NSCameraUsageDescription` 缺失 = 调用即崩 + 审核拒）；Android 权限由插件 Manifest 合并带入，自定义项写 `gen/android/app/src/main/AndroidManifest.xml`。
6. 官方插件覆盖不到的原生能力 = 自己写插件，别往 `gen/` 里手插 Kotlin/Swift（重建即丢）：`cargo tauri plugin new <name> --mobile`（单端用 `--android`/`--ios`，都不加就是纯桌面插件；已有插件补一端用 `cargo tauri plugin android init` / `ios init`；`--ios-framework` 默认 `spm`）。Kotlin 侧 `@TauriPlugin class XPlugin(private val activity: Activity): Plugin(activity)`，`@Command fun f(invoke: Invoke)` 内 `invoke.parseArgs(A::class.java)`（参数类标 `@InvokeArg`）→ `invoke.resolve(JSObject)` / `invoke.reject(msg)`；Swift 侧 `class XPlugin: Plugin` + `@objc public func f(_ invoke: Invoke) throws`，文件末尾 `@_cdecl("init_plugin_x") func initPlugin() -> Plugin`。命令权限照旧由插件 build.rs 的 `COMMANDS` 生成（[security.md](security.md)），Android 系统权限写插件自己的 `android/src/main/AndroidManifest.xml`，由 manifest merger 带进宿主应用。

```rust
// 插件 src/mobile.rs；桌面同名能力写 desktop.rs，两边给上层导出同一个 struct
#[cfg(target_os = "ios")]
tauri::ios_plugin_binding!(init_plugin_x);   // 声明 @_cdecl 那个 extern fn；缺了下面无从引用
pub fn init<R: Runtime, C: DeserializeOwned>(_app: &AppHandle<R>, api: PluginApi<R, C>) -> crate::Result<X<R>> {
    #[cfg(target_os = "android")]
    let handle = api.register_android_plugin("com.plugin.x", "XPlugin")?;  // 参数一 = Kotlin package、参数二 = 类名，拼成 class path，写错是运行期 ClassNotFound
    #[cfg(target_os = "ios")]
    let handle = api.register_ios_plugin(init_plugin_x)?;
    Ok(X(handle))
}
// 过界：handle.run_mobile_plugin::<Res>("f", payload)，异步用 run_mobile_plugin_async；payload: Serialize、Res: DeserializeOwned，原生侧 reject 回来是 ErrorResponse { code, message }
```

## 开发与真机调试（TA-35）

```bash
cargo tauri android dev            # 列出 adb devices / AVD 让你选；模拟器与 USB 设备由 CLI 映射 localhost，不必 --host；--open 进 Android Studio
cargo tauri ios dev "iPhone 16"    # 模拟器按名选；--open 进 Xcode（首次真机必须：选 Team）
cargo tauri ios dev --host         # iOS 真机 / Wi-Fi 设备：CLI 设置 TAURI_DEV_HOST=<本机局域网 IP> 并改写 devUrl
```

```ts
// vite.config.ts —— dev server 默认只听 127.0.0.1，真机连不上；host 跟着 TAURI_DEV_HOST 走，HMR 单独端口
const host = process.env.TAURI_DEV_HOST;
export default defineConfig({
  server: { port: 1420, strictPort: true, host: host || false,
            hmr: host ? { protocol: "ws", host, port: 1421 } : undefined },
});
```

1. 禁止把 `devUrl` 硬编码成局域网 IP 或把 `host: "0.0.0.0"` 入库：前者换网就坏，后者把 dev server 暴露给整个局域网。只在 `--host` 时开放，并放行防火墙 1420/1421。
2. 模拟器架构决定 target：Apple Silicon 上 Android AVD 是 arm64、iOS 模拟器是 `aarch64-apple-ios-sim`；Intel 机是 `x86_64-linux-android`/`x86_64-apple-ios`。`dev` 按设备自动选，`build` 默认全 ABI。
3. 日志：Rust 侧统一 `log` 宏 + `tauri-plugin-log`（Android 进 logcat，iOS 进 os_log / Xcode console；OBS-01），`println!` 只能在 `adb logcat -s RustStdoutStderr` 里找到。前端：Android debug 包自动开 WebView 调试 → Chrome `chrome://inspect/#devices`；iOS 在设备「设置 → Safari → 高级 → 网页检查器」打开后，桌面 Safari「开发」菜单选设备。真机白屏不要猜：debug 下把前端 `console.*` 转发进 Rust 日志——从 `@tauri-apps/plugin-log` 引 `trace/debug/info/warn/error`，对 log/debug/info/warn/error 逐个包一层 `const o = console[fn]; console[fn] = m => { o(m); logger(m) }`（`attachConsole` 方向相反，是把 Rust 日志送进 webview console，救不了白屏）。

## 签名与发布（TA-36）

```bash
keytool -genkey -v -keystore ~/upload-keystore.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload
cargo tauri android build --aab --target aarch64            # 上架 Play 用 AAB；不加 --apk/--aab 会两者都产且四个 ABI 全编
cargo tauri android build --apk --split-per-abi             # 侧载 / 测试分发
cargo tauri ios build --export-method app-store-connect     # 其它取值：release-testing（原 ad-hoc）、debugging（原 development）
```

1. `src-tauri/gen/android/keystore.properties`（已 ignore，三行：`password=`、`keyAlias=upload`、`storeFile=/abs/path/upload-keystore.jks`）；CI 从 secret 解码 `.jks` 到 `$RUNNER_TEMP` 后同样写这个文件。`build.gradle.kts`（入库）的 `signingConfigs.create("release")` 从 `rootProject.file("keystore.properties")` 读这三个键，**先 `exists()` 再 `load`**——同事与 CI 没有这个文件时 debug 构建不能炸；release buildType 再 `signingConfig = signingConfigs.getByName("release")`。
2. Play 上传密钥注册后不可换：`.jks` 进密码库。`versionCode` 默认由 `version` 推导（major×1000000 + minor×1000 + patch）；同版本重传要显式递增 `bundle.android.versionCode`。
3. iOS 本地用 Xcode 自动签名（`--open` 选 Team）；CI 设 `APPLE_DEVELOPMENT_TEAM` + `IOS_CERTIFICATE`（base64 p12）/`IOS_CERTIFICATE_PASSWORD`/`IOS_MOBILE_PROVISION`，或 App Store Connect API key（`APPLE_API_KEY`/`APPLE_API_ISSUER`/`APPLE_API_KEY_PATH`）。产物在 `gen/apple/build/arm64/<App>.ipa`。发布 profile 沿用 TA-01，移动端 `lto = true` 内存不够 → `"thin"`。

## 移动端 UI 差异（桌面 webview 看不出来，必须真机过）

1. 安全区：`<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">` + `padding-top: env(safe-area-inset-top)`；没有 `viewport-fit=cover` 时 `env()` 恒为 0。触控：`touch-action: manipulation` 去双击缩放延迟；hover 态只写在 `@media (hover: hover)`；`overscroll-behavior: none` 关橡皮筋（XP-09 的移动端版）。
2. Android 返回键：WebView 有历史就 `goBack`，没有就退出应用——SPA 路由必须走 History API，模态/抽屉也要 `pushState` 一层才能被返回键关闭。
3. 软键盘：iOS 弹起不改 `100vh`，用 `100dvh` + `visualViewport` 的 `resize` 事件滚到焦点；Android 在 Manifest `<activity android:windowSoftInputMode="adjustResize">`。
4. 沙盒：iOS 只有容器目录可写，桌面能跑的 `~/Documents` 字面路径在 iOS 是 `Operation not permitted`；一律 `app.path().app_data_dir()` / fs 插件 `$APPDATA`（XP-04）。

## WASM 前端：Trunk + Leptos/Yew 调 Tauri（TA-37）

```
Cargo.toml          # [workspace] members = ["crates/shared", "crates/app-ui", "src-tauri"]
crates/shared/      # 纯数据类型 + serde，publish = false（WS-03）；command 签名与 UI 共用，TA-13 由编译器完成
crates/app-ui/      # leptos/yew（features = ["csr"]，Tauri 没有 SSR），index.html + Trunk.toml，目标 wasm32-unknown-unknown
```

```json
// tauri.conf.json；真机调试要 trunk 监听 0.0.0.0 时放进 tauri.ios.conf.json / tauri.android.conf.json 覆盖，不进默认配置
{
  "build": {
    "beforeDevCommand": { "script": "trunk serve", "cwd": "../crates/app-ui" },
    "beforeBuildCommand": { "script": "trunk build --release", "cwd": "../crates/app-ui" },
    "devUrl": "http://localhost:1420",
    "frontendDist": "../crates/app-ui/dist"
  },
  "app": { "withGlobalTauri": true }
}
```

```rust
// crates/app-ui/src/tauri.rs —— 两个绑定够用；tauri-sys / tauri-wasm 也只是 window.__TAURI__ 的薄封装，同样要 withGlobalTauri（DEP-02）
use wasm_bindgen::prelude::*;
#[wasm_bindgen]
extern "C" {
    // ✗ 模板里的 `-> JsValue`：command 返回 Err 时 promise reject → wasm 直接 panic（unreachable）
    #[wasm_bindgen(catch, js_namespace = ["window", "__TAURI__", "core"])]
    pub async fn invoke(cmd: &str, args: JsValue) -> Result<JsValue, JsValue>;
    #[wasm_bindgen(js_namespace = ["window", "__TAURI__", "event"])]
    pub async fn listen(event: &str, handler: &Closure<dyn FnMut(JsValue)>) -> JsValue; // resolve 为 unlisten 函数
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]   // invoke 参数键默认 camelCase：user_id → userId；或在 command 上写 rename_all = "snake_case"
struct LoadArgs<'a> { user_id: &'a str }

pub async fn load(user_id: &str) -> Result<shared::Profile, String> {
    let ser = serde_wasm_bindgen::Serializer::json_compatible();   // 默认会把 HashMap 序列化成 JS Map，IPC 丢参数
    let args = serde::Serialize::serialize(&LoadArgs { user_id }, &ser).map_err(|e| e.to_string())?;
    let v = invoke("load_profile", args).await.map_err(|e| format!("{e:?}"))?;
    serde_wasm_bindgen::from_value(v).map_err(|e| e.to_string())
}
```

1. `withGlobalTauri: true` 是硬前提：wasm 拿不到 npm 的 `@tauri-apps/api`，只能走 `window.__TAURI__`；纯浏览器里 `trunk serve` 的页面没有它（`window.__TAURI__ is undefined`），IPC 只能在 `cargo tauri dev` 的 webview 里测——把依赖 Tauri 的代码收到一个模块，其余逻辑保持浏览器可跑可测。`Trunk.toml` 按官方模板加 `[serve] ws_protocol = "ws"`、`[watch] ignore = ["../../src-tauri"]`。
2. `listen` 的 `Closure` 必须活到 unlisten：`.forget()` 是泄漏，正确做法是存进组件状态，卸载时先调 unlisten 再 drop（提前 drop = `closure invoked recursively or after being dropped`）；回调收到的是 `{ event, id, payload }` 整个对象，反序列化取 `payload`。
3. shared 必须在 `wasm32-unknown-unknown` 可编译：禁 `tokio`/`std::fs`/`tauri`/`sqlx` 进依赖；`uuid` 开 `js`，`chrono` 开 `wasmbind`，`getrandom` 0.3.4+ 只要 `features = ["wasm_js"]`（0.3.0–0.3.3 还得在 `.cargo/config.toml` 写 `[target.wasm32-unknown-unknown] rustflags = ['--cfg', 'getrandom_backend="wasm_js"']`，0.2 是 `features = ["js"]`；缺了报 `The wasm32-unknown-unknown targets are not supported by default`）。CI 加 `cargo check -p shared --target wasm32-unknown-unknown`（XP-03）。禁止把 `build.target` 全局设成 wasm32（src-tauri 也会被编到 wasm）。
4. 计算放哪：数据已在 UI、纯 CPU、无系统访问 → WASM；文件/网络/密钥/多线程/大数据 → command（传输按 TA-06..08）。WASM 默认单线程，开线程要 SharedArrayBuffer + COOP/COEP，移动端 webview 不要指望；WKWebView 内存上限远低于进程，几百 MB 的 wasm 堆会让 webview 被系统杀掉。
5. 体积与首屏：`<link data-trunk rel="rust" data-wasm-opt="z" />` 让 Trunk 跑 wasm-opt；`[profile.release]` 是 workspace 级的，TA-01 的 `opt-level = "s"/"z"` 对 wasm 体积影响更大；`console_error_panic_hook` 只在 `debug_assertions` 下装。典型 Leptos/Yew 产物 1–3 MB，WKWebView 实例化要 100–500 ms → `visible: false` + ready 再 show（TA-10）是必需品。量 `ls -la dist/*.wasm` 前后对比（PERF-01）。Dioxus 自带 `dx` 与原生桌面渲染器，与 Tauri 二选一；已在 Dioxus web 的项目把 `dx build --platform web` 的输出目录设为 `frontendDist`，不再叠 Trunk。

## 常见错误

| 症状 | 原因 | 修法 |
|---|---|---|
| `NDK_HOME` not set / failed to find NDK | 没装 NDK (Side by side) 或变量未导出 | 装 + export；多版本时指向一个 |
| `unable to find library -lunwind` | NDK < r23（Rust ≥ 1.68 依赖 libunwind） | 升 NDK r25+，重设 `NDK_HOME` |
| `Could not resolve com.android.tools.build:gradle` / 卡在下载 gradle | 离线或代理 | `~/.gradle/gradle.properties` 设 proxy；wrapper `distributionUrl` 换镜像 |
| `minSdkVersion N cannot be smaller than version 24` | 手改了 minSdk 或插件要求更高 | `bundle.android.minSdkVersion` ≥ 24 |
| `tool 'xcodebuild' requires Xcode` | 只装了 Command Line Tools | 装 Xcode + `xcode-select -s` + `sudo xcodebuild -license accept` |
| 真机白屏 / `Could not connect to the server` | dev server 只听 127.0.0.1、不同网段、防火墙 | `--host` + vite 读 `TAURI_DEV_HOST` + 放行端口 |
| 桌面构建 `Permission xxx:default not found` | 移动端插件权限写进无 `platforms` 的 capability | 拆 `capabilities/mobile.json` |

## 验证

真机冒烟按平台各跑一遍：冷启动到首帧（TA-10）、安全区/横竖屏、软键盘遮挡、返回键、后台切回、断网。Android 取 `adb logcat` 片段、iOS 取 Xcode console 片段作证据；WASM 前端附 `dist/*.wasm` 尺寸表。CI 至少对声明的移动 target `cargo check`（XP-03）；发布流水线产出的 AAB/IPA 用 `bundletool` / TestFlight 装机验证，不拿桌面绿色代替。
