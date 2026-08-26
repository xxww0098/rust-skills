# /rust-skills:rust xplat [target] — 声明平台的一致性

目的：只对用户支持的平台审查可移植性，并用结构、对应平台验证和差异记录降低风险。Tauri 不自动意味着三端支持；先从发布目标和 CI 证明平台集合。

**facet 门控**：`artifact=service` → 跳过 XP-01/09–11；无 Windows 证据与用户反馈 → 跳过 XP-06 与「必须 Windows 实测」。Linux-only 服务只核 XP-03（声明↔CI）与已触达的 XP-02/04–08。

## 第一 bug 源：三个 webview 引擎（XP-01 · desktop）

| 平台 | 引擎 | 内核 | 特点 |
|---|---|---|---|
| macOS | WKWebView | WebKit/Safari | 你开发时看到的 |
| Windows | WebView2 | Chromium | 用户最多的 |
| Linux | WebKitGTK | WebKit（滞后版本） | 特性最老，最先炸 |

- XP-01 前端按**支持引擎交集**开发：特性检测（`if ('x' in obj)`）优先于 UA 嗅探；新 CSS 按支持矩阵带兜底；browserslist 记录实际引擎版本。

## 结构纪律

- XP-02 平台代码集中到少量具名模块，公共代码只见稳定接口；只有多实现确需替换时才引入 trait。简单局部 `#[cfg]` 可保留，重复分支再收口。
- XP-03 每个声明支持的平台都编译测试；宿主机 `cargo check` 不会类型检查未命中的 `#[cfg]` 分支，优先复用项目已有跨 target 入口，否则对声明目标逐个 `cargo check --target <triple>`。CI 矩阵覆盖实际发布集合，不自动增加产品不支持的 OS；缺交叉工具链/系统库时把「未编译该分支」列为缺口，不能拿宿主机绿色代替。仅 Linux 服务 → 单 OS（如 `ubuntu-latest`）即合规；三端矩阵仅当产品声明三端。

```yaml
# ✓ XP-03 仅 Linux 服务
runs-on: ubuntu-latest
# ✓ XP-03 声明三端时才用矩阵
# strategy.matrix.os: [ubuntu-latest, macos-latest, windows-latest]
```

## 通用 Rust 差异（服务端同样适用）

- XP-04 路径：`PathBuf::join` 禁手拼 `/`；tauri 项目一律用 path API，禁硬编码 `~/Library`/`AppData`。**Windows 两套 data 根（TA-40）**：`app.path().app_data_dir()` = `{FOLDERID_RoamingAppData}/{identifier}`（`%APPDATA%`），`app_local_data_dir()` = `{FOLDERID_LocalAppData}/{identifier}`（`%LOCALAPPDATA%`）；macOS 二者同为 `~/Library/Application Support/{identifier}`，Linux 同为 `$XDG_DATA_HOME`/`~/.local/share`。拿得到 `AppHandle` 就调 API；拿不到时手拼必须与所用 API **同一环境变量**。把控制根/锁文件拼到 `LOCALAPPDATA`、SQLite 落到 `app_data_dir()` = 两套根，跨进程互斥失效。缓存用 `app_cache_dir()`（mac `~/Library/Caches`、Win LocalAppData、Linux `~/.cache`）。**大小写**——mac 默认不敏感、Linux 敏感，mac 上跑通的 `Assets/logo.PNG` 在 Linux 404 → 资源文件名全小写策略；Windows 保留名（CON/NUL/aux）与 260 字符长路径要防。
- XP-05 `OsString`/`Path` 端到端：禁 `to_string_lossy()` 后再当路径用。Windows 上 `std`/`tokio` 的 `canonicalize` 会给出 `\\?\` 字面路径，写进配置/prompt/相等键会坏——用 `dunce::canonicalize`（或项目等价封装）。clippy `disallowed-methods` 可挡裸 canonicalize。
- XP-06 文件语义（**Windows 证据触发**）：Windows 能否删/改名取决于所有打开句柄的共享模式；Rust 标准库 `File::open` 默认允许 delete sharing，但第三方库或其他进程可能用不含 `FILE_SHARE_DELETE` 的方式打开，导致 `Access denied`。审计所有相关句柄；写入优先 tempfile + 原子 persist，遇占用时给有界重试或明确错误。**原子 rename（TA-45）**：`rename` 只在同卷有效，跨卷报 `EXDEV`（不会退化成拷贝）——临时文件必须 stage 在目标旁边，不要写到 `/tmp` 再搬到 data 根。Windows **不能 rename 覆盖已存在文件/目录**：先 `remove_file`/`remove_dir` 或 move-aside 再 rename。源目录只读（光盘、网络盘、iCloud）时对「同目录兄弟缓存」保持静默降级，不要把 `is_ok()` 吞错改成硬失败。文件监听（notify）三端事件次数/合并语义不同 → 消费端去抖 + 幂等。无 Windows 目标/反馈时标 N-A。
- XP-07 进程：`Command` 不过 shell（别拼 shell 字符串）；Windows spawn 加 `CREATE_NO_WINDOW`（否则弹黑框）；tauri sidecar 按 target triple 命名交给框架选；Unix 信号 Windows 不存在 → 停机路径双实现（ctrl_c 跨端 + terminate 分平台）。
- XP-08 文本：处理外部文本容忍 CRLF；仓库 `.gitattributes` 固定 LF；二进制显式 `read`/`write`，不走文本模式假设。

```rust
// ✗ XP-06 Windows：该句柄显式禁止 delete sharing
#[cfg(windows)]
use std::os::windows::fs::OpenOptionsExt;
#[cfg(windows)]
let f = OpenOptions::new().read(true).share_mode(0).open(&path)?;
let data = read_all(&f)?;
fs::rename(&path, &backup)?;      // 句柄还活着，Windows 拒绝

// ✓ 释放限制性句柄；原子替换仍须处理外部进程占用
drop(f);
let tmp = NamedTempFile::new_in(parent)?;
tmp.write_all(&new_data)?;
tmp.persist(&path)?;
```

## tauri 集成面（XP-09..11 · desktop-only）

- XP-09 窗口/系统集成逐平台验收：装饰/透明/振动效果、托盘、菜单（mac 全局菜单 vs Windows 窗口菜单）、DPI 缩放、深链注册、开机自启——各有平台脾气，冒烟清单按平台各跑一遍，不假设 mac 行为是默认语义。
- XP-10 平台专属依赖进 `[target.'cfg(windows)'.dependencies]`；行为随平台变的三方 crate（notify、keyring、窗口特效类）在 RUST.md 账本登记差异。
- XP-11 前端时区/locale 显式处理（`Intl` 明确传 locale），数字日期格式不吃系统默认。

## 账本（规范化的落点）

- XP-12 RUST.md 增设「平台差异账本」节：每修一个平台 bug → 输出差异账本候选 + `/rust-skills:rust capture` 写项目 outbox。只有显式 `--record` 才直接写 RUST.md。

## 验证

声明支持的平台 CI 全绿是合并门（XP-03）；desktop 集成面变更附对应平台冒烟记录。文件/路径类 **Windows** 修复必须在 Windows 实测；Linux-only 服务不要求。

## 输出

按 [SKILL 输出契约](../SKILL.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

只读调用：体检表（位置｜XP 编号｜问题｜修复）+ 结构/CI 候选 + 账本候选。`--apply` 或明确“修/改/实现”时才落结构与 CI diff；只有显式 `--record` 才更新 RUST.md 账本。
