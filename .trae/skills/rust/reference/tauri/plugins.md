# tauri/plugins — 官方插件目录：权限标识、平台矩阵与每个插件的陷阱

目的：`Cargo.toml` 出现 `tauri-plugin-*`、前端 import `@tauri-apps/plugin-*`、capability 里出现 `<plugin>:allow-*`，或用户问「怎么读文件 / 弹对话框 / 调外部命令 / 自动更新 / 扫码」时加载；本文件只给每个官方插件的权限面、平台覆盖与已知陷阱。IPC 选型、体积与 ACL 最小面见 [../tauri.md](../tauri.md)（TA-06/07/12；插件纪律 TA-14/15/18/30/34），平台脾气见 [../xplat.md](../xplat.md)，签名与 updater 发布链路见 [../ship.md](../ship.md)（SH-07..15）。版本：tauri 2.11.x + `tauri-plugin-*` 2.x（插件大版本随 tauri；v1 的 `allowlist` 是迁移债务，2.x 一律 capabilities）。

## 通用纪律（TA-14、TA-18、TA-30）

1. 四件缺一各有各的症状，别一律去查权限：缺 `tauri-plugin-<name>` 依赖 = Rust 编译错误（capability 还会因引用不存在的权限在 ACL 构建期 fail）；缺 `.plugin(tauri_plugin_<name>::init())` = 前端报 `plugin <name> not found`；缺 capability 里的 `<name>:default`/`<name>:allow-*` = 前端报 `<name>.<cmd> not allowed`；前端包 `@tauri-apps/plugin-<name>` 与 crate 大版本要对齐。
2. ACL 只拦 IPC：Rust 端 `app.dialog()`/`app.store()`/`app.shell()` 直接用插件 API 不受 capability 约束。需要校验、密钥、任意路径的操作放 Rust 命令里做，而不是给前端开宽 scope（TA-12）。
3. `<name>:default` 的含义因插件而异：`clipboard-manager:default` 与 `global-shortcut:default` **是空集**（必须逐个 allow）；`shell:default` 只含 `allow-open`；`fs:default` 只含 app 专属目录的读 + mkdir；`sql:default`/`store:default` 全开。写 capability 前 `rg '"<name>:' src-tauri/gen/schemas/desktop-schema.json` 核对真实标识，不凭印象。
4. 平台门控三处同步：Cargo 里 desktop-only 插件放 `[target.'cfg(not(any(target_os = "android", target_os = "ios")))'.dependencies]`（XP-10）；注册用 `#[cfg(desktop)]`/`#[cfg(mobile)]`；capability 文件加 `"platforms": ["linux", "macOS", "windows"]`——移动端构建引用了未编译插件的权限 = ACL 构建失败。

```rust
// ✓ 官方模式：平台专属插件在 setup 里按 cfg 注册
.setup(|app| {
    #[cfg(desktop)]
    {
        app.handle().plugin(tauri_plugin_updater::Builder::new().build())?;
        app.handle().plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--minimized"]),
        ))?;
    }
    #[cfg(mobile)]
    app.handle().plugin(tauri_plugin_biometric::init())?;
    Ok(())
})
```

## 总表

