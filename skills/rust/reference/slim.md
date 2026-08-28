# /rust-skills:rust slim [target] — 构建减肥

目的：用数据把构建时间和 Rust 开发反馈成本打下来。构建性能铁律：**无 `--timings` 不改性能配置**（BUILD-04/META-02）；冷构建与热增量分开诊治（BUILD-03）。`/cargo tools` 可以按仓库事实做工具盘点、命令去重、版本/安装源归一和孤儿配置清理，但只要声称“更快”仍必须给同指纹前后基线。

编排：多文件时按 [kernel/swarm.md](../kernel/swarm.md) — 三条 pin 即三条车道：cargo 指纹 · test 证明集 · tooling owner。禁止各跑一遍 metadata。`--timings` 与复测必须串行、同一 target-dir。 单文件或已有快照则跳过。

## 显式快捷入口与 Cargo 子模式

`slim` 仍是统一 owner；下面的 pin/子模式只缩短入口，不复制规则、不扩大隐式路由：

- `/cargo [target]` → [Cargo 最短反馈回路](slim/cargo.md)：深读 workspace、target、feature、profile、build.rs、缓存与 CI 命令，把“编辑 → 可编译/可链接”压到最短。
- `/cargo tools [target]` → [Rust 开发体验工具带](slim/tooling.md)：审查 rustup/rust-analyzer、watch/test/coverage/依赖治理工具、安装版本和任务入口，一个信号只保留一个 owner。
- `/test [target]` → [最小充分测试](slim/test.md)：深读改动面、测试目标和不变量，只编译并运行足以证明本次改动的测试，合并重复证明。

同一请求同时涉及 build、tools 与 test 时，本轮只消费一份 ProjectSnapshot：`/cargo` 固定 toolchain/target/profile/features/target-dir 指纹，`/cargo tools` 对齐编辑器/终端/CI 与该指纹，`/test` 在同一图上选最小证明集。禁止各 playbook 各跑一遍 metadata、各画一遍 crate 图、各维护一套 features，或切换 target dir 造成伪冷构建。

## 步骤

0. **先分诉求**：构建慢/链接慢/重编译 → `slim/cargo.md`；工具太多、IDE/终端重复、装工具慢、新人难启动 → `slim/tooling.md`；测试慢/重复跑 → `slim/test.md`。同一根因只由一个 owner 报告。
1. **盘点 prior art**：先列出已有 `[profile.*]` / package override / build-override / CI profile、rust-toolchain、Cargo aliases、任务系统和外部工具；新开方必须有新的证据，不得凭旧注释或流行模板复开。
2. **基线**：热增量在当前 target 运行；冷构建使用独立临时 `CARGO_TARGET_DIR`，不得删除或 sweep 用户共享缓存。对真实慢命令加 `--timings`；再跑 `cargo tree -d`，记录总时长与关键路径。`cargo report sessions/rebuilds/timings` 仅在项目已使用 nightly `-Zbuild-analysis` 时作为补充，不得写成 stable 能力。DX 额外记录 fresh-clone bootstrap、保存触发的 Cargo 次数、聚焦验证墙钟、必装工具数与 CI 重复安装次数。
3. **读图/读 fan-out**：串行长尾 → 拆分/砍入边候选；rmeta 等待空洞 → 依赖链过深（WS-08）；巨块 → 单 crate 过大（WS-11）；反复 custom-build → build.rs rerun 边界；保存一次启动多个同指纹 Cargo → 先删重复 owner。
4. **按收益排序开方**（每项给预期收益依据；顺序对齐 BUILD-10）：
   - 先减命令范围与重复工作：package / target / features / profile 只选当前证明所需；本地默认不跑 `--workspace --all-targets --all-features`
   - 工具/入口去重：rust-analyzer、Bacon/watcher、cargo test/nextest、deny/audit、machete/udeps、任务 runner 各自只有一个 owner
   - 依赖裁剪：重复版本、未用 default-features、重 proc-macro（serde derive / 重 codegen）的轻量替代（DEP-02/03）
   - debuginfo：dev 用 `line-tables-only`（BUILD-08）
   - 链接器：按平台实测；勿照抄旧的全仓 linker rustflags（BUILD-06）
   - rust-analyzer 与 `cargo` 确认互相卡住 → RA 单独 target dir（BUILD-09），不是常规缓存优化
   - 结构：只有 timings 显示重编译边界且模块有清晰所有权时才拆 crate；代码生成型“千 crate”不是模板（WS-08/12）
   - profile：package override 与 build-override 分别度量；点名热依赖（**禁**通配，BUILD-01/02）
   - 实验项标 MAY：nightly build-analysis、section timings、远端缓存等不得变成默认项目要求
5. **执行与复测**：一次只改一类，复跑完全相同的命令指纹或 DX 观察项。无提升就回滚；不能把冷缓存、不同 features/target triple、少跑测试或换安装源当成同口径收益。

无 target /“编译太慢”类诉求：从 ProjectSnapshot 的 workspace default-members 与当前改动包推导最可能主产物；只有出现两个同等主路径且代价差异巨大时才问一次，禁止先跑整仓。无 target /“开发体验差”类诉求：先体检权威 bootstrap、编辑环和提交前入口，不先推荐工具名单。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

- **构建无 timings**：拒改性能配置 + 显式拒 BUILD-01 通配 + 可粘贴基线命令 + 已排除旁路。
- **有构建数据后**：前后对比表（命令指纹 / 冷 / 热 / 关键路径 / 编译单元）+ 已做改动（规则号）+ 未做候选；默认 RUST.md 债务候选，`--record` 才写入。
- **开发体验**：输出“信号 → owner → 车道 → 安装/配置 → 去掉的重复”表；不宣称速度时明确标注只改善可发现性、一致性或失败诊断。
- **同时走 cargo/tools/test**：额外给“避免的重复工作”一栏，列出未再执行的 workspace、target、feature、测试二进制、watcher、安装步骤或同义门禁。
