# axum/data — 数据层接线、文件上传与静态文件

目的：handler 里出现 `PgPool`/`query!`/`begin()`、`Multipart`、`ServeDir`/`ServeFile`/`rust-embed` 证据时加载。只讲 axum 侧的接线与错误映射；池调优、N+1、`fetch` 流式、类型分界、离线宏缓存按 [../sqlx.md](../sqlx.md) 的 SX 编号引用不重复；错误 enum 形状见 AX-12，body 上限见 AX-05，大响应流式见 AX-07。

## 数据库：池进 state、handler 内查询与事务

1. 池在 `main` 建一次进 `AppState`；字段都是廉价句柄（`Pool`、`reqwest::Client`、`Arc<Config>`）时 `#[derive(Clone, FromRef)]`（axum feature `macros`），不再套 `Arc`（AX-02/SX-01）。`FromRef` 让 handler 与测试只收 `State<PgPool>`，不必知道整个 state。
2. 「零或一行」用 `fetch_optional` + `ok_or(NotFound)`，`fetch_one` 只用于「必须存在」的语义；查询结果禁 `unwrap`（ERR-03）。
3. 事务作用域 = `begin()` 到 `commit()` 之间只有本库语句，执行器写 `&mut *tx`；`?` 早退靠 `Transaction` Drop 回滚，不写手动 rollback（SX-07）。需要会话级状态（`LISTEN`、临时表）才写 `PoolConnection` extractor；普通「多条语句共用一条连接」就是事务。

```rust
#[derive(Clone, FromRef)]
struct AppState { db: PgPool, http: reqwest::Client }

async fn get_user(State(db): State<PgPool>, Path(id): Path<i64>) -> Result<Json<User>, AppError> {
    let user = sqlx::query_as!(User, "SELECT id, email FROM users WHERE id = $1", id)
        .fetch_optional(&db).await?
        .ok_or(AppError::NotFound)?;               // 404 语义写在调用点，不靠兜底映射
    Ok(Json(user))
}
```

## sqlx::Error → AppError 映射（AX-44）

一处 `From<sqlx::Error>`，handler 里只写 `?`（AX-12）。唯一键冲突按约束名区分字段，对外只说「已存在」，不回显 SQL。

```rust
impl From<sqlx::Error> for AppError {
    fn from(e: sqlx::Error) -> Self {
        match e {
            sqlx::Error::RowNotFound => Self::NotFound,                                   // 兜底；见下条
            sqlx::Error::Database(db) if db.is_unique_violation() =>
                Self::Conflict(db.constraint().map(str::to_owned)),                      // 409，约束名→字段提示
            sqlx::Error::Database(db) if db.is_foreign_key_violation() => Self::UnprocessableEntity,
            sqlx::Error::PoolTimedOut => Self::Unavailable,                               // acquire_timeout 到期 → 503（SX-02）
            other => Self::Internal(other.into()),                                       // 5xx 只带 request-id
        }
    }
}
```

- `RowNotFound` 兜底成 404 只对「URL 指向的资源」正确；内部必存在的行（当前用户、配置行）找不到是 500 级 bug，用 `fetch_optional` + 显式错误，不让兜底掩盖。`UPDATE`/`DELETE` 的 404 看 `rows_affected() == 0`。
- 先 `SELECT` 再 `INSERT` 判重复是竞态；唯一索引 + 409 映射才是边界（API-01 精神：约束进 DB）。

## 迁移与测试（AX-50）

- `sqlx::migrate!("./migrations").run(&pool)`（feature `migrate`）路径相对 `CARGO_MANIFEST_DIR`，workspace 里按 crate 指定；Docker 构建上下文必须含 `migrations/` 与 `.sqlx/`。单实例/开发可启动时跑；多实例滚动发布改独立迁移任务（SX-10）。
- `#[sqlx::test(migrations = "./migrations")] async fn t(db: PgPool)`：每个测试建全新库、跑迁移、结束删库；缺 `DATABASE_URL` 直接 panic（天然满足 TEST-07）。handler 测试 = 这个池装进 `app(AppState { db, .. })` + `oneshot` 打路由（TEST-10），同一请求发两次断言 201 → 409 就把唯一键映射测到了。

