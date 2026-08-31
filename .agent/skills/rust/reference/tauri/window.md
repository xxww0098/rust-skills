# tauri/window — tauri.conf.json、窗口、菜单、托盘与启动体验

目的：diff 里出现 `tauri.conf.json`、`WebviewWindowBuilder`、`decorations: false`、`TrayIconBuilder`、`MenuBuilder`、`tauri-plugin-window-state|positioner|single-instance`，或用户提到白屏/启动页/托盘/多开/关窗隐形时加载。体积、IPC、命令纪律归 owner [../tauri.md](../tauri.md)（TA-01..TA-47），三端 webview/文件系统差异归 [../xplat.md](../xplat.md)（XP-01/04/09）；本文只写配置、窗口与系统集成面。


## tauri.conf.json（v2 结构；TA-28、TA-33）

1. 顶层只有 `$schema`/`productName`/`version`/`identifier`/`build`/`app`/`bundle`/`plugins`；v1 的 `tauri.*`、`tauri.allowlist`、`package.*` 是迁移债务。窗口数组在 `app.windows[]`，不在 `tauri.windows`。
2. `identifier` 反域名（`com.acme.notes`）：决定 bundle ID 与 webview 数据目录，发布后改名等于用户数据丢失。只用小写字母数字与 `.`；禁 `-`（Android 包名非法）、禁 `.app` 结尾（与 macOS bundle 扩展名冲突）、禁模板值 `com.tauri.dev`。
3. `build`：`beforeDevCommand`+`devUrl` 与 `beforeBuildCommand`+`frontendDist` 成对；`removeUnusedCommands: true`（TA-02）。
4. `app.security.csp` 必须非 null；`asset:`/`http://asset.localhost` 只在真用了 asset protocol 时加（TA-07）。`app.withGlobalTauri` 只给无打包器的页面开——开了就是 `window.__TAURI__` 全量暴露。
5. `bundle.icon` 列全 png 多尺寸 + `.icns` + `.ico`：`app.default_window_icon()` 与托盘默认图取自这里，缺 `.ico` Windows 构建直接失败。
6. 平台覆盖：`tauri.macos|windows|linux|android|ios.conf.json` 与 `--config <文件|内联 JSON>` 按 JSON Merge Patch（RFC 7396）叠加——对象深合并、**数组整体替换**：平台文件里写 `app.windows` 是换掉整个窗口数组，不是改某一项。
7. 合并结果由 CLI 经 `TAURI_CONFIG` 环境变量喂给 `tauri-build`/`generate_context!`：直接 `cargo run` 看不到 `--config` 覆盖，必须经 `tauri dev`/`tauri build`；禁止手设 `TAURI_CONFIG`（内部通道，会无声覆盖文件配置）。

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "Acme Notes", "version": "1.4.0", "identifier": "com.acme.notes",
  "build": { "beforeDevCommand": "pnpm dev", "devUrl": "http://localhost:5173",
             "beforeBuildCommand": "pnpm build", "frontendDist": "../dist", "removeUnusedCommands": true },
  "app": {
    "withGlobalTauri": false,
    "security": { "csp": "default-src 'self'; connect-src ipc: http://ipc.localhost; img-src 'self' data:; style-src 'self' 'unsafe-inline'" },
    "windows": [{ "label": "main", "title": "Acme Notes", "width": 1100, "height": 720, "minWidth": 800, "center": true, "visible": false }]
  },
  "bundle": { "active": true, "targets": "all", "icon": ["icons/32x32.png", "icons/128x128@2x.png", "icons/icon.icns", "icons/icon.ico"] },
  "plugins": {}
}
```

## 窗口：配置式与运行时（TA-23、TA-24、TA-42）

1. 静态主窗写配置（可被平台文件覆盖、被 window-state 恢复）；按需窗口用 `WebviewWindowBuilder::new(app, label, WebviewUrl::App(path))` 或前端 `new WebviewWindow(label, opts)`。同一 label 同时只能存在一个，重复创建返回 Err——先 `get_webview_window(label)` 聚焦，再创建。
2. label 写成常量共用：capabilities 的 `windows: ["main"]` 按 label 匹配，新窗口没进任何 capability 时自定义命令仍能调，但 `core:*`/插件命令与 `listen` 全被拒，报错只在 devtools 里。
3. `visible: false` + 首帧就绪后 `show()`（TA-10）：前端 `getCurrentWindow().show()`（需 `core:window:allow-show`）或后端初始化完成后 `show()`；禁 `setTimeout(show, 500)`。
4. 关闭拦截：`WindowEvent::CloseRequested { api, .. }` → `api.prevent_close()`；JS `onCloseRequested(e => e.preventDefault())`。托盘常驻应用把关闭变隐藏。
5. 最后一个窗口销毁默认退出进程；托盘常驻必须 `.build(ctx)?.run(|_, e| if let RunEvent::ExitRequested { code: None, api, .. } = e { api.prevent_exit() })`——`code: Some` 是 `app.exit()` 主动退出，放行。
6. **macOS 关窗 ≠ 退出（TA-42）**：即使用户没做托盘，关主窗默认只销毁窗口、进程继续跑；没有 `RunEvent::Reopen` 时点 Dock 图标不会重建窗口——操作员困在隐形应用里。约定：`#[cfg(target_os = "macos")]` 下 `CloseRequested` → `window.hide()` + `api.prevent_close()`（保留窗口对象），`RunEvent::Reopen { .. }` → `show()` + `set_focus()`。Windows/Linux 关主窗 = 退出，保持默认，不要把 mac 的 hide 抄过去。macOS 专用 import 同样 cfg 住，否则 Windows 构建 unused import。
7. 其余 `WindowEvent`：`Focused`/`Resized`/`Moved`/`ScaleFactorChanged`/`ThemeChanged`/`Destroyed`；尺寸用 `LogicalSize` 不手乘 DPI；`Destroyed` 后句柄所有调用返回 Err。
8. 文件拖放默认被 Tauri 接管（`dragDropEnabled: true`，v1 叫 `fileDropEnabled`），webview 里的 HTML5 `dragover`/`drop` 因此永不触发——Windows 最明显且无任何报错。两条路互斥，选一条并在配置旁注释：**要前端拖放**就在 `app.windows[]` 写 `"dragDropEnabled": false`（或 `WebviewWindowBuilder::disable_drag_drop_handler()`）；**要系统路径**就保持默认，接 `WindowEvent::DragDrop(DragDropEvent::{Enter,Over,Drop,Leave})`（`Drop` 带 `paths`/`position`）或 JS `getCurrentWebview().onDragDropEvent(e => e.payload.type === 'drop' && e.payload.paths)`。拖进来的路径同样是不可信输入，按 TA-18 canonicalize 后再用。

