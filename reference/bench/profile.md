# 采集火焰图

目的：用与交付语义一致的 profiling profile 采到**带符号的** CPU 图。空栈或 `[unknown]` 占满宽度时停，不猜热点。构建慢不走这里 → `/rust-skills:rust slim`。

## 钉负载

必须有可复现命令：criterion bench、bin + 固定输入、或生产分布回放。玩具输入上的图作废（PERF-04）。脏工作区禁止 stash 造 before（场景 24）。

## profiling profile

与 release 同 opt-level / lto / codegen-units；只多符号与帧指针：

```toml
[profile.profiling]
inherits = "release"
debug = "line-tables-only"
[profile.profiling.build-override]
debug = false
```

```toml
# .cargo/config.toml 仅 profiling 目标使用，不要写进默认 rustflags
[target.'cfg(all())']
rustflags = ["-C", "force-frame-pointers=yes"]
```

debug 数据只定位，不能外推发布性能（PERF-01）。

## 采集命令

优先项目已有脚本。否则：

```sh
# 交互采样（推荐）：浏览器打开，宽条 = 时间
samply record -- cargo bench --bench <name> --profile profiling -- --bench
# 或
samply record -- cargo run --profile profiling --bin <bin> -- <args>

# 静态 svg
cargo flamegraph --profile profiling --bench <name>
```

堆分配用 dhat，不要用 CPU 图解释分配。

## Linux 权限（只打印，不执行）

`perf_event_paranoid` 过高会得到空栈。把下面命令交给用户，**等明确同意**再让用户自己跑。禁止 agent `sudo` / `setcap` / 改 sysctl。

```sh
# 用户知情后二选一
sudo sysctl kernel.perf_event_paranoid=1
sudo setcap cap_perfmon=ep "$(command -v samply)"
```

macOS：Instruments 或 samply；不要装 Linux perf。Windows：cargo-flamegraph + 对应记录器；空栈先查符号包。

## 中止条件

图里主宽条是 `[unknown]`、`[libc]` 无符号、或只有 `main`：先修 debuginfo / 帧指针 / 权限，再采第二次。禁止在无符号图上点名「热点函数」并改码。
