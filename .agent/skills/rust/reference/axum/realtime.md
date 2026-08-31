# axum/realtime — WebSocket 与 SSE

目的：代码里出现 `WebSocketUpgrade` / `axum::response::sse` / `EventSource` / `broadcast::channel`，或用户要做聊天、协作、通知、进度条、LLM token 流时加载。只讲长连接特有的坑；超时分层、停机、状态、鉴权 extractor 的通则在 [../axum.md](../axum.md)（AX-04/06/15），取消安全与任务管理在 [../async.md](../async.md)（AS-01..06）。

## 选型

| 维度 | WebSocket | SSE | long-poll |
|---|---|---|---|
| 方向 | 双向 | 服务端 → 客户端 | 服务端 → 客户端，一次一条 |
| 传输 | 101 升级；0.8 另支持 HTTP/2 `CONNECT`（RFC 8441） | 普通 HTTP 响应，`text/event-stream` | 普通 HTTP |
| 二进制 | 原生帧 | 仅文本（二进制要 base64） | 任意 |
| 断线重连 | 自己写 | 浏览器自动 + `Last-Event-ID` 续传 | 天然 |
| 代理/LB | 需支持 Upgrade | 需关闭响应缓冲 | 无要求 |
| 浏览器限制 | 无 | HTTP/1.1 每源 6 连接，多标签页会耗尽 → 生产走 HTTP/2 | 同左 |
| 鉴权载体 | Cookie / 子协议 header / 首条消息 | Cookie / 一次性 query token（`EventSource` 不能设 header） | 任意 |
| 用它 | 聊天、协作编辑、游戏、客户端高频上行 | 通知、进度、日志尾随、token 流 | 极低频或代理环境最差时 |

客户端从不上行就用 SSE，不要为单向推送付 WS 的升级、重连、框架成本；需要 `Authorization` header 的 SSE 前端改 `fetch` + `ReadableStream` 手解协议。

## WebSocket：升级与握手（AX-36）

1. 开 `axum = { features = ["ws"] }`，否则 `axum::extract::ws` 整个模块不存在（E0432，不是缺方法）。路由用 `any(handler)`：HTTP/2 上的 WS 方法是 `CONNECT`，`get` 只覆盖 HTTP/1.1。
2. `WebSocketUpgrade` 是 `FromRequestParts`：`State`/`Query`/`HeaderMap`/鉴权 extractor 随意同列，**body extractor 不能**（升级接管连接）。鉴权放 extractor（AX-15），缺/过期 token 在 upgrade 前就回 401，连接永远建不起来；禁止先升级再在首条消息里查 token 却不设读超时。
3. Cookie 鉴权的 WS **必须校验 `Origin`**：浏览器对 WS 不做 CORS，任意网页都能带 cookie 连上（跨站 WS 劫持）。前端用 `Sec-WebSocket-Protocol` 夹带 token 时，服务端必须 `.protocols([...])` 回选一个，否则浏览器判握手失败。
4. `on_failed_upgrade` 默认**静默丢弃**错误：生产必须接 `tracing`/指标。`max_message_size`（默认 64 MiB）、`max_frame_size`（默认 16 MiB）按业务收紧，这是 WS 版的 AX-05。
5. `on_upgrade` 立刻返回 101，回调 future 要 `Send + 'static`：`Rc`/`RefCell` 跨 await 直接编译失败，共享状态用 `Arc` + 原子/`tokio::sync`。`ConnectInfo<SocketAddr>` 要服务端 `into_make_service_with_connect_info::<SocketAddr>()`，否则运行期 rejection。

## 0.8 的 `Message`（AX-36）

