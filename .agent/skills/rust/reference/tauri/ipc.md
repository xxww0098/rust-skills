# tauri/ipc — 命令、事件、Channel、状态与类型化绑定

目的：代码里出现 `#[tauri::command]`、`invoke(`、`listen(`、`app.emit`、`State<'_, T>`、`tauri::ipc::Channel` 或 tauri-specta 时加载；覆盖前后端过界的定义、注册、错误契约、状态注入、事件语义与多窗口编排。通道选型与负载预算不重复 [../tauri.md](../tauri.md)（TA-06..08；本文展开 TA-19..24 与 TA-41），并发锁纪律见 ASYNC-02/03，这里只给落码形状。Tauri 2.11.x；`@tauri-apps/api/tauri`、`emit_all`、`window.emit` 定向语义都是 v1 遗留，见到即迁移。

## 命令定义与注册（TA-19）

1. `#[tauri::command]` 函数全部收进**一次** `generate_handler![…]`；`.invoke_handler()` 调第二次会覆盖第一次，前端报 `command X not found` 时先查这里。跨模块命令必须 `pub`，`generate_handler![cmds::bump]` 按路径引用；命令按函数名注册，不同模块同名即冲突。
2. 参数名：Rust `user_id` → 前端键 `userId`（宏自动转 camelCase）；要保留下划线加 `#[tauri::command(rename_all = "snake_case")]`。**结构体字段不受此转换影响**，走 serde：payload 结构体加 `#[serde(rename_all = "camelCase")]`，否则前端传 `{ userId }` 反序列化报 `missing field user_id`。
3. JSON 命令的 `invoke` 第二参数是对象，键对应参数名，`Option<T>` 参数可省略或传 `null`；整体传 `ArrayBuffer`/`Uint8Array` 则走 Raw 通道（见下文 `upload`）。
4. `async fn` 命令不能借用参数：`&str`/`&[u8]`/`Request<'_>` 只能进同步命令；async 收 `String`/`Vec<u8>`。**线程模型（TA-41）**：tauri-macros 对普通 `fn` 是在 IPC 消息路径上**内联**调用——wry 把该路径派到事件循环（主线程）；`async fn` / `#[tauri::command(async)]` 走 `async_runtime::spawn`，在共享 tokio runtime 上跑。因此：
   - 阻塞原生对话框（`rfd::FileDialog`、macOS 要求主线程的 NSOpenPanel）必须写**同步** command；放进 async command = 非主线程弹窗，macOS 卡死或静默失败——async 路径改 `rfd::AsyncFileDialog`。
   - 重活（SQLite、渲染、哈希）不要堵同步 command（冻窗口）；挪到 `spawn_blocking` / 自管线程池，或把命令本身改 async。
   - 插件 `dialog().blocking_pick_file()` 是另一套：在 `setup`/主线程直接调会与事件循环互锁，必须放 **async command**（见 [plugins.md](plugins.md)）。rfd 同步 command ≠ plugin-dialog blocking。
   默认仍优先 `async fn`（TA-09）；只有「必须主线程」的 API 才留同步。
5. 返回值 `T: Serialize`；`Result<T, E>` 要求 `E: Serialize`，否则编译错误在宏展开处、信息难读。`Vec<u8>` 会被序列化成 JSON 数字数组，二进制走 `tauri::ipc::Response`（TA-07）。
6. 注入参数不占前端键：`State<'_, T>`、`AppHandle`、`WebviewWindow`（调用方窗口，日常用它）、`Window`（裸 OS 窗口）、`Webview`、`ipc::Request<'_>`。`ipc::Channel<T>` **占键**：前端 `new Channel<T>()` 当同名 camelCase 参数传入（见下文 `onProgress`），漏传即 `missing required key`。

## 错误类型：前端拿到的是 `unknown`（TA-20）

```rust
// ✗ io::Error 不 Serialize；到处 map_err(|e| e.to_string()) 则丢掉错误种类
#[tauri::command]
async fn load(p: String) -> Result<String, std::io::Error> { tokio::fs::read_to_string(p).await }

// ✓ 具名 enum + thiserror（ERR-01/08），自定义 Serialize 决定过界形状
#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error(transparent)] Io(#[from] std::io::Error),
    #[error(transparent)] Tauri(#[from] tauri::Error),
    #[error("state lock poisoned")] Poisoned,
    #[error("expected raw body")] ExpectedRaw,
}
impl<T> From<std::sync::PoisonError<T>> for Error {
    fn from(_: std::sync::PoisonError<T>) -> Self { Self::Poisoned }
}
impl serde::Serialize for Error {
    fn serialize<S: serde::Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        s.serialize_str(&self.to_string())      // 前端需要分支处理时改为 tagged 结构体 { kind, message }
    }
}
```

