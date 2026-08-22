# axum/auth — 认证与授权：JWT、Session、RBAC

目的：代码里出现 `jsonwebtoken`/`tower-sessions`/`axum-login`/`oauth2`、`Authorization: Bearer`、`Session` extractor、`login_required!`、`route_layer(from_fn(..))`，或用户问「怎么保护路由 / 加登录 / 做权限」时加载；本文件只展开 AX-15 的实现与审查点。超时/限流见 [../axum.md](../axum.md)，`AuthError` 这类错误 enum 的 `IntoResponse` 骨架见 [handlers.md](handlers.md)，密码与会话表的查询纪律见 [../sqlx.md](../sqlx.md)。版本：axum 0.8（0.7 差异注释一行）、jsonwebtoken 11（10.x 同形）、tower-sessions 0.15、axum-login 0.18、oauth2 5.0。

## 选型

| 场景 | 方案 | 状态 | 撤销 | 主要风险 |
|---|---|---|---|---|
| SPA/移动端/S2S，每请求自带凭证，多实例无共享存储 | JWT（`jsonwebtoken` + `axum-extra` `Authorization<Bearer>`） | 无 | 只能等 `exp`；要即时撤销就得加状态 | 密钥泄露=全体可伪造；`exp` 过长；`alg`/`aud` 不显式 |
| 第一方浏览器、服务端渲染、需即时登出或可变用户态 | Session（`tower-sessions` + sqlx/redis store；全套登录用 `axum-login`） | 服务端 | `session.delete()`；`session_auth_hash` 变更即失效 | `MemoryStore` 上生产；cookie 属性被关；登录不轮换 id；CSRF |
| 第三方身份（Google/GitHub/SSO） | OAuth2 授权码 + PKCE（`oauth2`）→ 回调后建本地 session | 身份委托 | 同 session | 不校 `state`；`client_secret` 入库；HTTP client 跟随重定向（SSRF） |
| 内网/演示/机器对机器 | HTTP Basic（`Authorization<Basic>`） | 无 | 换密码 | 每请求明文 base64；只能走 TLS；禁作人类登录 |

一条路由只用一种主认证。OAuth2 是身份来源不是会话机制：回调之后仍要选 session 或 JWT 承载登录态。

## JWT（AX-39）

```toml
axum-extra   = { version = "0.10", features = ["typed-header"] }   # axum 0.7 配 axum-extra 0.9，TypedHeader 自 0.7 起已不在 axum 本体
jsonwebtoken = { version = "11", features = ["aws_lc_rs"] }        # 默认不带任何后端：aws_lc_rs / rust_crypto 必须显式二选一
```

1. `Claims` 必须带 `exp`（Unix 秒，`u64`），由「now + 生命周期」算出；`Validation::default()` 要求 `exp` 且校验过期（leeway 60 s），缺字段 = 所有 token 都解不开。access token 生命周期 5–15 分钟，不是 7 天。
2. 密钥只从环境/secret 管理读，启动时失败；禁止字面量、禁止进日志（OBS-02）。`Keys` 进 state 用 `FromRef` 取（测试能注入独立密钥）；单二进制小服务才用 `static KEYS: LazyLock<Keys>`。
3. `Validation` 显式：`Validation::new(alg)` + `set_issuer` + `set_audience`；`algorithms` 只放一族，禁止「HS256 和 RS256 都收」。验证 IdP 签发的 RS256/EdDSA：`decode_header(token)?.kid` 选 JWKS 里的 key → `DecodingKey::from_jwk`；JWKS 缓存在 state，未知 `kid` 只刷新一次。
4. 算法：一个服务自签自验 → HS256（32 字节随机密钥）；签发方与验证方分离 → RS256 或 EdDSA（`EncodingKey::from_rsa_pem`/`from_ed_pem`，验证方只拿公钥），`Header` 带 `kid` 便于轮换。
5. 错误：extractor 的 `Rejection` 是具名 `AuthError`（AX-12）；缺/坏/过期 token 统一 401 + `WWW-Authenticate: Bearer`，签发失败 500；禁止把 `jsonwebtoken::errors::Error` 当 `Rejection` 或写进响应体（泄露算法与失败类型）。官方 `examples/jwt` 对坏 token 回 400 是已知偏差，按 RFC 6750 用 401。
6. 刷新与撤销：refresh token 是不透明随机串，库里只存 SHA256 哈希 + 过期 + 家族 id，用一次换一次，旧串再次出现即撤销整个家族；禁止把 refresh token 做成另一枚 JWT。JWT 本身无法即时撤销——封号/改密码必须立刻生效的业务要么 `exp` 短到可接受，要么 `jti` 黑名单（又变有状态，那就直接用 session）。claims 里的角色到 `exp` 前不会更新，高敏操作查库。