```rust
use tauri::{DragDropEvent, Manager, WebviewUrl, WebviewWindowBuilder, WindowEvent};

fn open_settings(app: &tauri::AppHandle) -> tauri::Result<()> {
    if let Some(w) = app.get_webview_window("settings") {            // 已存在：聚焦，不重复创建
        return w.set_focus();
    }
    let w = WebviewWindowBuilder::new(app, "settings", WebviewUrl::App("settings.html".into()))
        .title("设置").inner_size(640.0, 480.0).visible(false)      // TA-10：前端 ready 后 show
        .build()?;
    let hide_target = w.clone();
    w.on_window_event(move |e| {
        if let WindowEvent::CloseRequested { api, .. } = e {
            api.prevent_close();                                     // 关闭 = 隐藏
            let _ = hide_target.hide();                              // 窗口已在销毁中时失败可忽略
        }
        if let WindowEvent::DragDrop(DragDropEvent::Drop { paths, .. }) = e {
            let _ = paths;                       // 不可信输入：TA-18 canonicalize + 根目录比对后再用
        }
    });
    Ok(())
}
```

## 自定义标题栏、透明与特效（TA-23）

1. 两条路线二选一：**全平台无边框** `decorations: false` + 自绘三键；或 **macOS 保留红绿灯** `decorations: true` + `titleBarStyle: "Overlay"` + `hiddenTitle: true`（仅 macOS 生效，直接写在 `tauri.conf.json` 的窗口项里，其他平台忽略；放进 `tauri.macos.conf.json` 会整体替换 `app.windows`）。`decorations: false` 会连红绿灯一起去掉，Overlay 随之失效。
2. 拖拽区只对带 `data-tauri-drag-region` 的元素本身生效，不继承到子元素；按钮禁带该属性（点击变拖拽、双击触发最大化）。固定在顶栏的 portal（toast/popover）必须落在标题栏高度之下，并标 `data-tauri-drag-region="false"`：叠进 Overlay 拖拽带时关闭点击会被当成拖窗口。
3. **跨会话偏好禁 renderer `localStorage`（TA-47）**：macOS WKWebView 把它放进 `~/Library/WebKit/{identifier}/WebsiteData/`，该容器会被系统整体删除重建（未重启机器也会发生）。必须记住的设置走宿主 command，落 `app.path().app_data_dir()` 下的 JSON；`localStorage` 只配当会话缓存。Windows/Linux 的 Chromium/WebKitGTK 存储路径不同，更不能靠「Mac 上 localStorage 还在」推断三端耐久。
4. JS 三键需要 ACL：`core:default` 只含只读 getter，capability 里必须显式加 `core:window:allow-start-dragging`/`allow-minimize`/`allow-toggle-maximize`/`allow-close`（`allow-show` 给 ready→show）。