- 前端 `catch (err: unknown)`：形状完全由 `E` 的 `Serialize` 决定，`String` → string，tagged enum → 对象；禁止 `err.message`（不是 `Error` 实例）。
- 把 `PoisonError` 收进错误类型后，命令里就能 `state.0.lock()?`，不再 `.lock().unwrap()`（ERR-03）。

## 状态注入（TA-21）

1. `Builder::manage(T)` / `app.manage(T)` 按**类型**唯一：同类型 manage 两次返回 `false` 并静默丢弃第二个，两份配置要用不同 newtype。`T: Send + Sync + 'static`，自身不必 `Clone`。
2. `app.state::<T>()` 未 manage 即 panic；插件/可选状态用 `app.try_state::<T>()`。manage 放 `Builder` 链或 `setup` 里，任何命令执行前完成。
3. 锁选型（D-3）：临界区短且不跨 `.await` → `std::sync::Mutex`；必须跨 `.await`（持连接做查询）→ 先缩临界区，真缩不掉再 `tokio::sync::Mutex`（ASYNC-02、TA-09）。只读配置不上锁，`RwLock` 只在读多写少并实测后用。
4. `State<'_, T>` 借自 app，不能 move 进 `spawn`：task 里用 `app.clone()` 再 `app.state::<T>()`，或把 `T` 内部的 `Arc` clone 出来。
5. 命令内长任务：`tauri::async_runtime::spawn`（async）/ `spawn_blocking`（CPU、`std::fs`，ASYNC-03）；`JoinHandle` 必须被 `await` 或登记（ASYNC-04），进度走 Channel 回传而不是命令阻塞到结束。

## 完整示例：命令 + 状态 + 事件

```rust
use std::sync::Mutex;
use tauri::{AppHandle, Emitter, State, WebviewWindow};

#[derive(Default)]
struct Counter(Mutex<u32>);

#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct Tick { value: u32, source_label: String }

#[tauri::command]
async fn bump(by: u32, state: State<'_, Counter>, app: AppHandle, win: WebviewWindow) -> Result<u32, Error> {
    let value = { let mut g = state.0.lock()?; *g += by; *g };    // guard 在块内释放，不跨 await
    app.emit("counter:tick", Tick { value, source_label: win.label().to_owned() })?;
    Ok(value)
}

pub fn run() {
    tauri::Builder::default()
        .manage(Counter::default())
        .invoke_handler(tauri::generate_handler![bump])            // 全部命令，只此一处
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

```ts
import { invoke } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';

type Tick = { value: number; sourceLabel: string };

