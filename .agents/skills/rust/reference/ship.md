# /rust-skills:rust ship [target] — 发布工程（双形态）

目的：按实际交付目标审查发布链路。service 不默认等于容器，desktop 也不默认等于三平台；从用户目标、现有产线、RUST.md facets 与依赖共同判定，冲突时报出而不猜。无 target 时：优先 facets 指向的主产物 crate（`artifact=service|desktop`）及其相关 CI/Dockerfile/conf；旁路 crate 默认排除并回显。

## 服务形态（SH-01..06）

- SH-01 多阶段构建：推荐模式之一是 cargo-chef 缓存依赖层；BuildKit cache mount / 分层 COPY 若已能复用依赖编译也算通过。运行层 distroless/cc 或 scratch+musl。镜像尺寸须有前后基线（`docker images`），阈值由项目自定——无基线只标缺口，不因未达某固定 MB 判阻断。
- SH-02 静态化取舍写明理由：musl 静态单文件最简，但 musl 分配器在高并发下有性能差异——延迟敏感服务选 gnu + distroless，或换 mimalloc 后实测（META-02）。
- SH-03 运行层纪律：非 root 用户、只读 rootfs（有编排/compose 时才强求）、`/healthz` 探针端点独立于业务路由（liveness 不查下游依赖，readiness 才查）。
- SH-04 停机对接：SIGTERM → AX-06 优雅停机 → drain 宽限对齐编排器 `terminationGracePeriodSeconds`（无 k8s 时用文档/compose 注释对齐即可）；三者对不齐 = 滚动更新易丢请求。
- SH-05 配置分层：环境变量优先，typed config 启动校验；secrets 不进镜像、不进日志（OBS-02）、不进 git——注入走运行时。fail-fast vs warn：`maturity=production` 或用户点名生产时，空密钥/弱密钥应硬失败；prototype/dev 路径允许 warn，但须在报告中标明「可带病启动」。
- SH-06 CI 产线：沿用项目已有入口（xtask/make/脚本）；若已定义 `[profile.ci]` 则建议 CI 显式 `--profile ci`（BUILD-05），未接线标改进而非虚构新工具链。rust-cache/sccache 按现状。镜像漏洞扫描 trivy、crate 层 cargo-deny 均为 [MAY]——勿假设仓库已有，缺了只列候选（DEP-06）。

## 桌面形态（SH-07..15）

构建产物矩阵、sidecar 命名、updater 插件接线等开发侧前置见 [tauri/develop.md](tauri/develop.md) 与 [tauri/plugins.md](tauri/plugins.md)；本节只管发布链。

- SH-07 三平台矩阵用官方 tauri-action（GitHub pipelines）；产物命名含版本 + 目标三元组；PR 构建不签名、tag 构建才走发布签名。
- SH-08 Windows 签名：证书/Azure Trusted Signing 凭据只存 CI secret，禁本地手签发布物（不可审计）。
- SH-09 macOS 双步缺一不可：签名 + **notarization**（无公证 = 用户见「恶意软件」弹窗）；entitlements 最小化申请。
- SH-10 updater 闭环：updater 插件 + minisign 签名密钥 + `latest.json` 端点；**私钥离线保管**、公钥进 tauri.conf；每次发布先本地验证完整更新链路再推生产 latest.json。
- SH-11 版本单源：tag 驱动发布；Cargo.toml / tauri.conf / CHANGELOG 版本一致性做成 xtask 检查（→ `/rust-skills:rust gate`）。
- SH-12 回滚预案先于发布存在：服务 = 镜像 tag 回退（无 registry 时 compose/文档中的回退步骤亦可）；桌面 = updater 可发紧急版本覆盖；冒烟清单跑完才更新 latest.json。
- SH-13 macOS DMG：create-dmg 调 Finder AppleScript 摆图标。无 GUI / agent 会话里 `osascript` 报「访达正忙」(-15260)，bundler 把脚本输出藏在 debug，表面只剩 `failed to run bundle_dmg.sh`。CI/无头打包必须 `CI=true`（bundler 加 `--skip-jenkins`）。scratch 放本机 `/tmp`，不要放外置卷（TA-46）。
- SH-14 在 macOS 上交叉出 Windows NSIS（cargo-xwin）是备用链，**不是**签名发布物：只能 NSIS（WiX/MSI 必须在 Windows 上做）；产物未 Authenticode，须 `signing = none` 并在真机至少跑一遍安装→本地 IO→一次 TLS。`brew install llvm` 不够——新 formula 不含 `lld-link`，要另装 `lld`；`nasm` 给 ring。`makensis` 在 `LANG`/`LC_ALL` 为空或 `C` 时编 Unicode 脚本会 `std::bad_alloc`（NSIS #1165），命令必须带 UTF-8 locale。首轮会拉 MSVC CRT+SDK 到 `~/Library/Caches/cargo-xwin`。交叉包与真机包语义大致等价（C 依赖的 CRT helper 名可能不同），交给用户前必须 Windows 实测。
- SH-15 GUI 父进程不得 spawn 未设 `CREATE_NO_WINDOW` 的 console-subsystem 工具（XP-07）；`windows_subsystem = "windows"` 的**自身**子进程继承管道不闪窗（TA-43）。`webviewInstallMode: downloadBootstrapper` 离线机会失败，改 `embedBootstrapper`/`offlineInstaller`。NSIS `currentUser` 免管理员。macOS 直接分发 + 回环服务 + 用户自选文件时：`hardenedRuntime: true` 只开 WebKit 需要的 `allow-jit`，**不要**开 App Sandbox（沙盒会掐回环与任意路径）。

```dockerfile
# ✓ SH-01 骨架示例（chef 非唯一合法形态）
FROM lukemathwalker/cargo-chef:latest-rust-1 AS chef
WORKDIR /app
FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json
FROM chef AS builder
COPY --from=planner /app/recipe.json recipe.json
RUN cargo chef cook --release --recipe-path recipe.json
COPY . .
RUN cargo build --release --bin server
FROM gcr.io/distroless/cc-debian12
COPY --from=builder /app/target/release/server /server
USER nonroot
ENTRYPOINT ["/server"]
```

## 验证

服务：镜像尺寸前后基线、滚动更新错误率、探针行为；桌面：三平台安装冒烟、更新链路端到端、签名校验证据。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

只读调用：产线检查表（SH 编号，分栏主目标｜邻接证据）+ 候选 diff + 验证方案。`--apply` 或明确“修/改/实现”时才修改 CI/Dockerfile/conf 并给验证证据。发布债务只输出 RUST.md 候选，显式 `--record` 才写入。