| axum 0.7 | axum 0.8 |
|---|---|
| `Text(String)` | `Text(Utf8Bytes)`：deref 到 `&str`，`.as_str()`；要 `String` 显式 `.to_string()` |
| `Binary(Vec<u8>)` / `Ping` / `Pong` | `Bytes`：deref 到 `&[u8]`，`.to_vec()` 才拷贝 |
| `CloseFrame<'static> { code: u16, reason: Cow<'static, str> }` | 去掉生命周期参数，`reason: Utf8Bytes`；`code` 仍是 u16，`close_code::NORMAL` 等常量两版都有 |

```rust
// ✗ 0.7 写法编 0.8：expected Utf8Bytes, found String
socket.send(Message::Text("hi".to_string())).await?;
// ✓ 构造走 .into() 或助手；读取优先借用
socket.send(Message::text("hi")).await?;
socket.send(Message::Text(format!("tick {i}").into())).await?;
let s: Utf8Bytes = msg.into_text()?;   // to_text()? -> &str；into_data() -> Bytes
```

`Utf8Bytes`/`Bytes` 都是引用计数，广播通道直接传它们（`Arc` 语义），禁止为了「类型熟悉」转回 `String` 再每订阅者 clone。

## 收发循环与取消安全（AX-37）

1. `recv()` 三态：`Some(Ok)` 数据、`Some(Err)` 协议/传输错误、`None` 对端干净断开。`None` 打 error 日志是刷屏事故（OBS-04）。
2. 顺序 `while let Some(m) = socket.recv().await { socket.send(m) }` 只能应答，卡在 `recv` 时推不出任何东西；服务端要主动推（广播、定时、他人消息）→ `loop + select!` 状态机（AS-06）。
3. `select!` 分支只放取消安全的 `socket.recv()` / `rx.recv()` / `interval.tick()` / `sleep_until`；**`send().await` 放分支体内跑完**——`SinkExt::send` 被取消会丢半条消息（AS-01）。单任务下 `send` 阻塞会暂停读取，这是对慢客户端的有界背压，不是 bug。
4. 只有读写必须互不阻塞时才 `socket.split()`（`futures_util::{StreamExt, SinkExt}`）成两个任务；此时**任一结束必须 `abort()` 另一半**，否则半开连接持有 `SplitSink` 永不释放（AS-03：abort 只在 await 点生效）：

```rust
let (mut sender, mut receiver) = socket.split();
let mut send_task = tokio::spawn(async move { /* rx.recv() → sender.send() */ });
let mut recv_task = tokio::spawn(async move { /* receiver.next() → tx.send() */ });
tokio::select! {
    _ = &mut send_task => recv_task.abort(),
    _ = &mut recv_task => send_task.abort(),
}
```

5. 心跳：tungstenite 收到 Ping 自动回 Pong，但只在你持续 `recv` 时才发出去；浏览器 API 不能主动 ping → 服务端 `interval` 发 `Message::Ping(Bytes::new())`，**只用入站帧续 deadline**。禁止 `timeout(IDLE, select!{...})` 整体包：出站分支也会重置计时，半开连接永不超时。
6. 关闭：收到 `Close(_)` 退出循环；主动关闭 `send(Message::Close(Some(CloseFrame { code: close_code::NORMAL, reason: "bye".into() })))` 后 return；0.8 已删掉 `WebSocket::close()`，`SinkExt::close` 只发空 Close 帧且要额外导入 `futures_util`。阻塞/重 CPU 不在连接任务里做（AX-08）：一个 `thread::sleep` 冻住整条 worker 上的所有连接。
7. `axum::serve(..).with_graceful_shutdown` **不等 upgrade 后的连接**（回调在独立 `tokio::spawn` 里跑）：房间循环加 `token.cancelled()` 分支，收到停机发 Close 帧再退出，连接任务进 `TaskTracker`（AX-06、AX-46、AS-04）。

## 广播房间（AX-37）

