# /rust-skills:rust slim [target] — 构建减肥

目的：用数据把构建时间打下来。铁律：**无 `--timings` 不动手**（BUILD-04/META-02）；冷构建与热增量分开诊治（BUILD-03）。无 timings 时本命令为**只读搭基线**；有数据且 `--apply` 或用户授权改动后才写 profile/依赖。

## 两个显式快捷入口

`slim` 仍是统一 owner；下面两个 pin 只缩短入口，不复制规则、不扩大隐式路由：

- `/cargo [target]` → [Cargo 最短反馈回路](slim/cargo.md)：深读 workspace、target、feature、profile、build.rs、缓存与 CI 命令，把“编辑 → 可编译/可链接”压到最短。
- `/test [target]` → [最小充分测试](slim/test.md)：深读改动面、测试目标和不变量，只编译并运行足以证明本次改动的测试，合并重复证明。

同一请求同时涉及 build 与 test 时，本轮只消费一份 ProjectSnapshot：先由 `/cargo` 固定 toolchain/target/profile/features/target-dir 指纹，再由 `/test` 在同一指纹上选最小证明集。禁止两个 playbook 各跑一遍 metadata、各画一遍 crate 图或切换 target dir 造成伪冷构建。

## 步骤

1. **盘点 prior art**：先列出已有 `[profile.*]` / package override / build-override / CI profile；新开方必须有**新的** timings，不得凭旧注释复开。
2. **基线**：热增量在当前 target 运行；冷构建使用独立临时 `CARGO_TARGET_DIR`，不得删除或 sweep 用户共享缓存。各跑 `cargo build --timings`（若项目实际慢命令是 check/test，就测那条原命令）；再跑 `cargo tree -d`，记录总时长与关键路径。`cargo report timings/rebuilds` 仅在项目已使用 nightly `-Zbuild-analysis` 时作为补充，不得写成 stable 能力。无长构建授权时：只输出可粘贴命令 + 标「基线未跑」缺口，仍拒改码。
3. **读图**：串行长尾（时间轴末端独占的 crate）→ 它是拆分/砍入边候选；rmeta 等待空洞 → 依赖链过深（WS-08）；巨块 → 单 crate 过大（WS-11）；反复出现的 custom-build → 检查 build.rs 的 rerun 边界。
4. **按收益排序开方**（每项给预期收益依据；顺序对齐 BUILD-10）：
   - 先减命令范围与重复工作：package / target / features / profile 只选当前证明所需；本地默认不跑 `--workspace --all-targets --all-features`
   - 依赖裁剪：重复版本、未用 default-features、重 proc-macro（serde derive / 重 codegen）的轻量替代（DEP-02/03）
   - debuginfo：dev 用 `line-tables-only`（BUILD-08）
   - 链接器：按平台实测；勿照抄旧的全仓 linker rustflags（BUILD-06）
   - rust-analyzer 与 `cargo` 互相卡住 → RA 单独 target dir（BUILD-09），不是常规缓存优化
   - 结构：只有 timings 显示重编译边界且模块有清晰所有权时才拆 crate；代码生成型“千 crate”不是模板（WS-08/12）
   - profile：package override 与 build-override 分别度量；点名热依赖（**禁**通配，BUILD-01/02）
   - 实验项标 MAY：nightly build-analysis、section timings 等不得变成默认项目要求
5. **执行与复测**：一次只改一类，复跑完全相同的命令指纹。无提升就回滚；不能把冷缓存、不同 features 或不同 target triple 当成前后对比。

无 target /「编译太慢」类诉求：从 ProjectSnapshot 的 workspace default-members 与当前改动包推导最可能主产物；只有出现两个同等主路径且代价差异巨大时才问一次，禁止先跑整仓。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

- **无 timings**：拒动手 + 显式拒 BUILD-01 通配 + 可粘贴基线命令 + 已排除旁路。
- **有数据后**：前后对比表（命令指纹 / 冷 / 热 / 关键路径 / 编译单元）+ 已做改动（规则号）+ 未做候选；默认 RUST.md 债务候选，`--record` 才写入。
- **同时走 cargo/test**：额外给“避免的重复工作”一栏，列出未再执行的 workspace、target、feature 或测试二进制。