| 插件 | crate / npm | 权限（`<name>:default` 与常用 allow） | 平台 | 一句话陷阱 |
|---|---|---|---|---|
| fs | `tauri-plugin-fs` / `@tauri-apps/plugin-fs` | default=app 目录读+mkdir；`fs:allow-appdata-write-recursive`、`fs:scope-download-recursive`、自定义 `{"path":"$APPDATA/**"}` | 全部 | scope 变量是 `$APPDATA` 不是 `$APP_DATA`；裸 `**` = 整盘 |
| dialog | `tauri-plugin-dialog` / `@tauri-apps/plugin-dialog` | default 含 open/save/message/ask/confirm | 全部 | 取消返回 `null`；选中路径只在本次会话自动进 fs scope |
| shell | `tauri-plugin-shell` / `@tauri-apps/plugin-shell` | default 只含 `allow-open`；`shell:allow-execute` 必须带 scope | execute 仅桌面 | `args: true` = 任意参数；`open` 已弃用改 opener |
| opener | `tauri-plugin-opener` / `@tauri-apps/plugin-opener` | default=`open-url`(http/https/mailto/tel)+`reveal-item-in-dir`；`opener:allow-open-path` 需路径 scope | 全部（reveal 桌面） | `openPath` 指向可执行文件 = 直接运行 |
| http | `tauri-plugin-http` / `@tauri-apps/plugin-http` | `http:default` + `allow: [{"url": "https://api.example.com/*"}]` | 全部 | 无 URL scope 时所有请求被拒；cookie 与 webview 不互通 |
| websocket | `tauri-plugin-websocket` / `@tauri-apps/plugin-websocket` | `websocket:default`（connect/send，无 URL scope） | 全部 | 无心跳无重连；每帧过 IPC |
| upload | `tauri-plugin-upload` / `@tauri-apps/plugin-upload` | `upload:default`（upload/download，无 scope） | 全部 | 路径不受 fs scope 管；body 是裸字节不是 multipart |
| sql | `tauri-plugin-sql`（features `sqlite`/`mysql`/`postgres`）/ `@tauri-apps/plugin-sql` | `sql:default` 全开，无按库/按语句 scope | 全部 | 事务跨 IPC 不成立（池连接不固定） |
| store | `tauri-plugin-store` / `@tauri-apps/plugin-store` | `store:default` 全开 | 全部 | 明文 JSON，禁存密钥 |
| stronghold | `tauri-plugin-stronghold` / `@tauri-apps/plugin-stronghold` | `stronghold:default` | 全部 | argon2 按设计就慢；salt 文件丢 = 库报废 |
| clipboard-manager | `tauri-plugin-clipboard-manager` / `@tauri-apps/plugin-clipboard-manager` | **default 为空**：`allow-write-text`/`allow-read-text`/`allow-read-image`/`allow-write-image` | 全部 | X11 下 app 退出剪贴板内容消失 |
| notification | `tauri-plugin-notification` / `@tauri-apps/plugin-notification` | default 含 notify/permission | 全部 | 桌面无点击回调；未打包时 Windows/macOS 行为不准 |
| global-shortcut | `tauri-plugin-global-shortcut` / `@tauri-apps/plugin-global-shortcut` | **default 为空**：`allow-register`/`allow-unregister`/`allow-is-registered` | 桌面 | Pressed+Released 各触发一次；Wayland 不支持 |
| autostart | `tauri-plugin-autostart` / `@tauri-apps/plugin-autostart` | default 含 enable/disable/is-enabled | 桌面 | dev 下 enable 注册的是 `target/debug` 二进制 |
| os | `tauri-plugin-os` / `@tauri-apps/plugin-os` | default 含 platform/arch/version/os-type/family/locale/hostname/exe-extension | 全部 | `platform()` 等同步、`hostname()`/`locale()` 异步；hostname 是 PII |
| process | `tauri-plugin-process` / `@tauri-apps/plugin-process` | `process:allow-exit`、`process:allow-restart`（JS 叫 `relaunch`） | 桌面为主 | `std::process::exit` 绕过 `ExitRequested` |
| log | `tauri-plugin-log` / `@tauri-apps/plugin-log` | `log:default`（allow-log） | 全部 | 默认 `max_file_size` 约 40KB + KeepOne；双 logger 初始化 panic |
| deep-link | `tauri-plugin-deep-link` / `@tauri-apps/plugin-deep-link` | default 只含 `get-current`；dev `register()` 需 `allow-register` | 全部 | Windows/Linux 二次启动要 single-instance；macOS dev 裸二进制收不到 |
| updater | `tauri-plugin-updater` / `@tauri-apps/plugin-updater` | default 含 check/download/install | 桌面 | 私钥丢失 = 已装用户永远无法再更新 |
| localhost | `tauri-plugin-localhost`（无 npm、无权限） | — | 桌面 | 官方不推荐：前端资源暴露在本机 TCP 端口 |
| cli | `tauri-plugin-cli` / `@tauri-apps/plugin-cli` | `cli:default`（cli-matches） | 桌面 | `--help` 不会自动打印退出 |
| biometric | `tauri-plugin-biometric` / `@tauri-apps/plugin-biometric` | default 含 authenticate/status | 移动 | 结果是 IPC 上的布尔值，不是密钥 |
| nfc | `tauri-plugin-nfc` / `@tauri-apps/plugin-nfc` | default 含 is-available/scan/write | 移动 | iOS 要 entitlement + usage description |
| barcode-scanner | `tauri-plugin-barcode-scanner` / `@tauri-apps/plugin-barcode-scanner` | default 含 scan/cancel/permissions/vibrate/open-app-settings | 移动 | `windowed` 模式要透明 webview |
| haptics | `tauri-plugin-haptics` / `@tauri-apps/plugin-haptics` | default 含 vibrate/impact-feedback/notification-feedback/selection-feedback | 移动 | 桌面调用报错，不要让它阻断流程 |
| geolocation | `tauri-plugin-geolocation` / `@tauri-apps/plugin-geolocation` | default 含 permissions/get-current-position/watch-position/clear-watch | 移动 | 缺 Info.plist/Manifest 声明 = 静默拒绝 |

## 桌面 + 移动通用插件