const unlisten: UnlistenFn = await listen<Tick>('counter:tick', (e) => render(e.payload.value));
try {
  const v = await invoke<number>('bump', { by: 2 });               // 参数键 camelCase
  console.log(v);
} catch (err: unknown) {
  showError(typeof err === 'string' ? err : JSON.stringify(err)); // 形状由 Rust 端 Serialize 决定
}
window.addEventListener('beforeunload', () => unlisten());
```

## 事件：广播语义与生命周期（TA-22）

1. Rust 端导入 `tauri::Emitter`/`tauri::Listener` trait 才有 `emit`/`listen`。`emit(name, payload)` 在 **任何** 句柄上（`AppHandle`、`WebviewWindow` 都一样）都是广播到全部窗口与 Rust 监听器；定向用 `emit_to("settings", name, payload)`，按规则筛选用 `emit_filter(name, payload, |t| matches!(t, EventTarget::WebviewWindow { label } if label.starts_with("doc-")))`。payload 要 `Serialize + Clone`。
2. 事件名只允许字母数字与 `-` `/` `:` `_`；`export.progress` 在 Rust 端 `listen` 直接 panic、`emit` 返回 `Err`（非法事件名）。统一 `域:动作` 命名并抽成常量，两端共用一份字符串。
3. 事件无缓冲：监听器注册前发出的事件丢失。前端先 `await listen(...)` 再 `invoke` 触发工作；启动期状态用 command 拉取，不靠 `setup` 里 `emit`。
4. 前端 `listen` 默认 target 是 Any，会收到 `emit_to` 发给**别的**窗口的事件；窗口专属监听用 `getCurrentWebviewWindow().listen(...)`；一次性用 `once`。
5. Rust 端 `app.listen(name, |ev| …)` 收到的 `ev.payload()` 是 JSON 字符串，`serde_json::from_str::<T>` 后再用；回调在事件线程执行，禁阻塞。`listen` 返回 `EventId`，不再需要时 `app.unlisten(id)`。
6. 前端 → Rust 一律 command（有返回、有类型、可被 ACL 约束）；event 只做 Rust → 前端广播与窗口间通知（`emitTo('main', …)`）。高频进度不用 event（TA-06/TA-11），单条 payload 守 TA-08 预算。
7. `listen` 返回的 unlisten 必须在组件卸载时调用；React 严格模式开发期会挂载两次，不清理就双倍回调：

```ts
useEffect(() => {
  let unlisten: UnlistenFn | undefined;
  let cancelled = false;
  listen<Tick>('counter:tick', (e) => setValue(e.payload.value)).then((u) => {
    if (cancelled) u(); else unlisten = u;          // 清理先于 Promise 完成时也要解除
  });
  return () => { cancelled = true; unlisten?.(); };
}, []);
```

## 流式与二进制：Channel、Response、Raw 上传

```rust
// 下行流式：有序、专用（TA-06）；二进制流用 Channel<tauri::ipc::InvokeResponseBody> 发 Raw(bytes)，以 docs.rs 为准
#[tauri::command]
async fn export(on_progress: tauri::ipc::Channel<u32>) -> Result<(), Error> {
    for pct in [10, 50, 100] { on_progress.send(pct)?; }
    Ok(())
}

// 上行大块：前端把 Uint8Array 作为整个 args 传入 → 走 InvokeBody::Raw，不经 JSON；借用类型 → 同步命令
#[tauri::command]
fn upload(request: tauri::ipc::Request<'_>) -> Result<usize, Error> {
    let tauri::ipc::InvokeBody::Raw(bytes) = request.body() else { return Err(Error::ExpectedRaw) };
    let name = request.headers().get("x-file-name").and_then(|v| v.to_str().ok()).unwrap_or("upload.bin");
    Ok(bytes.len() + name.len())
}
```

```ts
import { invoke, Channel } from '@tauri-apps/api/core';
const ch = new Channel<number>();
ch.onmessage = (pct) => setProgress(pct);
await invoke('export', { onProgress: ch });
await invoke('upload', new Uint8Array(buf), { headers: { 'x-file-name': 'a.bin' } }); // 嵌在对象里则退化为 JSON 数组
const video = await invoke<ArrayBuffer>('read_video', { p: path });                  // Rust 返回 ipc::Response（TA-07）
```

自定义 URI scheme：媒体/大文件直接喂 webview，完全不过 IPC（TA-07）。

```rust
use tauri::http;                                    // tauri 重导出 http crate
tauri::Builder::default().register_asynchronous_uri_scheme_protocol("stream", |_ctx, req, responder| {
    let range = req.headers().get(http::header::RANGE).cloned();          // 拖进度条必发 Range
    std::thread::spawn(move || responder.respond(serve_range(req.uri().path(), range)));  // 自行回 206 + Content-Range/Accept-Ranges
});
```

- 同步版 `register_uri_scheme_protocol("stream", |_ctx, req| -> http::Response<T>)`；闭包首参 v2 是 `UriSchemeContext`（v1 是 `app`），第二参 `http::Request<Vec<u8>>`。
- 前端 URL 分平台：macOS/iOS/Linux `stream://localhost/<path>`，Windows/Android `http://stream.localhost/<path>`（`WebviewBuilder::use_https_scheme(true)` 换 https）。CSP 的 `media-src`/`img-src` 两套 origin 都要写，只写一套 = 另一端静默失败；URL 别手拼，用 `convertFileSrc(path, 'stream')` 按平台生成。
- 只回 200 全量的表现是"能播不能拖、大文件首帧极慢"。asset protocol 已内建 Range（206 + `Accept-Ranges: bytes` + multipart/byteranges），开 `security.assetProtocol.enable` 配好 `scope` 后 `convertFileSrc(path)` 就够，别自己写；注册同名 `"asset"` scheme 会顶掉内建实现。