```rust
use axum::{extract::{FromRef, FromRequestParts}, http::request::Parts, RequestPartsExt};
use axum_extra::{headers::{authorization::Bearer, Authorization}, TypedHeader};
use jsonwebtoken::{decode, Algorithm, DecodingKey, EncodingKey, Validation};

#[derive(Clone)]
pub struct Keys { pub enc: EncodingKey, pub dec: DecodingKey, pub validation: Validation }

impl Keys {
    pub fn from_env() -> Result<Self, std::env::VarError> {
        let secret = std::env::var("JWT_SECRET")?;                 // 组合根调用，缺失直接启动失败
        let mut validation = Validation::new(Algorithm::HS256);
        validation.set_issuer(&["https://auth.example.com"]);
        validation.set_audience(&["orders-api"]);
        Ok(Self { enc: EncodingKey::from_secret(secret.as_bytes()), dec: DecodingKey::from_secret(secret.as_bytes()), validation })
    }
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct Claims { pub sub: String, pub iss: String, pub aud: String, pub exp: u64, #[serde(default)] pub roles: Vec<String> }

// axum 0.8：原生 async fn；axum 0.7 在 impl 上加 #[axum::async_trait]，其余一字不改
impl<S> FromRequestParts<S> for Claims
where S: Send + Sync, Keys: FromRef<S>,
{
    type Rejection = AuthError;

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, AuthError> {
        let TypedHeader(Authorization(bearer)) = parts
            .extract::<TypedHeader<Authorization<Bearer>>>()
            .await
            .map_err(|_| AuthError::MissingToken)?;
        let keys = Keys::from_ref(state);
        decode::<Claims>(bearer.token(), &keys.dec, &keys.validation)
            .map(|t| t.claims)
            .map_err(|e| { tracing::debug!(error = %e, "jwt rejected"); AuthError::InvalidToken })  // 细节只进 debug，不进响应
    }
}
```

签发：`encode(&Header::default(), &claims, &keys.enc)`（`Header::default()` 即 HS256；RS256 用 `Header::new(Algorithm::RS256)` 并填 `kid`）。登录接口比对 client secret/API key 必须常量时间（`subtle::ConstantTimeEq` 或直接 argon2 校验哈希），禁 `!=` 字符串比较。

## Session（AX-40）

1. `tower-sessions` 0.15 默认已是 `Secure` + `HttpOnly` + `SameSite=Strict`、名 `id`、无过期；通常只需 `with_expiry`。`with_secure(false)` 只许在本地 HTTP 开发分支（`cfg!(debug_assertions)` 或配置开关），生产代码里出现即缺口；`with_same_site(SameSite::None)` 必须同时写明跨站嵌入理由并加 CSRF token。
2. store：`MemoryStore` 仅开发（重启全掉线、多实例不共享）。生产 `tower-sessions-sqlx-store`（`PostgresStore::new(pool)` + `migrate()`，feature `postgres`/`mysql`/`sqlite`）或 `tower-sessions-redis-store`。sqlx store **不会自动清理过期行**：必须 spawn `store.clone().continuously_delete_expired(Duration::from_secs(60))`（trait `tower_sessions::ExpiredDeletion`）并纳入 TaskTracker（AS-05）。
3. 登录成功先 `session.cycle_id()` 再 `insert("user_id", ..)`：不换 id 就是 session fixation。登出 `session.delete()`（或 `flush()`）销毁服务端记录，不是只清 cookie。`axum-login` 的 `login()` 已含轮换。
4. 密码：argon2 校验是 50–100 ms CPU，必须 `spawn_blocking`（ASYNC-03/AX-08）；查无此用户也跑一次对固定假哈希的校验，否则响应时间泄露用户名存在性；禁 `==` 比对明文。
5. `axum-login`：`AuthUser::session_auth_hash` 返回密码哈希字节 → 改密码即全端登出，免费的撤销。`AuthnBackend`/`AuthzBackend` 0.18 是原生 async fn（无 `#[async_trait]`）。`login_required!` / `permission_required!(Backend, login_url = "/login", "orders:write")` 只用 `route_layer` 且在要保护的 `.route(..)` 之后；`AuthManagerLayerBuilder::new(backend, session_layer).build()` 用 `.layer` 挂整棵树（每个请求都要能加载 session）。
6. CSRF：`SameSite=Strict/Lax` 已挡住大部分跨站 POST；`SameSite=None` 或用 cookie 承载 JWT 时必须加同步令牌（存 session、表单/头回传）。`Authorization` 头里的 JWT 不受 CSRF 但受 XSS；cookie 相反。选哪边写进 ADR，不要两边都做一半。
7. HTTP Basic：`TypedHeader<Authorization<Basic>>`，`auth.username()`/`auth.password()`；失败回 401 + `WWW-Authenticate: Basic realm="admin"`。缺 header 时 `TypedHeader` 自带拒绝是 400——用 `Option<TypedHeader<..>>` 自己回 401。仅 TLS、仅内网/S2S，人类登录一律 session。

