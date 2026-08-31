# axum/extractors — 提取器：内置、自定义、拒绝响应与校验

目的：handler 签名里出现 `Path`/`Query`/`Json`/`Form`/`Option<Extractor>`、`impl FromRequest(Parts)`、`*Rejection`、`validator`/`garde` 证据，或用户问「为什么报 Handler is not satisfied / 为什么返回纯文本 400 / Option 升 0.8 后开始 4xx / 校验放哪」时加载。只讲「如何把请求安全地变成类型」：状态模型按 [../axum.md](../axum.md) 的 AX-01/AX-02，鉴权 extractor 的 token/session 策略按 AX-15，错误 enum 总体设计按 AX-12——本文只给它们在 extractor 层的接缝。API 对 axum 0.7/0.8 基本相同，差异处并排标注。

## 内置 extractor 与顺序

1. 两类 trait：`FromRequestParts`（method/uri/headers/extensions/path 捕获，不碰 body，任意位置任意个数）与 `FromRequest`（消费 body）。消费 body 的只能有一个且必须是最后一个参数（AX-13）；违者报 `Handler<_, _> is not satisfied`，先加 `#[axum::debug_handler]`（`macros` feature）看真实原因，不要盲改。
2. 非 extractor 类型（`bool`、领域 struct）不能直接做参数：从提取值里算，或写成自定义 extractor。
3. `State<T>` 要求 `T: FromRef<S>`，编译期检查；`State<Pool>` 直接拿子状态，不必 `State<AppState>` 再 `.pool.clone()`。`Extension<T>` 缺失是运行时 500，只放中间件注入的每请求数据（AX-01）。
4. `Query<T>`：`serde_urlencoded` 不支持重复键 `?tag=a&tag=b` → `Vec<T>`，需要时换 `axum_extra::extract::Query`（feature `query`）；可选参数写 `Option<T>`/`#[serde(default)]`；`#[serde(flatten)]` 下的数字字段在 query/form 里解析失败，不要 flatten。
5. `Form<T>`：GET/HEAD 读 query string，其它方法读 body 且要求 `application/x-www-form-urlencoded`。
6. 单个类型化 header 用 `axum_extra::TypedHeader<H>` + `axum_extra::headers`（feature `typed-header`）；`axum::TypedHeader` 自 0.7 起不存在。全部 header 用 `HeaderMap`。
7. `Request`（= `http::Request<axum::body::Body>`）拿整个请求，同样算 body extractor；要「先读 parts 再消费 body」用 `axum::RequestExt`：`req.extract_parts::<T>().await` 之后再 `Json::<T>::from_request(req, &())`。
8. `Path<T>` 四种形状：单值、元组（按捕获顺序）、具名 struct（字段名 = 捕获名）、`HashMap<String, String>`。百分号编码自动解码；`Uuid` 需 `uuid` 的 `serde` feature。路径语法 0.8 是 `{id}`（AX-18）。

```rust
// ✓ parts 在前，唯一的 body extractor 在最后
async fn create(
    State(app): State<Arc<App>>,
    Path(team): Path<Uuid>,
    Query(page): Query<Page>,
    headers: HeaderMap,
    Json(body): Json<CreateUser>,      // FromRequest：最后
) -> Result<StatusCode, ApiError> { /* … */ }

// ✗ 两个 body / body 不在最后：不编译，错误信息不会告诉你是顺序问题
async fn bad(body: String, Json(j): Json<Value>) {}
```

## 默认 rejection 一览（AX-20）

| extractor | 默认状态码 | 默认 body（`text/plain`） | 如何定制 |
|---|---|---|---|
| `Json<T>` | 415 缺/错 `Content-Type`；400 JSON 语法错；422 形状不符；413 超 `DefaultBodyLimit` | `Failed to deserialize the JSON body into the target type: missing field …` | `JsonRejection` → 下节三档 |
| `Form<T>` | 415 / 400 / 422 / 413，同上 | `Failed to deserialize form body: …` | `FormRejection` |
| `Path<T>` | 400 客户端值解析失败；**500** 捕获个数与 `T` 不符、`T` 类型不支持、路由无捕获（路由 bug） | `Invalid URL: Cannot parse "abc" to a u64` | `PathRejection` |
| `Query<T>` | 400 | `Failed to deserialize query string: …` | `QueryRejection` |
| `Bytes` / `String` | 413 超限；400 读 body 失败 / 非法 UTF8 | `Failed to buffer the request body: length limit exceeded` | `BytesRejection` / `StringRejection` |
| `Extension<T>` | 500 | `Missing request extension: …` | `ExtensionRejection` |
| `TypedHeader<H>`（axum-extra） | 400 缺头或解析失败 | `Header of type "authorization" was missing` | `TypedHeaderRejection` |
| `State` / `HeaderMap` / `Method` / `Uri` / `Request` | 不失败（`Infallible`） | — | — |

