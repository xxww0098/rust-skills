// Scene 14: select! drop of read_exact loses the half-read buffer.
loop {
    select! {
        r = stream.read_exact(&mut buf) => handle(r),
        _ = shutdown.recv() => break,
    }
}
