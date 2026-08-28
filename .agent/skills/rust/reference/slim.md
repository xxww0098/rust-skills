# /rust-skills:rust slim [target] — 构建减肥

目的：用数据把构建时间打下来。铁律：**无 `--timings` 不动手**（BUILD-04/META-02）；冷构建与热增量分开诊治（BUILD-03）。无 timings 时本命令为**只读搭基线**；有数据且 `--apply` 或用户授权改动后才写 profile/依赖。

## 步骤

1. **盘点 prior art**：先列出已有 `[profile.*]` / package override / build-override / CI profile；新开方必须有**新的** timings，不得凭旧注释复开。
2. **基线**：热增量在当前 target 运行；冷构建使用独立临时 `CARGO_TARGET_DIR`，不得删除或 sweep 用户共享缓存。各跑 `cargo build --timings`（有则再 `cargo report timings`）；再跑 `cargo tree -d`，记录总时长与关键路径。无长构建授权时：只输出可粘贴命令 + 标「基线未跑」缺口，仍拒改码。
3. **读图**：串行长尾（时间轴末端独占的 crate）→ 它是拆分/砍入边候选；rmeta 等待空洞 → 依赖链过深（WS-08）；巨块 → 单 crate 过大（WS-11）。
4. **按收益排序开方**（每项给预期收益依据；顺序对齐 BUILD-10 / 2025 调查）：
   - 依赖裁剪：重复版本、未用 default-features、重 proc-macro（serde derive / 重 codegen）的轻量替代（DEP-02/03）
   - debuginfo：dev 用 `line-tables-only`（BUILD-08）
   - 链接器：x86_64 Linux ≥1.90 已默认 rust-lld，勿再抄旧 `rustflags = ["-C", "link-arg=-fuse-ld=lld"]`。mold/wild 只在本机实测优于默认时加（BUILD-06）
   - rust-analyzer 与 `cargo` 互相卡住 → RA 单独 target dir（BUILD-09），不是 slim 的改码项
   - 结构：只有 timings 显示重编译边界且模块有清晰所有权时才拆 crate；Feldera「1000 crate」是代码生成特例，不是模板（WS-08/12）
   - profile：package override 与 build-override 分别度量；点名 O3 热依赖（**禁**通配，BUILD-01）
   - 实验项标 MAY：`-Zhint-mostly-unused` 等，不默认打开
5. **执行与复测**：一次一类改动，改完复跑 timings（Cargo ≥1.93 可用 `cargo report timings` 看历史）。无提升则回滚。

无 target /「编译太慢」类诉求：先问一次扫描范围是 workspace 主产物还是当前改动集（用户已点名除外）。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

- **无 timings**：拒动手 + 显式拒 BUILD-01 通配 + 可粘贴基线命令 + 已排除旁路。
- **有数据后**：前后对比表（冷/热/关键路径）+ 已做改动（规则号）+ 未做候选；默认 RUST.md 债务候选，`--record` 才写入。