- 所有 rejection enum 都 `#[non_exhaustive]`：`match` 必须留 `rej => (rej.status(), rej.body_text())` 兜底。禁止把所有分支硬编码成 400——415/422 语义被抹平，客户端分不清「JSON 坏了」和「字段不对」。
- `status()`/`body_text()` 是权威来源；`Error::source()` 可下钻到 `serde_json::Error`，一般不需要。
- 默认 body 是纯文本且带 serde 细节。对外 JSON API 统一换成 JSON 错误信封（下节）；`PathRejection`/`ExtensionRejection` 的 500 分支只记日志不回显（AX-12）。

## 定制 rejection：按覆盖范围选三档（AX-20）

| 范围 | 手段 | 备注 |
|---|---|---|
| 1–2 个 handler | 参数写 `Result<Json<T>, JsonRejection>` 自己 match | 超过两处就停止复制 match |
| 全仓统一 | `#[derive(FromRequest)]` + `#[from_request(via(axum::Json), rejection(ApiError))]` 做同名 newtype，`use crate::extract::{Json, Path, Query}` 遮蔽 axum 的 | 需 axum `macros` feature；`ApiError: IntoResponse + From<每个 via 的 Rejection>`，少一个 `From` 不编译 |
| 不想定义 newtype | `axum_extra::extract::WithRejection<Json<T>, ApiError>`（feature `with-rejection`） | 第二个字段是 `PhantomData`，用 `_` 丢弃 |

```rust
// ✓ 一个 ApiError 吃掉所有 rejection + 校验错；handler 返回 Result<_, ApiError>
use axum::extract::rejection::{JsonRejection, PathRejection};
use axum::{http::StatusCode, response::{IntoResponse, Response}};

#[derive(Debug, thiserror::Error)]
pub enum ApiError {
    #[error(transparent)] Json(#[from] JsonRejection),
    #[error(transparent)] Path(#[from] PathRejection),   // Query/Form 同理各加一个变体
    #[error("validation failed")] Validation(#[from] validator::ValidationErrors),
    // … 领域错误变体（AX-12）
}

fn envelope(status: StatusCode, code: &str, text: String) -> Response {
    // 5xx 来自路由/类型 bug：记日志，不把 serde 细节回给客户端
    let message = if status.is_server_error() { tracing::error!(%text, "extractor 5xx"); "internal error".to_owned() } else { text };
    (status, axum::Json(serde_json::json!({ "code": code, "message": message }))).into_response()
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        match self {
            Self::Json(r) => envelope(r.status(), "bad_json", r.body_text()),
            Self::Path(r) => envelope(r.status(), "bad_path", r.body_text()),
            // 只回字段名 + code；直接 Json(e) 会在 params.value 回显原值（密码字段泄到响应和日志）
            Self::Validation(e) => {
                let fields: BTreeMap<String, Vec<String>> = e.field_errors().into_iter()
                    .map(|(f, errs)| (f.to_string(), errs.iter().map(|e| e.code.to_string()).collect())).collect();
                (StatusCode::UNPROCESSABLE_ENTITY, axum::Json(serde_json::json!({ "code": "validation", "fields": fields }))).into_response()
            }
        }
    }
}

// crate::extract —— 同名遮蔽，handler 里 `use crate::extract::{Json, Path}` 即可
#[derive(axum::extract::FromRequest)]
#[from_request(via(axum::Json), rejection(ApiError))]
pub struct Json<T>(pub T);

#[derive(axum::extract::FromRequestParts)]
#[from_request(via(axum::extract::Path), rejection(ApiError))]
pub struct Path<T>(pub T);
```

## `Option<T>`：0.8 语义变化（AX-19）