## 上传：Multipart 接线（AX-30）

1. `axum = { features = ["multipart"] }`；`Multipart` 消费 body，必须是最后一个参数，且与 `Json`/`Form`/`Bytes` 互斥（AX-13）；元数据走 `Path`/`Query` 或同一表单的文本字段。
2. 默认 2MB 上限对 `Multipart` 同样生效：小文件测试全绿、真实文件 413 是最常见事故。**只给上传路由抬限**：`post(upload).layer(DefaultBodyLimit::max(n))`，不要把 200MB 盖到整棵树让 JSON 路由一起失守（AX-05）。`DefaultBodyLimit::disable()` 必须紧跟 `RequestBodyLimitLayer::new(n)`（tower-http `limit`），单独 `disable()` = 无界 body。双上限：总大小由这层兜底，单文件在 chunk 循环里计数，超限立即停读并清理。
3. 整树 `TimeoutLayer` 会杀慢链路大文件：上传路由单独挂更长超时或 idle 策略（AX-04）。
4. `MultipartError` 自带 `IntoResponse`：`From<MultipartError> for AppError` 透传 `e.status()`/`e.body_text()`（超总上限 413、坏体 400、流读失败 500），不硬编码 400 也不 `unwrap`（坏请求变 500 + panic 日志）（AX-20）。

## 上传：流式落盘与文件名清洗（AX-43）

```rust
// ✗ 全量进内存 + 客户端文件名直接落盘
async fn upload(mut mp: Multipart) -> Result<(), AppError> {
    while let Some(field) = mp.next_field().await? {
        let name = field.file_name().unwrap_or("blob").to_owned(); // 可控："../../etc/cron.d/x"
        let data = field.bytes().await?;                           // 峰值内存 = 文件大小 × 并发数
        tokio::fs::write(format!("uploads/{name}"), &data).await?;
    }
    Ok(())
}

// ✓ 逐 chunk 写临时文件 → fsync → 同目录原子 rename；名字由服务端生成
const MAX_FILE: u64 = 50 << 20;
const ALLOWED: &[&str] = &["png", "jpg", "jpeg", "webp", "pdf"];

fn safe_ext(client_name: Option<&str>) -> Result<&'static str, AppError> {
    let ext = client_name.and_then(|n| Path::new(n).extension()?.to_str()).map(str::to_ascii_lowercase); // 只取扩展名；目录段与 `..` 全丢
    ALLOWED.iter().copied().find(|a| Some(*a) == ext.as_deref()).ok_or(AppError::UnsupportedMediaType)
}

async fn stream_to(field: &mut Field<'_>, tmp: &Path) -> Result<(), AppError> {
    let mut w = BufWriter::new(File::create(tmp).await?);
    let mut n = 0u64;
    while let Some(chunk) = field.chunk().await? {
        n += chunk.len() as u64;
        if n > MAX_FILE { return Err(AppError::PayloadTooLarge); }   // 单文件上限
        w.write_all(&chunk).await?;
    }
    w.flush().await?;
    w.get_ref().sync_all().await?;
    Ok(())
}

async fn upload(State(s): State<AppState>, mut mp: Multipart) -> Result<Json<Vec<Uuid>>, AppError> {
    let mut ids = Vec::new();
    while let Some(mut field) = mp.next_field().await? {
        if field.name() != Some("file") { continue; }
        let ext = safe_ext(field.file_name())?;       // 元数据在读 body 之前取
        let id = Uuid::new_v4();
        let tmp = s.upload_dir.join(format!(".{id}.part"));
        if let Err(e) = stream_to(&mut field, &tmp).await {
            let _ = tokio::fs::remove_file(&tmp).await;   // 清理尽力而为，主错误优先返回
            return Err(e);
        }
        tokio::fs::rename(&tmp, s.upload_dir.join(format!("{id}.{ext}"))).await?;  // 读者永远看不到半截文件
        ids.push(id);
    }
    Ok(Json(ids))
}
```