4. Windows：`decorations: false` 后 `shadow: true`（默认）仍给边缘阴影与可拖拽边框；再加 `transparent: true` 阴影即消失，圆角/阴影要自己画。`skipTaskbar` 只 Windows/Linux 有效。
5. macOS `transparent: true` 需 `app.macOSPrivateApi: true` + Cargo feature `macos-private-api`（App Store 审核风险自担）；`windowEffects` vibrancy 只 macOS，Windows 用 `mica`/`acrylic`（Win11），Linux 无特效且透明依赖合成器——逐平台验收（XP-09）。

```html
<header data-tauri-drag-region class="titlebar">   <!-- 子元素要拖拽需各自再标；按钮不标 -->
  <button id="min">–</button><button id="max">□</button><button id="close">×</button>
</header>
```
```ts
import { getCurrentWindow } from '@tauri-apps/api/window';   // v2；v1 的 appWindow 已移除
const w = getCurrentWindow();
document.getElementById('min')!.onclick = () => w.minimize();
document.getElementById('max')!.onclick = () => w.toggleMaximize();
document.getElementById('close')!.onclick = () => w.close();
```

## 菜单（TA-25）

1. `MenuBuilder`/`SubmenuBuilder`/`MenuItemBuilder::with_id`/`CheckMenuItemBuilder`/`PredefinedMenuItem`；自定义项必须显式字符串 id，事件按 `event.id().as_ref()` 分发，禁按显示文本匹配（本地化一改全断）。
2. `app.set_menu` 是应用级：macOS 进全局菜单栏，Windows/Linux 成为每个窗口的菜单条（新窗口自动继承，`WebviewWindowBuilder::menu` 可单独覆盖）。
3. macOS 第一个 submenu 就是应用菜单：标题被系统替换成 app 名，`about`/`services`/`hide`/`hide_others`/`show_all`/`quit` 放这里；Windows/Linux 没有应用菜单，Quit 放「文件」末尾、About 放「帮助」——`#[cfg(target_os = "macos")]` 分两套，别让 Windows 出现一个叫 app 名的空菜单。
4. 自建菜单必须补 `undo/redo/cut/copy/paste/select_all`，否则 macOS 上 webview 里 Cmd+C/V 失灵；没特殊需求直接 `Menu::default(app)`。
5. `accelerator("CmdOrCtrl+N")` 只在菜单所属窗口聚焦时触发，全局热键走 `tauri-plugin-global-shortcut`；右键菜单 `window.popup_menu(&menu)`/`popup_menu_at`，菜单对象建一次复用，不在每次右键里 build。

```rust
use tauri::{menu::{MenuBuilder, MenuItemBuilder, SubmenuBuilder}, Emitter};

// setup 内
let new_note = MenuItemBuilder::with_id("new", "新建").accelerator("CmdOrCtrl+N").build(app)?;
let edit = SubmenuBuilder::new(app, "编辑").undo().redo().separator().cut().copy().paste().select_all().build()?;
let file = SubmenuBuilder::new(app, "文件").item(&new_note).close_window();
#[cfg(target_os = "macos")]
let menu = {                                                            // 首个 submenu = 应用菜单，Quit 在这里
    let app_menu = SubmenuBuilder::new(app, "Acme Notes").about(None).separator().services().separator()
        .hide().hide_others().show_all().separator().quit().build()?;
    MenuBuilder::new(app).items(&[&app_menu, &file.build()?, &edit]).build()?
};
#[cfg(not(target_os = "macos"))]
let menu = MenuBuilder::new(app).items(&[&file.separator().quit().build()?, &edit]).build()?; // Quit 在文件末尾
app.set_menu(menu)?;
app.on_menu_event(|app, e| match e.id().as_ref() {
    "new" => { let _ = app.emit("menu:new", ()); }                      // 无监听者时失败可忽略
    _ => {}
});
```