```rust
// 组合根（tower-sessions 0.15 + axum-login 0.18）
let store = PostgresStore::new(pool.clone());
store.migrate().await?;
tracker.spawn(store.clone().continuously_delete_expired(std::time::Duration::from_secs(60)));
let session_layer = SessionManagerLayer::new(store)          // 默认 Secure/HttpOnly/SameSite=Strict，不必重复写
    .with_expiry(Expiry::OnInactivity(time::Duration::minutes(30)));
let auth_layer = AuthManagerLayerBuilder::new(Backend::new(pool), session_layer).build();

let app = Router::new()
    .route("/orders", get(list_orders))
    .route_layer(login_required!(Backend, login_url = "/login"))   // 只包上面已注册的路由；.layer 会把 404 变登录跳转
    .route("/login", get(login_form).post(login))
    .layer(auth_layer);                                            // 整棵树
```

裸 `tower-sessions` 的登录 handler 形状与下节 OAuth2 回调尾部相同：校验凭证 → `cycle_id()` → `insert("user_id", ..)` → `Redirect`。

## OAuth2 授权码（AX-41）

1. `BasicClient::new(ClientId)` + `set_client_secret`/`set_auth_uri`/`set_token_uri`/`set_redirect_uri`；`client_secret` 从环境读。5.x 的 client 类型参数是 typestate，进 state 时写 `type OauthClient = BasicClient<EndpointSet, EndpointNotSet, EndpointNotSet, EndpointNotSet, EndpointSet>`（以 docs.rs 为准）。
2. 跳转路由：`PkceCodeChallenge::new_random_sha256()` → `authorize_url(CsrfToken::new_random).set_pkce_challenge(..).url()`；把 `csrf.secret()` 与 `verifier.secret()` 写进 session 再 `Redirect`。机密客户端也用 PKCE；scope 最小。
3. 回调路由：**先**从 session `remove` 出 state（一次性）并与 `params.state` 比对，不等回 400；**再** `exchange_code`。跳过比对 = 受害者被登进攻击者账号。
4. token 交换用的 `reqwest::Client` 必须 `redirect(Policy::none())`（oauth2 文档明确的 SSRF 防护），建一次进 state（AX-02）。
5. 拿到 token → 查/建本地用户 → `cycle_id` + 写 `user_id`。provider 的 access/refresh token 不下发浏览器；后续要调 provider API 才服务端加密保存。

```rust
#[derive(serde::Deserialize)]
struct Callback { code: String, state: String }

async fn oauth_callback(session: Session, State(app): State<App>, Query(q): Query<Callback>) -> Result<Redirect, AppError> {
    let expected: String = session.remove("oauth_state").await?.ok_or(AppError::BadRequest)?;
    if q.state != expected { return Err(AppError::BadRequest); }                         // 先校 state
    let verifier: String = session.remove("oauth_pkce").await?.ok_or(AppError::BadRequest)?;
    let token = app.oauth.exchange_code(AuthorizationCode::new(q.code))                   // 再换 code
        .set_pkce_verifier(PkceCodeVerifier::new(verifier))
        .request_async(&app.http).await                                                   // app.http: redirect Policy::none()
        .map_err(|_| AppError::Unauthorized)?;
    let user = app.users.upsert_from_provider(token.access_token().secret()).await?;
    session.cycle_id().await?;
    session.insert("user_id", user.id).await?;
    Ok(Redirect::to("/"))
}
```

## 授权（AX-42）