1. `broadcast::channel(N)`：N 是保留消息条数，发送方永不阻塞；订阅者落后超过 N 条收 `RecvError::Lagged(n)`，下一次 `recv` 从最老保留消息继续。`while let Ok(m) = rx.recv().await` 把第一次 Lagged 当断线——活连接被误杀；`.ok()` 静默跳过则客户端不知道少了 n 条。必须二选一：发 resync 提示让客户端走 REST 补齐，或踢下线。
2. `tx.send` 只在零订阅者时失败；多房间用 `HashMap<RoomId, broadcast::Sender<_>>`，`receiver_count() == 0` 时清理。
3. 每连接一个任务、一个 `Receiver`；禁止所有连接共用一把 `Mutex<WebSocket>` 逐个 `send`（锁跨 await，一个慢客户端拖死全房间，ASYNC-02）。

```rust
// axum 0.8 聊天室骨架：单任务 select，无 split
use axum::extract::{State, ws::{Message, Utf8Bytes, WebSocket, WebSocketUpgrade}};
use axum::{body::Bytes, response::Response};
use std::time::Duration;
use tokio::sync::broadcast::{self, error::RecvError};
use tokio::time::Instant;

#[derive(Clone)]
struct Chat { tx: broadcast::Sender<Utf8Bytes> }   // broadcast::channel(256)

async fn ws_handler(ws: WebSocketUpgrade, State(chat): State<Chat>, user: AuthUser) -> Response {
    // user: AX-15 的 FromRequestParts extractor，失败即 401，不会走到 upgrade
    ws.max_message_size(64 << 10)
        .on_failed_upgrade(|e| tracing::warn!(error = %e, "ws upgrade failed"))
        .on_upgrade(move |socket| room(socket, chat, user))
}

async fn room(mut socket: WebSocket, chat: Chat, user: AuthUser) {
    const IDLE: Duration = Duration::from_secs(60);
    let mut rx = chat.tx.subscribe();
    let mut ping = tokio::time::interval(Duration::from_secs(20));
    let mut deadline = Instant::now() + IDLE;                  // 只由入站帧续命
    loop {
        let sent = tokio::select! {                            // 四个分支都取消安全
            _ = tokio::time::sleep_until(deadline) => break,
            _ = ping.tick() => socket.send(Message::Ping(Bytes::new())).await,
            out = rx.recv() => match out {
                Ok(text) => socket.send(Message::Text(text)).await,
                Err(RecvError::Lagged(n)) => socket.send(Message::text(format!("lagged:{n}"))).await,
                Err(RecvError::Closed) => break,
            },
            inbound = socket.recv() => {
                deadline = Instant::now() + IDLE;              // Pong/Text 都算活着
                match inbound {
                    Some(Ok(Message::Text(t))) => {
                        chat.tx.send(format!("{}: {t}", user.name).into()).ok(); // 自身持有 rx，不会失败
                        Ok(())
                    }
                    Some(Ok(Message::Close(_))) | None => break,   // 对端关闭 / 连接消失，不是错误
                    Some(Ok(_)) => Ok(()),                         // Ping 已自动回 Pong
                    Some(Err(e)) => { tracing::debug!(error = %e, "ws protocol error"); break }
                }
            }
        };
        if sent.is_err() { break }                             // 写失败 = 对端已走
    }   // 返回即 Drop：rx 退订、socket 关闭
}
```

## SSE（AX-38）