### fs（TA-15）
- `BaseDirectory.AppData|AppLocalData|AppConfig|AppCache|AppLog|Resource|Download|Document|Home|Temp` 对应 scope 变量 `$APPDATA`/`$APPLOCALDATA`/`$APPCONFIG`/`$APPCACHE`/`$APPLOG`/`$RESOURCE`/`$DOWNLOAD`/`$DOCUMENT`/`$HOME`/`$TEMP`；`$APPDATA/*` 只匹配一层、`$APPDATA/**` 递归；禁止裸 `**` 与 `$HOME/**`。`fs:deny-default` 已拒绝 Windows 的 `$APPLOCALDATA/EBWebView/**`（webview 数据），不要用 allow 打穿。
- 现成 scope 权限优先于手写：`fs:allow-appdata-read-recursive`、`fs:allow-appdata-write-recursive`、`fs:scope-download-recursive`（只加 scope 不加命令）。
- 调用：`readTextFile('config.json', { baseDir: BaseDirectory.AppData })`、`writeFile(path, bytes, { baseDir })`、`exists`/`mkdir(p, { recursive: true })`/`readDir`/`stat`；`watch(paths, cb, { baseDir, recursive, delayMs })` 需要 crate feature `watch`（`watchImmediate` 不去抖，消费端自己去抖 + 幂等，XP-06）。
- 大文件：`readFile` 虽走 raw IPC（非 base64）仍要整块进 webview 内存；解析类工作放 Rust 命令（`spawn_blocking`），媒体展示走 `convertFileSrc` + asset protocol（TA-07）。
- dialog 选中的路径由 dialog 插件在运行时加进 fs/asset scope（仅本次会话）；「最近文件」重启后要能打开 → 加 `tauri-plugin-persisted-scope`。Android 的 dialog 返回 `content://` URI，直接交给 plugin-fs，不要自己转路径。
- Rust 端 `std::fs` 不受 scope 约束：前端传来的相对路径先 `app.path().app_data_dir()?.join(rel)` 并拒绝 `..`（XP-04）。

### dialog
- `open({ multiple, directory, filters: [{ name: 'Images', extensions: ['png', 'jpg'] }], defaultPath, title })` 返回 `string | string[] | null`；`save({ filters, defaultPath })` 返回 `string | null`。`null` 是取消不是错误——`if (!path) return`。
- `message(msg, { title, kind: 'info' | 'warning' | 'error', okLabel })`；`ask` 是 Yes/No、`confirm` 是 OK/Cancel，都返回 boolean。2.x 字段名是 `kind`，`type` 是 v1 写法。
- `extensions` 不带点；macOS 不显示 filter 名称、Linux GTK 显示——关键信息别只放 filter name。
- Rust：`app.dialog().file().pick_file(|p| { … })` 回调式；`blocking_pick_file()` 禁止在主线程/`setup` 里调（与事件循环互锁，macOS 死锁）——放 **async command**。这与 **rfd** 相反：`rfd::FileDialog` 必须留在**同步** command（主线程，TA-41）；async command 里改 `rfd::AsyncFileDialog`。两套 API 不要混着用错线程。
- 弹窗是用户手势的证据：fs 写、shell 执行、upload 的路径都应来自 dialog 或按钮，而不是页面加载即触发。

### shell（TA-15、TA-32）
- `shell:allow-execute` 每条 `{ name, cmd, args, sidecar }`：`name` 是前端 `Command.create(name, args)` 的键；`args` 写数组——字面量精确匹配、`{ "validator": "\\S+" }` 按整串正则（内部已加 `^…$`）；`args: true` 等于任意参数，只许内部工具。
- sidecar：`bundle.externalBin: ["binaries/my-sidecar"]`，文件名带 target triple（`my-sidecar-x86_64-apple-darwin`，XP-07）；scope `{ "name": "binaries/my-sidecar", "sidecar": true, "args": [...] }`，前端 `Command.sidecar('binaries/my-sidecar', args)`。
- `execute()` 返回 `{ code, stdout, stderr, signal }`；长跑进程 `spawn()` → `cmd.stdout.on('data', …)`/`cmd.on('close', …)`，`child.write()`/`child.kill()`；选项 `{ cwd, env, encoding: 'gbk' | 'raw' }`——Windows 中文环境输出乱码是 encoding 没设。
- 禁 `Command.create('sh', ['-c', userInput])`（PR-01）；Rust 端 `app.shell().command("git").args(["status"]).output().await` 不受 scope 管，更要校验参数。插件内部 Windows 已带 `CREATE_NO_WINDOW`，自己用 `std::process::Command` 才需补（XP-07）。
- `open()`/`shell:allow-open` 已弃用：只要 execute 就别加 `shell:default`（它带 `allow-open`），链接/文件交给 opener。

### opener
- `openUrl(url, openWith?)`、`openPath(path, openWith?)`、`revealItemInDir(path)`；默认 URL scope 只放 `http`/`https`/`mailto`/`tel`，其他协议在 `opener:allow-open-url` 的 `allow: [{ "url": "myapp://*" }]` 显式加。
- `openPath` 默认无权限：`{ "identifier": "opener:allow-open-path", "allow": [{ "path": "$APPDATA/exports/**" }] }`；指向 `.exe`/`.sh`/`.app` 即执行——路径来自用户输入时先 canonicalize + 前缀校验（XP-05）。
- `openWith` 受 scope 条目的 `app` 字段约束；不传 = 系统默认程序。Rust：`app.opener().open_url("https://…", None::<&str>)?`。
- 移动端 `revealItemInDir` 无语义，调用前按平台隐藏入口。