- `file_name()`/`content_type()` 都是客户端声明：只能用于白名单拒绝，不能作信任依据；要验真看文件头（首个 chunk 自查 magic 或 `infer` crate），或落盘后校验失败即删。
- `bytes()`/`text()` 只留给小而有界的字段（标题、说明）；`Field` 也实现 `Stream`，要接 `tokio::io::copy`/哈希管道时 `StreamReader::new(field.map_err(io::Error::other))`。
- 临时文件与目标必须同一文件系统，否则 `rename` 直接返回 `EXDEV` 错（不会退化成拷贝，`mv` 才拷），文件已全部落盘才失败：临时文件放上传目录内而不是 `/tmp`。上传目录不在静态服务的 `ServeDir` 根下（见下节）。

### 下载

- 鉴权与存在性查完再 `File::open`；响应体 `Body::from_stream(ReaderStream::new(file))`（AX-07，不 `read_to_end`），头部 `Content-Type` 取库里记录的 MIME（不是请求时客户端声明的），`Content-Disposition: attachment; filename="…"` 的文件名先剔除 `"`、`\`、CR/LF，非 ASCII 用 RFC 6266 的 `filename*`。
- 需要 `Range`/断点续传/`Last-Modified` 时，鉴权后把请求交给 `ServeFile::new(path).oneshot(req)`（`tower::ServiceExt`），不手写 Range 解析。

## 静态文件：ServeDir/ServeFile 挂载（AX-45）

`tower-http = { features = ["fs", "set-header"] }`。`ServeDir`/`ServeFile` 是 `Service` 不是 `Layer`：挂 `nest_service`/`fallback_service`/`route_service`，传给 `.layer()` 或 `.fallback()` 都是编译错误。0.7/0.8 写法相同（路径为静态字面量，不受 AX-18 影响）。

| 需求 | 写法 | 备注 |
|------|------|------|
| 目录挂前缀 | `nest_service("/assets", ServeDir::new("dist/assets"))` | 前缀被剥掉：磁盘路径不重复 `assets` |
| 根目录服务 | `fallback_service(ServeDir::new("dist"))` | 不用 `nest_service("/", …)` |
| 单文件 | `route_service("/favicon.ico", ServeFile::new("dist/favicon.ico"))` | MIME 按扩展名猜 |
| 缺文件 → 自定义页 + **404** | `ServeDir::new(d).not_found_service(svc)` | 自动套 `SetStatus(404)` |
| 缺文件 → 自定义页 + 自身状态 | `ServeDir::new(d).fallback(svc)` | SPA 深链 200 用这个 |
| 预压缩 | `.precompressed_br().precompressed_gzip()` | 构建期生成 `.br`/`.gz` 同名文件，零 CPU；已带 `content-encoding`，`CompressionLayer` 不会二次压 |

- 反方向同样卡人：带 `_service` 后缀的 `fallback_service`/`route_service`/`nest_service` 与 `ServeDir` 的 `not_found_service`/`fallback` 收的是 `Service<_, Error = Infallible>`，直接传 handler 函数编译不过。`use axum::handler::HandlerWithoutStateExt;` 后 `ServeDir::new("dist").not_found_service(api_404.into_service())`——`into_service()` 就是 `with_state(())`，只对不要 `State` 的 handler 可用；要 state 的写 `Handler::with_state(state)`。别为一个 404 页手写 `impl Service`。无 `_service` 后缀的 `route`/`fallback` 收的本来就是 handler，别反过来转。
- 路径穿越：`ServeDir` 会 percent 解码并拒绝 `..` 段（挂了 `fallback`/`not_found_service` 时非法路径走回退服务，不是裸 404），但**跟随符号链接、照常服务点文件**——`dist` 只放构建产物，不要指向仓库根或含 `.env`/`.git`/上传目录的路径。
- `ServeDir` 的 `Error = Infallible`：缺文件是 404 响应不是 `Err`，别套 `HandleErrorLayer` 等它出错。动态 `CompressionLayer` 只给 `/api` 的文本响应（AX-09）；静态资源走预压缩。

## SPA 回退、缓存头与路由优先级（AX-45）

```rust
fn app(state: AppState) -> Router {
    let api = Router::new()
        .route("/users/{id}", get(get_user))        // axum 0.8；0.7 写 "/users/:id"（AX-18）
        .fallback(|| async { (StatusCode::NOT_FOUND, Json(json!({"error": "not found"}))) })
        .with_state(state);                          // /api/* 未命中 → JSON 404，禁止漏到 index.html
    let assets = ServiceBuilder::new()
        .layer(SetResponseHeaderLayer::if_not_present(
            header::CACHE_CONTROL, HeaderValue::from_static("public, max-age=31536000, immutable")))
        .service(ServeDir::new("dist/assets").precompressed_br().precompressed_gzip());
    let spa = ServiceBuilder::new()
        .layer(SetResponseHeaderLayer::overriding(header::CACHE_CONTROL, HeaderValue::from_static("no-cache")))
        .service(ServeDir::new("dist").fallback(ServeFile::new("dist/index.html")));
    Router::new()
        .nest("/api", api)                // 1. 显式路由最先
        .nest_service("/assets", assets)  // 2. 前缀服务
        .fallback_service(spa)            // 3. 其余全部：根文件命中就给，否则 index.html（200，客户端路由）
}
```

- 缓存两档：hash 文件名（`app.3f9c1a.js`）`immutable` 一年；`index.html` 及其它无 hash 根文件 `no-cache`（每次协商，`ServeDir` 自带 `Last-Modified`/`If-Modified-Since`）。两档必须分开挂层，一个 `SetResponseHeaderLayer` 盖全站 = index 被缓存一年或 assets 白白协商。
- 深链状态码二选一并注释：客户端路由合法路径（`/settings`）→ `ServeDir::fallback(ServeFile)` 给 200；希望未知路径诚实 404（监控/爬虫可区分）→ `not_found_service`。无论哪种，`/api` 子路由必须有自己的 `fallback`，否则 `/api/nope` 返回 200 HTML 让客户端 JSON 解析失败。
- 优先级：显式 `route` > `nest`/`nest_service` > `fallback_service`；同前缀的 `route("/assets/x")` 与 `nest_service("/assets")` 可共存且静态段优先（AX-23），构造期 panic 的是 `nest_service("/", …)`（改 `fallback_service`）与同一路径注册两次（AX-25）。静态资源仍挂独立前缀，根只留 fallback。

### 单二进制嵌入的取舍

- 默认不嵌：容器部署 `COPY dist` + `ServeDir`（SH-01），改前端不触发 Rust 全量重编译，`Range`/`Last-Modified`/预压缩全免费。
- 嵌入（`rust-embed`，debug 下默认读磁盘、release 进二进制；`include_dir` 两种构建都嵌）只为单文件分发：CLI 自带 UI、桌面 sidecar。嵌入后 Content-Type、SPA 回退、缓存头都要自己补：`#[derive(RustEmbed)] #[folder = "dist/"] struct Dist;`，handler 里 `Dist::get(uri.path().trim_start_matches('/')).or_else(|| Dist::get("index.html"))` → `([(CONTENT_TYPE, f.metadata.mimetype())], f.data).into_response()`，`ETag` 取 `metadata.sha256_hash()`。

## 验证

- 数据：`#[sqlx::test]` + `oneshot` 覆盖 404/409/503 三条映射；`cargo sqlx prepare --check`（SX-03）。
- 上传：`curl -F file=@big.bin` 验证超 2MB 不再 413、超单文件上限 413 且 `uploads/` 无 `.part` 残留；文件名 `../../x.png` 落在上传目录内；`oha` 并发传大文件时进程 RSS 不随文件大小线性涨。
- 静态：`curl -I /assets/app.<hash>.js` 看 `cache-control: immutable` 与 `content-encoding: br`；`curl /api/nope` 必须 JSON 404；`curl /%2e%2e/Cargo.toml` 与 `/.env` 的响应体只能是 index.html（SPA `fallback` 模式下 200）或 404，绝不能是仓库文件内容，再跑 `find dist -name '.*'` 确认产物里没有点文件。
