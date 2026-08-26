# /rust-skills:rust serde [target] — 序列化边界优化

目的：在 serde 位于外部输入、协议演进或已测性能热点时审查序列化边界。现行稳定线 **1.0.x**（crates.io serde 1.0.229 / serde_json 1.0.151）。仅有 serde 依赖、或 target 内 derive/调用面很少，都不等于无入站序列化风险；关联 API-01/04、SIMP-05、FFI-05、PERF-01。target 委托邻接 crate 做 peek/DTO（例如 `crates/proxy` 调用邻接 `RequestSpec::parse`）时：体检表必须含邻接行并标「邻接证据 · 不可写」，审委托边界；不要因本 crate derive 少就结案。

## SE 检查单（体检输出：位置｜编号｜问题｜修复）

**类型边界**

- SE-01 wire 类型与领域类型分离：serde derive 只挂 DTO/IPC 结构，领域类型经 `TryFrom` 换入换出——否则序列化格式变成隐式公共 API，改内部字段即破坏协议（API-04 精神）。
- SE-02 读取多场景零拷贝：`&str`/`Cow<'a, str>` + `#[serde(borrow)]`；大 payload 反序列化的 String 风暴是 SIMP-05 的 wire 版。
- SE-11 入站禁止 `serde_json::Value` / `HashMap<String, Value>` 当领域模型。无结构 = 校验散落在 if，非法状态可表示（API-01）。透传网关的白名单 peek 除外（同 SE-05 例外），并写进合同。

```rust
// ✗ SE-02 10MB JSON 全字段 String：一次反序列化几千次分配
#[derive(Deserialize)]
struct Event { id: String, kind: String, payload: String }

// ✓ 借用输入缓冲，零拷贝
#[derive(Deserialize)]
struct Event<'a> {
    id: &'a str,
    kind: &'a str,
    #[serde(borrow)] payload: Cow<'a, str>,
}
```

**表示与字段纪律**

- SE-03 enum 表示显式选：`untagged` 是线性试错（慢 + 报错信息差 + 可被恶意 payload 放大）——有判别字段就用 `tag`/adjacently tagged；untagged 仅限真无标签的历史格式并注明。
- SE-04 `#[serde(flatten)]` 走中间 buffer（分配 + 慢路径），热路径慎用；能平铺定义就平铺。
- SE-05 安全边界加 `deny_unknown_fields`（防参数走私）；出口用 `skip_serializing_if` 控 wire 面；`default` 只给真有默认语义的字段。**例外**：网关透传 peek（只抽白名单字段、其余原样转发）**禁止**对完整 body 加 `deny_unknown_fields`；须把白名单字段合同写进注释或 RUST.md，不要报成漏检。
- SE-06 兼容演进：加字段配 `default`；改名走 `alias` + 弃用期；破坏性变更升版本字段（信封层），禁悄改。
- SE-07 校验进类型：`deserialize_with`/newtype `TryFrom` 在反序列化时验证（范围/格式/长度），非法值根本构造不出来（FFI-05 同族）。
- SE-13 密钥/token 字段：响应 DTO `#[serde(skip_serializing)]`；请求 DTO 反序列化后立刻进 `SecretString`/零化，禁止 `Debug` 打全值（OBS-02）。
- SE-14 API 边界 `rename_all` 统一（JSON 常用 `camelCase`），Rust 字段保持 snake_case。禁止同一 DTO 字段级风格混用却无注释。

**性能、安全、错误**

- SE-08 大 JSON 热点先测再换：serde_json 1.0.151 多数够用；simd-json/sonic-rs 须 bench 证据（PERF-01）；超大文档用 `StreamDeserializer` / `RawValue` 延迟解析子树。
- SE-09 二进制通道（tauri IPC 旁路、缓存、进程间）选紧凑格式：postcard（嵌入友好）/ bincode / rmp——注明 schema 演进策略再上。
- SE-10 调试省命：深层字段报错用 `serde_path_to_error` 包一层，错误带完整路径。
- SE-12 外部 JSON 用 `from_slice`/`from_str` 默认递归上限。不要为「方便」换自定义 Deserializer 放开深度；无界嵌套是 DoS。
- SE-15 入站解析失败是 **400/协议错误**，不是 panic。禁 `serde_json::from_str(...).unwrap()` 在 handler/command 里（ERR-03）。axum 用 `Json<T>` 的 rejection；CLI 用 clap/thiserror 映射退出码。

```rust
// ✗ SE-11/15 无结构 + unwrap
let v: serde_json::Value = serde_json::from_str(&body).unwrap();
let id = v["id"].as_str().unwrap();

// ✓ DTO + TryFrom 领域类型；失败可映射
let dto: CreateUser = serde_json::from_slice(&body)?;
let user = User::try_from(dto)?;
```

## 验证

改动前后：payload 尺寸、反序列化耗时/分配数（dhat）、错误信息可读性抽查。协议兼容变更必须有新旧版本互读测试（TEST-08：期望值来自协议不是实现）。恶意嵌套/未知字段各一条契约测试即可，不堆 Value 套件。

## 输出

按 [SKILL 输出契约](../SKILL.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

只读调用：体检表分栏「主目标｜邻接证据」+ 候选（SE 编号 + 全局规则号）+ 兼容/性能验证方案；邻接行标注不可写。`--apply` 或明确“修/改/实现”时才落改动并给数据。协议演进债务只输出 RUST.md 候选，显式 `--record` 才写入。