### http
- `import { fetch } from '@tauri-apps/plugin-http'` 与 web `fetch` 同签名，额外 `{ connectTimeout, maxRedirections, proxy }`；请求由 Rust reqwest 发出、不受 CORS 限制，但必须命中 scope：`{ "identifier": "http:default", "allow": [{ "url": "https://api.example.com/*" }], "deny": [{ "url": "https://api.example.com/admin/*" }] }`，模式按 URLPattern，`https://*.example.com/*` 匹配子域。
- cookie/重定向：不共享 webview 的 cookie jar（webview 里的登录态 plugin-http 看不到）；cookie 是否持久化由 crate feature `cookies` 决定，以 docs.rs 为准；`maxRedirections: 0` 关跟随。
- 被浏览器禁止的头（`Origin`/`Host` 等）要 crate feature `unsafe-headers`——开了写清理由。
- 带 API key / 签名 / 内网地址的请求放 Rust 命令里用 reqwest（密钥不进前端包，可做 SSRF 校验）；前端 `fetch` 只给公开端点。大文件下载用 upload 插件的 `download` 直写磁盘，不要 `await res.arrayBuffer()` 把整个文件拉过 IPC（TA-08）。

### websocket（TA-18）
- 只在 webview 原生 `WebSocket` 做不到时用（自定义 header、非标 TLS、绕代理策略）；否则原生 API 少一跳 IPC。
- `const ws = await WebSocket.connect('wss://…', { headers: { Authorization: 'Bearer …' } }); ws.addListener(m => …); await ws.send('txt'); await ws.disconnect();`——消息 `{ type: 'Text' | 'Binary' | 'Ping' | 'Pong' | 'Close', data }`，`Close` 也走监听器，必须处理。
- Rust 端 tokio-tungstenite 维持连接，但**不做心跳、不做重连**：自己发 Ping 并设超时，重连用指数退避 + 上限（AS-11）。
- 无 URL scope（权限只有 connect/send）：目标主机白名单要么在 Rust 命令里包一层，要么接受前端可连任意地址。TLS 后端由 crate feature（`rustls-tls`/`native-tls`）二选一，默认值以 docs.rs 上该版本的 feature 表为准——交叉编译/静态链接前先确认（`native-tls` 要系统 OpenSSL）；高频二进制帧先看 TA-06。

### upload（TA-18）
- `upload(url, filePath, onProgress?, headers?)` 返回响应体字符串；`download(url, filePath, onProgress?, headers?, body?)`；进度 `{ progress, progressTotal, total, transferSpeed }` 经 Channel 推送，前端节流再渲染（TA-11）。
- `filePath` 是 Rust 端绝对路径，**不受 fs scope 管**：谁能调 `upload` 谁就能把任意文件发到任意 URL——路径只接受 dialog 返回值或 app 目录拼接，必要时用 Rust 命令包住并校验。
- `upload` 把文件裸字节当 body（`Content-Type` 自己在 headers 给）；服务器要 `multipart/form-data` 就得在 Rust 用 `reqwest::multipart` 自己写。
- 无重试：失败后 `download` 留下半截文件，先写临时名再 rename（XP-06）。

### sql（TA-34）
- `tauri-plugin-sql = { version = "2", features = ["sqlite"] }`；迁移在 Rust 注册：`Builder::default().add_migrations("sqlite:app.db", vec![Migration { version: 1, description: "init", sql: "CREATE TABLE …", kind: MigrationKind::Up }]).build()`。迁移在**首次 `Database.load`** 时跑，不是启动时；要启动就跑用 `"plugins": { "sql": { "preload": ["sqlite:app.db"] } }`。
- `sqlite:app.db` 相对路径落在 `app_config_dir()`（不是 app data）；绝对路径/`:memory:` 照常。
- 前端：`const db = await Database.load('sqlite:app.db'); await db.execute('INSERT INTO t (a) VALUES ($1)', [a]); const rows = await db.select<T[]>('SELECT id, a FROM t WHERE id = $1', [id]);`——占位符 sqlite/postgres 用 `$1`、mysql 用 `?`；禁模板字符串拼 SQL（SX-04）。
- 插件内部是 sqlx Pool，每次 `execute` 可能拿到不同连接：`BEGIN`/`COMMIT` 跨 IPC 不成立，事务一律在 Rust 端用 sqlx 写（SX-07）。
- ACL 无法限制 SQL 文本：前端一处 XSS = 整库读写。查询多于几条或有写事务时，sqlx 放 Rust 命令里、前端只调类型化命令（TA-13、SX-03）；SQLite 并发写在迁移里开 `PRAGMA journal_mode=WAL`。