## 类型化绑定：tauri-specta 2.x（TA-13）

1. 依赖：`specta`（2.0 线）、`specta-typescript`、`tauri-specta = { features = ["derive", "typescript"] }`，具体 rc/stable 号以 crates.io 为准。每个命令加 `#[specta::specta]`（放在 `#[tauri::command]` 之后），参数/返回/错误类型全部 `derive(specta::Type)`。
2. `u64`/`i64` 字段默认导出失败：`Typescript::default().bigint(BigIntExportBehavior::Number)`，或把 wire 类型改成 `u32`/`String`（API-08）。
3. 事件用 `#[derive(tauri_specta::Event)]`，Rust 端 `Tick { … }.emit(&app)?`，前端 `events.tick.listen(...)`，事件名由类型生成，两端不再手写字符串。

```rust
let builder = tauri_specta::Builder::<tauri::Wry>::new()
    .commands(tauri_specta::collect_commands![bump, export])
    .events(tauri_specta::collect_events![Tick]);
#[cfg(debug_assertions)]                                   // 只在 debug 构建导出，CI 用 git diff 校验 bindings.ts 未漂移
builder.export(specta_typescript::Typescript::default(), "../src/bindings.ts").expect("export bindings");
tauri::Builder::default()
    .invoke_handler(builder.invoke_handler())
    .setup(move |app| { builder.mount_events(app); Ok(()) });
```

前端 `const r = await commands.bump(2);` 返回 `{ status: "ok", data } | { status: "error", error }`，按 `status` 分支而不是 try/catch；仍写裸 `invoke("bump", {...})` 的调用点视为 TA-13 违例。

## 权限与多窗口（TA-23、TA-24）

1. 自定义命令默认对所有窗口放行，不需要任何 capability；只有在 `build.rs` 用 `tauri_build::AppManifest::new().commands(&["bump"])` 声明后才进入 ACL，此时 capability 要写 `allow-bump`（以 docs.rs tauri-build 为准）。插件命令（含 `core:*`）一律走 ACL：前端 `listen`/`emit` 本身是 `plugin:event|*` 调用，需要 `core:event:default`（含于 `core:default`，TA-12）。
2. 新窗口的 label 必须命中某个 capability 的 `windows`（支持 glob `"doc-*"`），否则它能调自定义命令却不能 `listen`，症状是"事件静默收不到"。label 在 `tauri.conf.json`、capabilities、`get_webview_window("main")`、`emit_to` 四处出现，抽成一处常量。
3. `app.get_webview_window(label)` 返回 `Option`（需 `use tauri::Manager`），窗口可能已被用户关掉，禁 unwrap。Rust 建窗：`WebviewWindowBuilder::new(&app, "settings", WebviewUrl::App("settings.html".into())).build()?`；前端 `new WebviewWindow(...)` 需要 `core:webview:allow-create-webview-window`，并监听 `tauri://created`/`tauri://error`。
4. 关闭前保存：前端 `getCurrentWindow().onCloseRequested(async (e) => { if (dirty) { e.preventDefault(); await invoke('save'); await getCurrentWindow().destroy(); } })`——保存后必须 `destroy()`，再调 `close()` 会重新触发事件形成循环。Rust 端等价于 `on_window_event` 里匹配 `WindowEvent::CloseRequested { api, .. }` → `api.prevent_close()` 后异步保存再 `window.destroy()`；最小化到托盘同样在这里 `window.hide()`。窗口行为逐平台冒烟（XP-09）。

## 验证

- 命令单测：`tauri::test::mock_builder` + `get_ipc_response` 只锁序列化契约，完整夹具（含 `InvokeRequest` 全字段）见 [develop.md](develop.md)（TA-38）；测 `bump` 时 builder 上补 `.manage(Counter::default())`，body 喂 `InvokeBody::Json(json!({ "by": 2 }))`。断言值来自规格而非复述实现（TEST-08）。
- 错误契约：对每个 `Error` 变体写一条 `serde_json::to_string(&err)` 快照，前端按同一份固定字符串/`kind` 分支。
- 事件与窗口：真机冒烟覆盖"先 listen 后 invoke"、多窗口 `emit_to` 只到目标、React 严格模式下回调次数为 1、关闭请求保存后进程退出。
- 大块/流式：`Response`、`Raw` 上传与 Channel 按 TA-05/TA-08 做前后计时对比，不凭感觉换通道。