1. 返回 `Sse<impl Stream<Item = Result<Event, Infallible>>>`：`Sse::new` 要 `TryStream<Ok = Event>`，裸 `Stream<Item = Event>` 不满足 → `.map(Ok)`；会失败的源（DB 游标、`BroadcastStream`）用 `Result<Event, axum::BoxError>`。流必须 `Send + 'static`（捕获 `Arc`，不捕获借用）。
2. `Event::default().data(..)` / `.json_data(v)?`（`json` 是**默认 feature**）/ `.event("name")` / `.id("42")` / `.retry(Duration)`。`data`/`json_data`/`event`/`id`/`retry` 每个 `Event` 只能调一次，第二次 panic；`event`/`id`/`comment` 含换行 panic；多行放进一个 `.data("a\nb")`。`data` 为空的事件浏览器不派发。
3. `.keep_alive(KeepAlive::default())` 必挂：默认 15s 一条注释帧，要短于代理 idle（nginx `proxy_read_timeout` 默认 60s）。没有它，安静的流被中间层掐断而浏览器以为还活着。
4. 来源：`ReceiverStream`（有界 mpsc，ASYNC-05）或 `BroadcastStream`（tokio-stream feature `sync`，Lagged 同 WS 规则：映射成 `lagged` 事件或结束流让浏览器重连补齐，禁止 `filter_map(Result::ok)`）。生产者在独立任务，`tx.send().await.is_err()` 就是客户端断开——立即停工；重 CPU 走 `spawn_blocking` 再回传，不在 `poll_next` 路径做任何阻塞。
5. 续传：读 `HeaderMap` 的 `last-event-id`，从持久日志回放 `stream::iter(backlog).chain(live)`；**先 subscribe 再查 backlog**，按 id 去重，否则两步之间的事件丢失。broadcast 本身不能回放，要续传就得有存储。
6. 结束语义：流产出 `None` 响应即结束，`EventSource` 默认约 3s 后**自动重连**（`retry` 可调）。有限流（进度、一次性任务）要发终止事件让前端 `close()`，或重连时返回 204——非 200 状态使 `EventSource` 停止重连。
7. 超时与中间件：禁止整请求 `TimeoutLayer` 盖住 SSE 路由（AX-04，嵌套/拆分后只给非流式路由挂）；tower-http `CompressionLayer` 默认谓词已排除 `text/event-stream`，自定义 predicate 必须保留该排除（AX-09）。
8. 代理缓冲：nginx `proxy_buffering off` 或响应头 `X-Accel-Buffering: no`；`Content-Type: text/event-stream` 与 `Cache-Control: no-cache` 由 axum 设置，不要再手写覆盖。

```rust
// axum 0.7/0.8 相同：进度流骨架
use axum::{extract::State, response::{sse::{Event, KeepAlive, Sse}, IntoResponse}};
use std::{convert::Infallible, sync::Arc, time::Duration};
use tokio_stream::{wrappers::ReceiverStream, StreamExt as _};

async fn progress(State(app): State<Arc<App>>) -> impl IntoResponse {
    let (tx, rx) = tokio::sync::mpsc::channel::<Event>(16);   // 有界
    app.tasks.spawn(async move {                               // TaskTracker（AS-05）
        for pct in (0..=100).step_by(10) {
            let evt = Event::default().id(pct.to_string()).data(pct.to_string());
            if tx.send(evt).await.is_err() { return }          // 客户端断开 → 停工
            tokio::time::sleep(Duration::from_millis(300)).await; // 真实工作：spawn_blocking 后回传
        }
        tx.send(Event::default().event("done").data("100")).await.ok(); // 终止事件，前端据此 close()
    });
    // 返回型是 impl IntoResponse（要带头），错误类型没处可推 → 必须显式钉住，否则 E0283
    let sse = Sse::new(ReceiverStream::new(rx).map(Ok::<_, Infallible>)).keep_alive(KeepAlive::default());
    ([("x-accel-buffering", "no")], sse)
}
```

## 验证

- WS：`oneshot` 走不了升级——`TcpListener::bind("127.0.0.1:0")` 起 app，用 `tokio-tungstenite` 客户端连；`tokio::time::pause()` 驱动心跳与 idle 分支（TEST-09）；压测看 Lagged 计数、RSS 与每连接任务数是否随断开归零。
- SSE：`oneshot` 拿 `Response`，断言 `content-type: text/event-stream`，`http_body_util::BodyExt::frame()` 取前几帧后 drop（无限流不要 `collect`）；断线后生产者任务必须在一个 send 周期内退出。