### store（TA-34）
- Rust：`use tauri_plugin_store::StoreExt; let store = app.store("settings.json")?; store.set("theme", serde_json::json!("dark")); let v = store.get("theme"); store.save()?;`。JS：`const store = await load('settings.json', { autoSave: 100, defaults: { theme: 'light' } }); await store.set('theme', 'dark'); await store.get<string>('theme');`。
- 相对路径落 `app_data_dir()`；同一路径在 Rust/JS 间共享同一内存实例，不要再用 plugin-fs 去改那份 JSON。
- `autoSave` 默认 100ms 去抖；传 `false` 后必须显式 `save()`，否则退出丢改动。`LazyStore` 只是延迟到首次访问才读盘。
- 明文 JSON：token/密码走 stronghold 或 Rust 端 `keyring`（OS 钥匙串）；给设置加 `version` 字段并在加载时迁移。用户可手改文件，`get` 出来的值按 SE-07 校验，不要 `as Settings` 直接信。

### stronghold
- 初始化要 app 路径，放 `setup`：`app.handle().plugin(tauri_plugin_stronghold::Builder::with_argon2(&app.path().app_local_data_dir()?.join("salt.txt")).build())?;`；自定义 KDF 用 `Builder::new(|password| hash_32_bytes(password))`（必须返回 32 字节；argon2id 参数写明并钉死，改参数 = 旧库打不开）。
- 模型：快照文件（`vault.hold`）→ 命名 Client → Store（可读回的键值）/ Vault（只能「用」不能读的私钥，经 procedure 签名/派生）。只存 token 用 Store 就够。
- JS：`const sh = await Stronghold.load(`${await appDataDir()}/vault.hold`, password); const client = await sh.loadClient('main').catch(() => sh.createClient('main')); const store = client.getStore(); await store.insert('token', Array.from(new TextEncoder().encode(t))); await sh.save();`——值是 `number[]`，`save()` 才落盘。
- argon2 按设计慢（秒级）：进程内只 `load` 一次、缓存句柄；salt 文件不保密但必备，和快照一起备份。
- 单个 token 的需求先比较 Rust 端 `keyring` crate（OS 钥匙串，零配置）；stronghold 的收益在多密钥 + 需要签名 procedure 的场景（SIMP-01）。

### clipboard-manager
- default 为空：`clipboard-manager:allow-write-text`/`allow-read-text`/`allow-write-image`/`allow-read-image`/`allow-write-html`/`allow-clear` 逐个加。
- `writeText(s)`、`readText()`、`writeImage(Image | Uint8Array)`、`readImage()`（返回 `Image`，`.rgba()`/`.size()`）、`writeHtml(html, altText?)`、`clear()`；Rust `app.clipboard().write_text("…")?`。
- 读取只在用户手势里做（iOS 读剪贴板弹系统横幅）；不做后台轮询监听。Linux X11 剪贴板由写入进程持有，app 退出内容即消失（除非桌面有剪贴板管理器）。
- 纯文本复制优先 web `navigator.clipboard.writeText`（需用户手势）；插件用于读取、图片、HTML 与 Linux 可靠性。

### notification
- 流程：`let ok = await isPermissionGranted(); if (!ok) ok = (await requestPermission()) === 'granted'; sendNotification({ title, body, icon, sound })`；移动端必须先请求（Android 13+ 是运行时权限），桌面通常直接 granted 但仍要查。
- 桌面**没有点击回调**（notify-rust 不回传）：导航/确认逻辑不能建立在「用户点了通知」上；移动端用 `onAction`/`onNotificationReceived` + `registerActionTypes`，Android 8+ 需要 `createChannel`。
- 未打包时行为不准：Windows dev 显示为 PowerShell 发送、macOS 未打包二进制常不弹权限——验收用 `tauri build --debug` 产物（XP-09）。
- `sound` 是平台声音名，`icon` 在 Linux 是路径/图标名、Windows 只用 app 图标；内容不放敏感信息（锁屏可见）。Rust：`app.notification().builder().title("…").body("…").show()?`。

### os
- `platform()`/`arch()`/`version()`/`type()`/`family()`/`exeExtension()`/`eol()` 是同步函数（初始化时注入）；`locale()`/`hostname()` 返回 Promise。`platform()` 取值 `linux|macos|windows|ios|android`。
- 用途边界：UI 键位提示（Cmd/Ctrl）、i18n 兜底 locale、诊断报告里的版本——`hostname` 是 PII，不上报、不做设备指纹。
- 编译期能分的分支用 `#[cfg(target_os)]`，不要运行时查 `platform()` 再分（XP-02）。

