# kernel/evidence — 一轮只建一份 ProjectSnapshot

快照是本轮的事实账本。禁止每个 playbook 另画 crate 图。采集不到的写入 `degraded_reasons`，不要猜一个确定答案。

机械采集入口：`python3 scripts/inspect_project.py <根>`。投影节入口：先采集快照，再 `python3 scripts/render_rust_md.py --snapshot <快照.json>`。渲染器不得自己再采集。
