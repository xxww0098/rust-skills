# rust-skills evals

评测技能，而不是凭感觉改 `SKILL.md`。模式来自
[Testing Agent Skills Systematically with Evals](https://developers.openai.com/blog/eval-skills)：

> prompt → captured run (trace + artifacts) → checks → score over time

成功拆成四类，写进 [`success-criteria.json`](success-criteria.json)：

| 类 | 问的是 |
|---|---|
| Outcome | 任务做完了吗？只读命令有没有改业务代码？ |
| Process | 技能触发了吗？走的是预定 owner 吗？写授权守住了吗？ |
| Style | Finding / HOW→WHY→WHAT / 规则引用符不符合约定？ |
| Efficiency | 有没有 document+review+init 串烧、整目录读、命令空转？ |

## 证据阶梯

| 级 | 什么 | 何时绿 | 不是什么 |
|---|---|---|---|
| **E1** | 触发面：[`triggers.json`](triggers.json) + `scripts/eval-triggers.py` | description 含正向词、不含 skip 吸引词 | 不是「agent 会选这个技能」 |
| **E2** | 结构：压力场景 + `tests/fixtures/scene-*/contract.json` + `eval-fixtures.py` | playbook 仍点名规则、反模式还在磁盘上 | 不是「LLM 会按 playbook 做」 |
| **E3** | 行为：本目录 `prompts/*.csv` → 跑 agent → JSONL → grader | `--live` 或人工会话 + `--grade-trace` | 静态 `--static` **不算** E3 |

`check-consistency.sh` 只保证 E1/E2 和 E3 **契约**（CSV/schema/覆盖）没漂。
不得把 consistency 绿灯写成「行为已验证」。

## Prompt 集

每种都混了 blog 里的四类：explicit / implicit / contextual / negative。

| 文件 | 钉死什么 |
|---|---|
| [`prompts/trigger.prompts.csv`](prompts/trigger.prompts.csv) | 技能该不该激活 |
| [`prompts/routing.prompts.csv`](prompts/routing.prompts.csv) | 激活之后走哪条命令（含 craft/help/skip） |
| [`prompts/write-gate.prompts.csv`](prompts/write-gate.prompts.csv) | 只读 vs 建议 vs 声明文件 vs `--apply` |

发现一次失败（误触发、走错 slim/distill、`review --apply` 写了码）→ 加一行，不要只改散文。

## 怎么跑

```bash
# CI / 每次改 SKILL 或 metadata：契约检查（默认）
python3 scripts/eval-agent.py

# 有 Codex CLI 时才是真 E3
python3 scripts/eval-agent.py --live --suite trigger
python3 scripts/eval-agent.py --live --suite routing --limit 5

# 人工跑过、留下 JSONL 之后打分
python3 scripts/eval-agent.py --grade-trace evals/artifacts/trig-01.jsonl --case trig-01
```

`--live` 调 `codex exec --json`（只读用例不加 `--full-auto`；写授权用例在临时 Cargo fixture 里加）。
stdout 是 JSONL，grader 看 `command_execution` / 最终消息，不看「感觉更好」。

定性项（Finding 形状、HOW→WHY→WHAT）用
[`schemas/rubric.schema.json`](schemas/rubric.schema.json) + [`rubrics/rust-skill.md`](rubrics/rust-skill.md)
做第二轮只读 `codex exec --output-schema`。

产物写到 `evals/artifacts/`（gitignore）。