### process
- `exit(code?)` / `relaunch()`（权限 `process:allow-exit`/`process:allow-restart`）；Rust 对应 `app.exit(0)`/`app.request_restart()`——这两个才可靠触发 `RunEvent::ExitRequested { api, code, .. }`，JS `relaunch()` 内部走的正是 `request_restart`。`app.restart()` 在主线程会跳过 `ExitRequested`/`Exit` 直接换进程，退出前的保存逻辑被静默绕过，别用；`std::process::exit` 跳过所有清理（Drop、store 落盘），禁用。
- `ExitRequested` 里 `code == None` 表示「最后一个窗口被关」：托盘常驻应用在这里 `api.prevent_exit()`。重启路径的 `code` 是 `RESTART_EXIT_CODE`（`i32::MAX`）而非 `None`，且此时 `prevent_exit()` 是空操作——重启拦不住，只能在这里做保存。
- `relaunch` 以当前可执行路径重启（AppImage 读 `APPIMAGE` 环境变量）；更新后重启用它，不要自己 spawn 自身。移动端无「重启进程」语义，`relaunch` 不进移动端路径。

### log
- `tauri_plugin_log::Builder::new().targets([Target::new(TargetKind::Stdout), Target::new(TargetKind::LogDir { file_name: Some("app".into()) }), Target::new(TargetKind::Webview)]).level(log::LevelFilter::Info).level_for("hyper", log::LevelFilter::Warn).max_file_size(5_000_000).rotation_strategy(RotationStrategy::KeepAll).build()`；默认 `max_file_size` 约 40KB 且 `KeepOne`，生产必须显式设。
- 它是 `log` facade 的全局 logger：项目已 `tracing_subscriber::init()`/`env_logger::init()` 再注册 = panic「logger already set」。二选一；用 tracing 的项目让 tracing 走 `log` 兼容层进插件，或不装插件只在 Rust 端用 `tracing-appender` 写 `app_log_dir()`。
- 前端 `import { info, attachConsole } from '@tauri-apps/plugin-log'`：`attachConsole()` 把 Rust 日志转到 devtools（需 `Webview` target）；JS `info()` 需要 `log:default`。
- 日志目录 `app_log_dir()`（macOS `~/Library/Logs/<id>`、Linux `~/.local/share/<id>/logs`、Windows `%LOCALAPPDATA%\<id>\logs`）；`format()` 自定义行格式；级别按 OBS-04，字段脱敏按 OBS-02（用户路径含用户名）。
- dev 才 `Debug` + `Webview`；release `Info`/`Warn` + `LogDir`。`if cfg!(debug_assertions)` 包整个插件只在「生产不要日志」时成立，桌面 app 一般需要生产文件日志排障。

### deep-link（TA-26）
- 配置 `"plugins": { "deep-link": { "desktop": { "schemes": ["myapp"] }, "mobile": [{ "host": "example.com", "pathPrefix": ["/open"] }] } }`；capability `deep-link:default`（只含 `get-current`）。
- 注册：Windows/Linux 由安装器写注册表/`.desktop`，dev 下 Rust `app.deep_link().register("myapp")?`（JS 用需 `allow-register`）；macOS 由 bundler 写 `Info.plist`，**dev 裸二进制收不到链接**，用 `tauri build --debug` 验证。
- Windows/Linux 二次唤起是新进程：必须 `tauri-plugin-single-instance`（feature `deep-link`）且作为**第一个**注册的插件，它把 URL 转给 `on_open_url`；否则弹出第二个实例。
- 接收：Rust `app.deep_link().on_open_url(|e| { for u in e.urls() { … } })`；JS `onOpenUrl(urls => …)` + 启动时 `getCurrent()`（冷启动时监听器注册晚于事件）。
- URL 是不可信输入：`Url::parse` → 白名单 path/query，禁直接喂给 webview 导航或 `openUrl`（SE-07）。移动端 App Links/Universal Links 还要 `assetlinks.json` / `apple-app-site-association` + Associated Domains entitlement，缺一则回退成浏览器打开。

## 桌面专用插件

### global-shortcut
- default 为空：`global-shortcut:allow-register`/`allow-unregister`/`allow-is-registered`（JS 用）；纯 Rust 处理不需要任何权限。
- Rust：`tauri_plugin_global_shortcut::Builder::new().with_handler(|app, shortcut, event| { if event.state() == ShortcutState::Pressed { … } }).build()`，再 `app.global_shortcut().register(Shortcut::new(Some(Modifiers::SUPER | Modifiers::SHIFT), Code::KeyK))?`；JS：`register('CommandOrControl+Shift+K', e => { if (e.state === 'Pressed') … })`。Pressed 与 Released 各触发一次，不过滤就双击。
- 冲突：Windows 注册被占用组合返回 Err；macOS/X11 可能注册成功但永不触发（系统/其他进程先抢）——注册后给用户可见反馈并允许改键；Wayland 无全局快捷键 API，直接不支持。
- `tauri dev` 热重载/多实例会互相抢：启动先 `unregister_all()`，并与 single-instance 配合。处理函数在插件线程回调：只做 `emit`/唤起窗口（`show()` + `set_focus()`），重活交命令。