1. 0.7：`Option<T>` 对任意 extractor 可用，且吞掉一切错误——`/abc` 打到 `Option<Path<u32>>` 得到 `None`。
2. 0.8：`Option<T>` 要求 `T: OptionalFromRequestParts`/`OptionalFromRequest`，语义是「缺席 → `None`，在场但坏 → rejection」。已实现的内置：`Path`（路由无该捕获）、`Query`（无 query string）、`Extension`、`Json`（无 `Content-Type` 头 → `None`，有头非 JSON → 415；0.8.x 补丁版起）、axum-extra 0.10 `TypedHeader`（缺头）。没有实现的类型——`Form`/`Bytes`/`String`/`HeaderMap`/**你的自定义 extractor**——写 `Option<T>` 直接不编译。
3. 要「任何失败都当缺席」：`Result<T, T::Rejection>` 然后 `.ok()`，显式承认吞错。要让自定义 extractor 支持 `Option`：另实现 `OptionalFromRequestParts`（与 `FromRequestParts` 共存，两者之间没有 blanket 桥接）。
4. axum-extra 的 `OptionalPath`/`OptionalQuery` 是 0.7 时代同一语义的替代；0.8 里 `Option<Path<T>>`/`Option<Query<T>>` 已覆盖，新代码不必引入。
5. 0.7 → 0.8 升级必须逐个审计 `Option<Extractor>` 参数：原来兜底的 `None` 分支现在对坏输入返回 4xx，测试不覆盖就静默变更行为。

```rust
async fn show(id: Option<Path<u32>>) {}  // axum 0.7：/abc → None ｜ axum 0.8：/abc → 400，只有路由没有 {id} 才 None
// axum 0.8：恢复「任何失败都当缺席」要写明
async fn show(id: Result<Path<u32>, PathRejection>) { let id = id.ok().map(|Path(id)| id); }

// axum 0.8：让自定义 extractor 支持 Option<AuthUser>（可选登录的路由）
impl<S: Send + Sync> OptionalFromRequestParts<S> for AuthUser {
    type Rejection = ApiError;
    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Option<Self>, ApiError> {
        if parts.headers.get(AUTHORIZATION).is_none() { return Ok(None); }          // 缺席
        <Self as FromRequestParts<S>>::from_request_parts(parts, state).await.map(Some) // 在场但坏 → 401
    }
}
```

## 自定义 extractor（AX-21）

1. 选 trait 只问一件事：读不读 body。不读 → `FromRequestParts`（任意位置）；读 → `FromRequest`（最后）。禁止给同一具体类型同时实现两者：blanket `impl FromRequest<S, ViaParts> for T where T: FromRequestParts<S>` 已经桥接，再手写 `FromRequest<S>` 会让 marker `M` 无法推断，该类型作为参数直接失效。泛型包装器（如 `WithRejection<E, R>`）是唯一例外。
2. 0.7 impl 上必须 `#[async_trait]`；0.8 是原生 `async fn`，留着 `#[async_trait]` 会签名不匹配（`Pin<Box<dyn Future>>` ≠ `impl Future + Send`）。迁移 = 删属性 + 删 `async-trait` 依赖，函数体一字不动。
3. `Rejection` 必须 `IntoResponse`。优先直接用项目的 `ApiError`，不要每个 extractor 各来一种 `(StatusCode, &'static str)`，否则错误信封在 extractor 层就碎了。
4. 在 extractor 里复用别的 extractor：`use axum::RequestPartsExt;` 后 `parts.extract::<TypedHeader<Authorization<Bearer>>>().await` / `parts.extract_with_state::<T, S>(state).await`。不要手拆 `Authorization` 字符串。
5. 拿子状态用 `FromRef` 约束而不是钉死 `FromRequestParts<AppState>`：`where Pool: FromRef<S>` + `Pool::from_ref(state)`，`AppState` 上 `#[derive(FromRef)]`（AX-01）。钉死具体 state 的 extractor 不能复用到精简 state 的子路由/测试路由。
6. 消费 body 的自定义 extractor 必须委托 `Json`/`Form`/`Bytes`：`DefaultBodyLimit` 是在这些 extractor 内部经 `into_limited_body` 生效的，手写 `axum::body::to_bytes(req.into_body(), usize::MAX)` 等于无上限（AX-05）。非委托不可时先 `req.into_limited_body()`，或给 `to_bytes` 显式上限。
7. 多个 extractor 捆成一个参数：`#[derive(FromRequestParts)]`/`#[derive(FromRequest)]`，字段默认按自身 extractor 提取，`#[from_request(via(Query))]` 指定包装；`FromRequest` 派生只有最后一个字段可消费 body，含 body 字段却用 `FromRequestParts` 派生不编译；`#[from_request(state(AppState))]` 钉具体 state。

```rust
// axum 0.8 —— 原生 async fn；FromRef 取子状态，不钉死 AppState
// axum 0.7 —— 仅多一行：impl 上加 #[async_trait]，函数体相同
impl<S> FromRequestParts<S> for CurrentTenant
where S: Send + Sync, TenantRegistry: FromRef<S>,
{
    type Rejection = ApiError;
    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, ApiError> {
        let id = parts.headers.get("x-tenant-id").and_then(|v| v.to_str().ok()).ok_or(ApiError::MissingTenant)?;
        TenantRegistry::from_ref(state).lookup(id).map(CurrentTenant).ok_or(ApiError::UnknownTenant)
    }
}
```

## 校验：`ValidatedJson`、`garde` 与领域 parse 分层（AX-16、AX-20）

1. `Json<T>` 只保证「是 JSON 且能反序列化」。形状规则（必填/长度/格式/范围）放 `ValidatedJson<T>` extractor，不在 handler 里手调 `.validate()`：第一个忘记调用的 handler 就把脏数据送进库，而签名 `ValidatedJson<T>` 本身就是证明。`.validate()` 返回 `Result<(), ValidationErrors>`，丢弃返回值等于没校验（ERR-05）。
2. 状态码分两档：JSON 解析/类型不符 → 沿用 `JsonRejection` 自己的 400/415/422；解析成功但违反规则 → 422。禁止统一 400。
3. 校验层与领域层分工（AX-16/API-08）：extractor 查形状；`Email::parse`/`TryFrom<CreateUserReq> for NewUser` 收不变式并产出领域类型；同一条规则不在两层重复写；要查库的唯一性不属于任何校验 crate，是服务层的事。只有少量字段、不需要逐字段错误报告时，跳过 `validator`，直接 `#[serde(try_from = "String")]` newtype 让 `Json<T>` 本身产出领域类型（失败走 `JsonDataError` 422）。
4. `validator` 0.20（`features = ["derive"]`）：`#[validate(email)]`、`length(min = 1, max = 100)`、`range(min = 18)`、`must_match(other = "password2")`、`nested`（子类型也要 `derive(Validate)`）、`custom(function = "f")`、`regex(path = *RE)`——`RE` 必须是 `LazyLock<Regex>` 静态量（`expect("invariant: literal regex")`，ERR-03），禁止在 custom 函数里每请求 `Regex::new`。
5. 选 `garde` 当校验需要运行时上下文（租户、feature flag）：`#[garde(context(Ctx))]` + `validate_with(&ctx)`；garde 要求每个字段都有 `#[garde(…)]`，无规则字段写 `#[garde(skip)]`。`axum-valid` 之类包装 crate 提供 `Valid<Json<T>>`，但下面十几行已够，按 DEP-02 评估再加。

```rust
// axum 0.8（0.7 在 impl 上加 #[async_trait]）；Rejection 复用 ApiError，From 已在上节实现
pub struct ValidatedJson<T>(pub T);

impl<S, T> FromRequest<S> for ValidatedJson<T>
where S: Send + Sync, T: DeserializeOwned + Validate,
{
    type Rejection = ApiError;
    async fn from_request(req: Request, state: &S) -> Result<Self, ApiError> {
        let axum::Json(value) = axum::Json::<T>::from_request(req, state).await?; // 400/415/422 原样透传
        value.validate()?;                                                          // 规则错 → 422
        Ok(Self(value))
    }
}

// handler：CreateUserReq 已 derive(Deserialize, Validate)；形状已过，领域 parse 产出 NewUser，不再重复查 email 格式
async fn create(State(app): State<Arc<App>>, ValidatedJson(req): ValidatedJson<CreateUserReq>) -> Result<StatusCode, ApiError> {
    let new_user = NewUser::try_from(req)?;   // 领域不变式（API-08）
    app.users.create(new_user).await?;
    Ok(StatusCode::CREATED)
}
```

## 验证

- `tower::ServiceExt::oneshot` 逐条打（TEST-10）：缺 `Content-Type` → 415；`{"email": 1}` → 422 `bad_json`；`{"email": "x", "password": "short"}` → 422 `validation` 且 body **不含**提交的密码；`/users/abc` → 400；无 `Authorization` 打 `Option<AuthUser>` 路由 → 200，坏 token → 401。断言状态码 + 信封字段，不断言 serde 文案（TEST-08）。
- 0.7 → 0.8 升级：`rg 'Option<[A-Z]\w*<' src/` 列出所有 `Option<Extractor>` 逐个定语义；`rg async_trait src/` 在 extractor 文件里应为零。