## 托盘（TA-25）

1. Cargo feature `tauri = { features = ["tray-icon"] }`（不用就关，TA-03）；Rust 侧建托盘不需要 ACL，JS `TrayIcon.new` 才要 `core:tray:default`。配置式 `app.trayIcon` 与 `TrayIconBuilder` 二选一：配置式自动建 id=`main` 的托盘，用 `app.tray_by_id("main")` 挂菜单/事件，两边都写就是两个图标。
2. `TrayIconBuilder::with_id` 固定 id，后续 `tray_by_id` 换图标/标题（未读数）；macOS 单独准备黑色透明 22px 模板图 + `icon_as_template(true)` 随深浅色，彩色图标在菜单栏是事故。
3. 左键语义：macOS `show_menu_on_left_click` 默认 true——左键弹菜单且**不发 Click 事件**；要「左键开窗、右键菜单」必须显式 false。Linux appindicator 没有任何点击事件，「左键开窗」只能做成菜单项。
4. `on_tray_icon_event` 只响应 `Click { button: Left, button_state: Up, .. }`：`Down`/`Up` 各来一次，不过滤就双触发；`DoubleClick` 与两次 `Click` 并存，别同时绑两种。
5. Linux 运行时依赖 `libayatana-appindicator3`（deb/rpm 依赖与 AppImage 都要带），缺库时托盘静默不出现；`tooltip` Linux 不显示。
6. macOS 托盘常驻应用默认仍占一个 Dock 图标与应用菜单，`setup` 里 `#[cfg(target_os = "macos")] app.set_activation_policy(tauri::ActivationPolicy::Accessory);` 才隐藏（等价 Info.plist 的 `LSUIElement`；该方法只在 macOS 编译出来，漏 cfg 直接编译不过——`App` 上无返回值、`AppHandle` 上返回 `Result`）。代价是全局菜单栏一并消失：`app.set_menu` 的菜单不再显示，靠菜单快捷键的功能要重新验收，需要时切回 `ActivationPolicy::Regular`。应用仍能被激活——`set_focus()` 内部走 `activateIgnoringOtherApps`，但窗口不可见/最小化时它是空操作，顺序必须 `show()` → `unminimize()` → `set_focus()`（下面的 `focus_main`）。只想运行时开关 Dock 图标用 `set_dock_visibility(bool)`（tauri 2.11 有，更早版本以 docs.rs 为准）：它的 hide 在 show 后 1 秒内被静默忽略（绕开 macOS 残留多个 Dock 图标的 bug），别拿它做快速来回切换。TA-24 的 `prevent_exit` 只保住进程，不管 Dock。

| 行为 | macOS | Windows | Linux |
|---|---|---|---|
| 菜单位置 | 全局菜单栏，首个 submenu 为应用菜单 | 每窗口菜单条 | 每窗口菜单条（GTK） |
| Quit/About | 应用菜单 `quit()`/`about()`；`services/hide/show_all` 仅此处 | 文件末尾 `quit()`，帮助里自定义 About | 同 Windows |
| `accelerator` | 菜单栏可见即触发 | 需窗口聚焦 | 需窗口聚焦 |
| 托盘左键 | 默认弹菜单，关掉才有 Click | Click 事件，右键弹菜单 | 无点击事件，只有菜单 |
| 托盘图标 | 模板图 `iconAsTemplate` | `.ico` 多尺寸 | 需 appindicator 库；`iconAsTemplate` 忽略；无 `DoubleClick` |

```rust
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{menu::{MenuBuilder, MenuItemBuilder}, Manager};

fn focus_main(app: &tauri::AppHandle) {
    let Some(w) = app.get_webview_window("main") else { return };
    let _ = w.show().and_then(|_| w.unminimize()).and_then(|_| w.set_focus()); // 销毁中的窗口失败可忽略
}

// setup 内
let quit = MenuItemBuilder::with_id("quit", "退出").build(app)?;
let menu = MenuBuilder::new(app).item(&quit).build()?;
TrayIconBuilder::with_id("main")
    .icon(app.default_window_icon().expect("invariant: bundle.icon 非空").clone())
    .icon_as_template(true)
    .menu(&menu)
    .show_menu_on_left_click(false)                                    // 左键开窗、右键菜单；Linux 忽略
    .on_menu_event(|app, e| if e.id().as_ref() == "quit" { app.exit(0) })
    .on_tray_icon_event(|tray, event| {
        tauri_plugin_positioner::on_tray_event(tray.app_handle(), &event); // 只在用 positioner 的 Tray* 位置时接
        if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
            focus_main(tray.app_handle());
        }
    })
    .build(app)?;
```

