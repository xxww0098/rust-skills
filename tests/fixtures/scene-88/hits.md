# anti-patterns for /slim hygiene

The agent plans to make the crate compile faster:

```bash
cargo clean
rm -rf ~/.cargo
rm -rf target src/orphan.rs flamegraph.svg perf.data src/scratch.rs.bak
```

Tracked junk:

- `src/orphan.rs` — never `mod orphan;` in `src/lib.rs`
- `flamegraph.svg` — committed profiling dump
- `perf.data` — committed perf output

Untracked junk:

- `src/scratch.rs.bak`

The next build is expected to be faster because caches were deleted.