1. 分层：认证 extractor 产出身份，失败 401；授权读身份做判断，失败 403。handler 里散落 `if claims.role == "admin"` 是缺口（AX-15）；401/403 错位会让已登录客户端反复重登。
2. 两种机制：整组路由（`/admin/*`）用 `route_layer(from_fn_with_state(state.clone(), guard))`；单个 handler 用 newtype extractor（`RequireRole<Admin>`），要求出现在签名里、忘不掉。newtype 内部必须复用 `Claims::from_request_parts`，禁止第二次解 token（两条验证路径会漂移）。
3. `from_fn` 参数顺序固定：`[FromRequestParts..], Request, Next`（AX-13 同理）。`Claims` 依赖 state（`Keys: FromRef<S>`）时 `from_fn` 的 `S = ()` 编不过，必须 `from_fn_with_state(state.clone(), guard)` 且路由 `.with_state(state)`。
4. `route_layer` 只包调用时已注册的路由（AX-28）：写在 `.route(..)` **之后**，之后再加的路由不受保护且无编译错误。用 `.layer` 挂守卫会把不存在的路径从 404 变 401/403，泄露路由存在性。
5. 拒绝默认：权限集用 `resource:action`（`orders:write`、`billing:refund`），端点写能力不写角色，角色到能力的映射在签发/加载用户时展开一次；映射里没有的 = 拒绝。
6. 资源归属检查在 handler/服务层：`WHERE id = $1 AND owner_id = $2`（SX-04 参数绑定），不在 route_layer。非归属资源回 404 还是 403 定一次并写注释：按资源（订单、文档）默认 404 防枚举，按区段（`/admin`）403。
7. 日志只记 `user_id`/`sub` 与决策结果，禁记 token、cookie、`Authorization` 头；自定义 `TraceLayer::on_request` 打印 headers 的先脱敏（OBS-02）。持 token/密码的结构手写或脱敏 `Debug`（API-05）。

```rust
// 单 handler 级：要求写在类型里
pub trait Role { const NAME: &'static str; }
pub struct Admin;
impl Role for Admin { const NAME: &'static str = "admin"; }

pub struct RequireRole<R: Role>(pub Claims, pub std::marker::PhantomData<R>);   // 两个字段都要 pub：私有字段的元组结构体跨模块无法解构（E0532）

impl<S, R> FromRequestParts<S> for RequireRole<R>
where S: Send + Sync, R: Role, Claims: FromRequestParts<S, Rejection = AuthError>,
{
    type Rejection = AuthError;

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, AuthError> {
        let claims = Claims::from_request_parts(parts, state).await?;      // 401 留给 Claims
        if !claims.roles.iter().any(|r| r == R::NAME) {
            return Err(AuthError::Forbidden);                               // 已认证无权：403
        }
        Ok(Self(claims, std::marker::PhantomData))
    }
}

async fn delete_user(RequireRole(claims, _): RequireRole<Admin>, Path(id): Path<u64>) -> Result<StatusCode, AppError> {
    tracing::info!(actor = %claims.sub, target = id, "delete user");
    Ok(StatusCode::NO_CONTENT)
}

// 组级：/admin 整组；from_fn_with_state，因为 Claims 要从 state 拿 Keys
async fn require_admin(claims: Claims, req: Request, next: Next) -> Result<Response, AuthError> {
    if !claims.roles.iter().any(|r| r == "admin") { return Err(AuthError::Forbidden); }
    Ok(next.run(req).await)
}
let admin = Router::new()
    .route("/admin/users/{id}", delete(delete_user))                                  // axum 0.7 写 :id（AX-18）
    .route_layer(middleware::from_fn_with_state(state.clone(), require_admin))      // 在 .route 之后
    .with_state(state);
```

## 验证

`tower::ServiceExt::oneshot` 矩阵（TEST-10），每条都必须能变红：无 token → 401 且带 `WWW-Authenticate`；过期 / 改签名 / 把 header `alg` 改成 `none` 或另一族 → 401；合法 token 非 admin → 403；不存在路径 + 坏 token → 404（证明守卫走的是 `route_layer`）；登录响应 `Set-Cookie` 含 `HttpOnly; Secure; SameSite`，且登录前后 session id 不同；OAuth2 回调 `state` 不匹配 → 400 且未发起 token 请求；他人资源 → 约定的 404/403。测试用独立 `Keys` 注入 state，不读环境变量。
