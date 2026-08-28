# 首轮提示（预期行为）

这些是给人和评测用的**最小可复制输入**。坏答案 = 失败。磁盘反例在 `tests/fixtures/`。证据级别 **E2 文案契约**，不是 E3 会话回放。

## 1. 编译器 E0382 → triage，不先 clone

```text
交易系统报 E0382：audit.push(record); ledger.push(record);
```

- 期望：HOW→WHY→WHAT；对照 `&` / `Arc` / `clone`；审计记录用 `Arc`（OWN-01）。
- 失败：直接 `record.clone()`，或不问业务角色。
- 场景 2。

## 2. 技术栈 → stack 出表，不写 Cargo.toml

```text
/rust-skills:rust stack 这是个 REST API 加一个运维 CLI
```

- 期望：分层表；HTTP axum 0.8.9、CLI clap 4.6.6；桌面 N-A；未改文件。
- 失败：axum+sea-orm+sqlx+Tauri 全家桶，或 `cargo add`。
- 场景 69。`--apply` 见场景 71（不删活栈）。

## 3. tracing 库里 init → obs

```text
/rust-skills:rust obs
```

- 期望：库禁 `init()`（TR-11）；WorkerGuard 活到退出（TR-12）；span 名静态（TR-14）。
- 失败：再装 env_logger，或把 URI 当 span 名。
- 场景 70。

## 4. 过期开发文件 → slim/hygiene，不用 cargo clean 加速

```text
开发文件一直增长，清理多余的过期开发文件
```

- 期望：四层表（target / CARGO_HOME / 未入库垃圾 / 入库孤儿）；拒绝 `rm -rf ~/.cargo`；`cargo clean` 不是加速（HY-03）。
- 失败：立刻清缓存并宣称更快，或把死函数当文件删。
- 场景 88。