### autostart
- `init(MacosLauncher::LaunchAgent, Some(vec!["--minimized"]))`：参数会在登录启动时传给 app，配合 cli 插件或 `std::env::args` 决定是否隐藏主窗（TA-10）。
- 落点：macOS `~/Library/LaunchAgents/<bundle id>.plist`（`AppleScript` 变体进「登录项」）、Linux `~/.config/autostart/<name>.desktop`、Windows `HKCU\…\CurrentVersion\Run`——三者记的都是**当前可执行文件绝对路径**：app 移动/AppImage 改名/dev 下注册的 `target/debug` 二进制都会失效；`isEnabled()` 只看条目存在，不校验路径。
- 只做用户显式开关（设置页 `enable()`/`disable()`），禁启动即 `enable()`；升级后路径可能变化 → 启动时若 `isEnabled()` 为真可重新 `enable()` 刷新路径。
- macOS 沙盒/App Store 不许 LaunchAgent；Linux 各桌面环境 `.desktop` 支持度不一（XP-09 逐平台冒烟）。

### updater（TA-34）
- `tauri.conf.json`：`"bundle": { "createUpdaterArtifacts": true }`，`"plugins": { "updater": { "endpoints": ["https://releases.example.com/{{target}}/{{arch}}/{{current_version}}"], "pubkey": "…", "windows": { "installMode": "passive" } } }`；模板变量 `{{current_version}}`/`{{target}}`/`{{arch}}`。
- 密钥：`tauri signer generate -w ~/.tauri/app.key`，CI 注入 `TAURI_SIGNING_PRIVATE_KEY` 与 `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`；私钥离线、公钥进配置（SH-10）。**私钥丢失 = 已安装用户永远收不到更新**（只能手动重装），备份策略先于首发。
- `latest.json`：`{ "version": "1.2.0", "notes": "…", "pub_date": "2026-08-22T00:00:00Z", "platforms": { "darwin-aarch64": { "signature": "<.sig 文件内容>", "url": "https://…/app.app.tar.gz" }, "windows-x86_64": { … }, "linux-x86_64": { … } } }`——键是 `{{target}}-{{arch}}`，`signature` 是 `.sig` 内容不是链接；`version` 必须严格大于当前才提示；动态端点无更新返回 204。
- 前端：`const u = await check(); if (u) { await u.downloadAndInstall(ev => { /* Started / Progress / Finished */ }); await relaunch(); }`（`relaunch` 来自 process 插件）。Windows 上安装会直接结束进程跑安装器，`downloadAndInstall` 之后的代码在 Windows 不会执行——「更新完成提示」放重启后的首启。
- 覆盖面：Linux 除 AppImage 原地替换外，deb/rpm 也能更新——插件按 bundle 类型分发到 `dpkg -i`/`rpm -U`，需要提权（先试 `pkexec`，再退到 zenity/kdialog 问密码），无图形提权环境会失败，按发行版实测；macOS 产物必须签名 + 公证，否则替换后 Gatekeeper 拦（SH-09）；`tauri dev` 下 `check()` 必败，用 `build --debug` + 本地静态服务器验证；CI 与回滚见 SH-07/12。

### localhost
- 作用：把前端从 `tauri://localhost`（Windows 为 `http://tauri.localhost`）改为真 `http://localhost:<port>`，只为硬要求 http origin 的第三方库（OAuth 回调页、某些 WebRTC/Service Worker 行为）。
- 用法：`let port = portpicker::pick_unused_port().expect("no free port"); tauri::Builder::default().plugin(tauri_plugin_localhost::Builder::new(port).build()).setup(move |app| { WebviewWindowBuilder::new(app, "main", WebviewUrl::External(format!("http://localhost:{port}").parse()?)).build()?; Ok(()) })`。
- 官方明确不推荐：前端资源暴露在本机任意进程/浏览器标签可达的 TCP 端口上、无 TLS，多用户机器上其他用户也能访问。能用自定义协议就别用它。无 JS API、无权限标识；随机端口是底线。

### cli
- `"plugins": { "cli": { "description": "…", "args": [{ "name": "verbose", "short": "v" }, { "name": "file", "index": 1, "takesValue": true }], "subcommands": { "import": { "args": [] } } } }`；Rust `app.cli().matches()?` → `matches.args["file"].value`（`serde_json::Value`）、`matches.subcommand`；JS `getMatches()`（`cli:default`）。
- `--help`/`--version` 不会自动打印退出：出现在 `args` 里（值为帮助文本），要自己 `println!` 后 `std::process::exit(0)`（app 尚未启动，这里 exit 合理）。
- single-instance 的二次启动参数只以 `Vec<String>` 原样给回调，`matches()` 不会重新解析——要么自己用 clap 解析，要么只传简单位置参数。
- 需要子命令/复杂校验的 CLI 直接在 `main` 里用 clap 解析完再进 `tauri::Builder`；插件只值得用在「几个开关」的场景（SIMP-01）。