## window-state 与 positioner（TA-26）

1. `tauri-plugin-window-state`：`Builder::new().with_state_flags(StateFlags::all() & !StateFlags::VISIBLE).with_denylist(&["splashscreen"]).build()`。带 `VISIBLE` 会在恢复时按上次状态直接显示窗口，打穿 `visible: false` + ready→show（TA-10）。
2. 恢复发生在窗口创建时、先于首帧，配置里的 `width/height/center` 只是首次运行默认值；某窗口不想恢复用 `skip_initial_state(label)`；正常退出自动保存，只有自己接管退出路径才手动 `app.save_window_state(StateFlags::all())`。
3. 多显示器：外接屏拔掉后保存坐标落在屏外，插件按显示器边界回退（细节以 docs.rs 为准）；不同 DPI 的屏之间实测 `ScaleFactorChanged`。
4. `tauri-plugin-positioner`：`window.move_window(Position::TrayCenter)`（`WindowExt`）。`Tray*` 系列位置依赖托盘事件坐标——插件开 feature `tray-icon` 并在 `on_tray_icon_event` 里先调 `on_tray_event`，否则 `TrayCenter` 无数据；`Center`/`TopRight` 等不需要接线。JS `moveWindow(Position.TrayCenter)` 需 `positioner:default`。

## splashscreen（TA-26）

1. `visible: false` + ready→show 已覆盖「遮白屏」（TA-10）；只有秒级真实初始化（迁移数据库、加载模型）才值得第二个窗口：`splashscreen`（小、`decorations: false`、`resizable: false`、`alwaysOnTop`、`center`）+ `main`（`visible: false`），完成后 `splash.close()` 再 `main.show()`。
2. 切换时机来自真实完成信号：后端初始化在 `setup` 里 `spawn` 出去不阻塞事件循环；前端也有重初始化时用 `set_complete("frontend"|"backend")` 两票齐才切换（官方示例），禁 `sleep`/`setTimeout` 假装加载。
3. 形状：`async fn boot(app: AppHandle) -> anyhow::Result<()>` 里做初始化 → `splash.close()?` → `main.show()?`；setup 内 `tauri::async_runtime::spawn(async move { if let Err(e) = boot(h.clone()).await { tracing::error!(error = %e, "boot failed"); h.exit(1); } })`。失败必须有出口（退出或把 splash 切成错误页），不留永不关闭的 splash。

## single-instance（TA-26）

1. `.plugin(tauri_plugin_single_instance::init(|app, argv, cwd| { focus_main(app); /* 路由 argv */ }))` 必须是 `Builder` 上**第一个** `.plugin()`：它在初始化阶段发现已有实例就退出当前进程，排在它前面的插件副作用（写状态文件、注册协议）已经发生。
2. 回调在**已运行实例**里执行，收到第二实例的 `argv`（含可执行路径）与 `cwd`：典型动作是聚焦主窗 + 把文件参数转成事件；不在回调里创建窗口。
3. 深链：Windows/Linux 的深链是以 URL 为 argv 启动第二实例，插件开 feature `deep-link` 并把 `tauri_plugin_deep_link::init()` 紧随其后注册，URL 才会转给 `app.deep_link().on_open_url`；macOS 由 LaunchServices 保证 `.app` 单实例并直接投递 URL 事件，不走 argv。
4. 无 JS API、无权限标识：capabilities 里写 `single-instance:default` 会 build 失败。

## 验证

- 配置：每个平台覆盖文件各跑一次 `tauri dev`/`tauri build --debug`；`cargo run` 直接跑不算验证（看不到 `--config`）。
- 窗口/标题栏/托盘/菜单：按 XP-09 三端冒烟——拖拽、三键、双击标题、关闭→隐藏、macOS Dock Reopen 能把隐藏窗唤回（TA-42）、最后窗口关闭后进程是否仍活、托盘左右键、Cmd+C/V 在 webview 内可用；Accessory 应用另确认 Dock 无图标且没有功能只挂在菜单栏快捷键上。
- 启动：冷启动到首帧毫秒数（TA-05/TA-10 口径）；splash 场景确认初始化失败会退出。单实例：第二次启动带文件参数与深链 URL，确认已运行实例收到 argv 并聚焦。