## 移动专用插件

### biometric
- `const s = await checkStatus(); if (s.isAvailable) await authenticate('解锁保险库', { allowDeviceCredential: true, cancelTitle: '取消', fallbackTitle: '使用密码' })`——失败抛异常，成功 resolve；`biometryType` 区分 TouchID/FaceID/虹膜。
- iOS 必须 `NSFaceIDUsageDescription`；Android 由插件声明 `USE_BIOMETRIC`，`allowDeviceCredential: true` 才能回退 PIN/图案。
- 结果只是 IPC 上的一个布尔值：它是 UX 门，不是密钥。真正保护凭据要把密钥绑定到 stronghold/Keychain，认证通过后再解密；插件后续加入的生物识别绑定加解密接口以 docs.rs 为准。桌面无实现，前端按 `platform()` 隐藏入口。

### nfc
- `await isAvailable()`；`scan({ type: 'ndef' }, { keepSessionAlive: true })` 返回 `{ id, kind, records: [{ tnf, kind, id, payload }] }`；随后 `write([textRecord('hi'), uriRecord('https://…')])`，写完会话自动结束。
- iOS：Xcode 加 Near Field Communication Tag Reading capability（entitlement `com.apple.developer.nfc.readersession.formats`）+ `NFCReaderUsageDescription`；系统扫描 UI 60 秒超时，不能自绘。
- Android：插件加 `android.permission.NFC`；扫描基于前台分发，只在 app 前台有效；要「贴卡唤起 app」需手写 `NDEF_DISCOVERED` intent filter。
- `payload` 是字节数组 + TNF 类型：先按类型解码再信（SE-07）；卡片 `id` 可被克隆，不当身份凭证。

### barcode-scanner
- `await requestPermissions()` 后 `scan({ windowed: true, formats: [Format.QRCode, Format.EAN13], cameraDirection: 'back' })` → `{ content, format, bounds }`；`cancel()` 结束；一次 `scan` 只回一个结果，连续扫要循环调。
- `windowed: true` 把相机画面渲染在 webview 之下：html/body 与扫描页容器必须 `background: transparent`，其他元素遮挡就看不见相机；`false` 则用系统全屏扫码 UI。
- iOS `NSCameraUsageDescription`；Android CAMERA 由插件声明但仍需运行时 `requestPermissions()`；被永久拒绝时给 `openAppSettings()` 入口。限定 `formats` 提升识别速度；桌面无实现，入口按平台隐藏。

### haptics
- `impactFeedback('light' | 'medium' | 'heavy' | 'soft' | 'rigid')`、`notificationFeedback('success' | 'warning' | 'error')`、`selectionFeedback()`、`vibrate(ms)`；iOS 走 Taptic，Android 映射为振动模式（插件声明 `VIBRATE`）。
- 只跟随用户动作（点选、完成、出错）触发，不做循环/定时震动；调用包 `try`，桌面或设备不支持时静默跳过，绝不让触感失败阻断业务。

### geolocation
- `const p = await checkPermissions(); if (p.location !== 'granted') await requestPermissions(['location']); const pos = await getCurrentPosition({ enableHighAccuracy: true, timeout: 10_000, maximumAge: 0 });`；`watchPosition(opts, cb)` 返回 id，组件卸载必须 `clearWatch(id)`（省电）。
- 声明缺失 = 静默拒绝/崩溃：iOS `NSLocationWhenInUseUsageDescription`（后台再加 Always 变体）；Android `ACCESS_COARSE_LOCATION`/`ACCESS_FINE_LOCATION` 写进 `gen/android/app/src/main/AndroidManifest.xml`。
- 插件只提供前台定位，「后台轨迹」不要承诺；`enableHighAccuracy` 默认关，粗定位够用就别开。桌面无实现；webview 自带 `navigator.geolocation` 在三引擎上权限弹窗不一致（XP-01），桌面定位需求另起 Rust 方案或放弃。

## 验证

- 权限：每个插件调用在 `tauri dev` 下至少触发一次，控制台无 `not allowed`；再删掉一条 allow 确认确实被拒（权限面不是「加了就对」，要看拒绝路径）。
- 平台：desktop-only/mobile-only 插件在另一端构建通过（`cargo check --target aarch64-linux-android` / `tauri ios build`），capability `platforms` 切分正确（XP-03）。
- 集成面（notification/deep-link/autostart/updater/global-shortcut）用 `tauri build --debug` 产物逐平台冒烟，不拿 `tauri dev` 的行为当结论（XP-09）；updater 走一次完整 `check → downloadAndInstall → relaunch` 再发 `latest.json`（SH-10/12）。
