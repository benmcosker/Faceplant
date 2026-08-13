# Orchestrator and delegated contexts

A working setup for running Faceplant development as one orchestrator
supervising several specialist contexts, plus the reasoning behind it so you
can move the pattern to another repo.

Everything described here is checked into this repository and runs as-is:

```
CLAUDE.md                            shared brief, loaded by every context
.claude/agents/faceplant-scout.md    read-only recon          (haiku)
.claude/agents/faceplant-backend.md  backend/**               (sonnet)
.claude/agents/faceplant-frontend.md frontend/**              (sonnet)
.claude/agents/faceplant-persona.md  bot voice, prose only    (sonnet)
.claude/agents/faceplant-verifier.md read-only gate           (sonnet)
.claude/skills/orchestrate/SKILL.md  /orchestrate <feature>
```

---

## 1. The idea in one paragraph

A context window is a budget, and it is spent on everything the model has
looked at, not just what it needs now. A single agent that greps the backend,
reads twelve files, runs pytest twice, then starts on the frontend is making
its frontend decisions while dragging a full backend investigation behind it —
worse decisions, more expensive, and increasingly likely to lose the thread.
Delegation fixes this by giving each piece of work its own fresh context and
letting only a short structured report come back. The orchestrator's context
then grows by paragraphs instead of by files, so it stays sharp enough to do
the one thing only it can do: decide.

The subagent is not a smarter worker. It is a **context boundary with a job
description**.

---

## 2. What actually crosses the boundary

This is the part people get wrong, so it is worth being precise. When you
delegate, the new context starts with:

- its own system prompt — the markdown body of the agent file, *not* the main
  system prompt
- the delegation message the orchestrator writes
- every `CLAUDE.md` in the hierarchy
- a git status snapshot
- any skills named in the agent's `skills:` frontmatter

And that is all. It does **not** get your conversation history, the files
already read, the skills already invoked, or what a sibling context decided
thirty seconds ago. Two consequences follow, and they drive the whole design:

1. **`CLAUDE.md` is the only free channel.** A fact written there reaches every
   context at no cost per delegation. A fact stated in chat reaches none of
   them. That is why `CLAUDE.md` in this repo carries the commands, the wire
   contract, and the spend rules — those are exactly the things every context
   needs and would otherwise have to rediscover.
2. **Everything else you must restate, every time.** The orchestrate skill's
   four-part prompt (goal, contract, boundary, done-means) exists because there
   is no ambient context to lean on.

Coming back the other way is one message: the subagent's final report. So the
report format is not bureaucracy — it is the entire API between contexts, and
it is why every agent file here ends with a fixed output shape.

---

## 3. Cutting the seams

The instinct is to split by task: "you do step one, you do step two." That
produces contexts that fight over files and hand each other half-finished work.

Split by **ownership** instead. One writable territory per context, no overlap:

| Context | Writes | Never touches |
| :-- | :-- | :-- |
| `faceplant-backend` | `backend/app/**`, `backend/tests/**` | `frontend/`, persona prose |
| `faceplant-frontend` | `frontend/src/**`, `frontend/cypress/**` | `backend/` |
| `faceplant-persona` | `roster.py`, `house_style.py` | everything else |
| `faceplant-scout` | nothing | — |
| `faceplant-verifier` | nothing | — |

Faceplant makes this easy because its seams are real: the backend and frontend
communicate through exactly one contract, and the bot voices are prose that
happens to live in a `.py` file. That last one is the interesting case — the
persona context is defined by *what kind of thinking the work needs*, not by
directory. Writing a convincing satirical voice and wiring an APScheduler job
are different jobs that happen to share a folder, and they read better as
different contexts with different instructions.

Two rules keep the seams honest:

- **If two contexts can write the same file, you have one context, not two.**
- **If a slice needs a file it does not own, that is a dependency** — sequence
  it, or have the owner do it. It is never a reason to widen a boundary.

### Read-only is a real constraint, not a hint

`faceplant-verifier` has `disallowedTools: Write, Edit`. This matters more than
it looks. An agent that can both judge and fix will, under pressure to finish,
quietly fix — deleting the failing assertion, loosening a type to `any`,
disabling the lint rule. Removing the tool removes the temptation. The verifier
can only describe what it found, which is exactly what a gate should do.

The same logic gives `faceplant-persona` no `Bash` and no `Write`: it is there
to write voice, not to restructure the engine it feeds.

---

## 4. Running it

### The full protocol

```
/orchestrate add a "reply from this bot" button that regenerates one comment
```

The skill drives the loop: scout → cut slices → fix the contract → delegate in
parallel → fan in → gate through the verifier → report. Read
`.claude/skills/orchestrate/SKILL.md`; it is written to be read.

### Delegating one thing by hand

Three ways, escalating in force:

```text
Use the faceplant-scout agent to map everything the cost meter touches
```
Natural language — Claude decides whether to delegate.

```text
@agent-faceplant-verifier check the current diff
```
`@`-mention — guarantees that specific agent runs. (Type `@` and pick from the
typeahead, or type `@agent-<name>` manually.)

```bash
claude --agent faceplant-backend
```
Session-wide — the *main* thread takes on that agent's system prompt, tools, and
model. Useful when the whole session is backend work and you want the
boundaries enforced on yourself. Set it per-project instead with
`{"agent": "faceplant-backend"}` in `.claude/settings.json`.

### Continuing a context instead of restarting it

When a slice comes back needing a fix, resume it — Claude uses `SendMessage`
with the agent's name or ID:

```text
Send the pytest failure back to the backend agent and have it fix it
```

The original context still holds everything it read and every decision it made.
Spawning a fresh one instead makes it re-derive all of that from nothing, which
is both slower and where contradictory second attempts come from. **Resume by
default; spawn fresh only when you want the blind second opinion.**

### When you want the conversation carried along

`/subtask` forks the current conversation into a subagent that *inherits* your
history rather than starting fresh. That is the opposite trade from everything
above: no context savings, but no re-explaining either. Reach for it when the
setup cost genuinely exceeds the context cost — a long debugging thread you
want to branch without losing the thread.

---

## 5. Worked example: a per-thread spend cap in the UI

Say you want the cost meter to show spend for a single thread, not just
globally. It crosses every seam in the project, so it is a good stress test.

**Scout.** `faceplant-scout` returns roughly: `usage.py` records `TokenUsage`
rows; `routers/costs.py` aggregates them; `CostMeter.tsx` renders the total;
`reactions.py` writes usage rows keyed by the call, not the thread. Contract
note: `TokenUsage` has no `post_id`. That last line is the whole design problem,
found without reading a single file into your own context.

**Contract, decided by you, before anyone starts.** Not by the backend agent,
and not discovered later by the frontend agent:

```
GET /api/costs/thread/{post_id} -> {
  post_id: number, cost_usd: number,
  input_tokens: number, output_tokens: number, message_count: number
}
```

**Fan out, in parallel, in one message.** Backend: add `post_id` to
`TokenUsage`, thread it through the recording path in `reactions.py`, add the
route returning exactly that shape, cover it in `tests/test_costs.py`, keep
`ensure_columns()` self-healing for existing databases. Frontend: add the type
to `api.ts` exactly as specified, render it in `CostMeter`, colocated test,
theme tokens only.

They cannot collide — different territories — and they cannot drift, because
neither one invented the field names.

**Fan in.** Backend reports the migration path and a green pytest; frontend
reports lint, vitest, and build green. You read two short reports, not two
implementations.

**Gate.** `faceplant-verifier` runs all four checks and audits: does `api.ts`
match `schemas.py` field for field, is the new usage still metered, does the
new path respect the spend brakes, did any test get weakened. This is the first
context to see the change whole — which is the point, because every failure
mode in that list survives two individually-passing test suites.

---

## 6. Failure modes

**The orchestrator starts implementing.** The most common one. It reads a file
to route, the file is interesting, and forty minutes later it has written the
feature with a full backend investigation in context. The `/orchestrate` skill
states the rule flatly: read to decide, never to implement.

**Contract drift.** Two contexts each invent a plausible name — `cost_usd` and
`total_cost` — and both suites pass while the app is broken. Fixed only by
writing the shape down before fanning out. Never delegate "coordinate with the
other agent"; they cannot talk, and the orchestrator deciding is the mechanism.

**Delegating a question you have not formed.** "Look into the cost meter" comes
back with a competent essay you did not need. The four-part prompt exists to
force the question into shape before it costs anything.

**Re-spawning instead of resuming.** Ten fresh scouts that each rediscover the
same file map. If a context already knows something, send it a message.

**Splitting work that was not big enough to split.** Below about one file and
ten lines, the delegation overhead — writing the prompt, reading the report —
exceeds the work. Just do it.

**Trusting green slice reports.** Each context only ran its own checks. The
verifier gate is not redundancy; it is the only thing that sees the whole.

---

## 7. Knobs worth knowing

| Thing | Default | Change with |
| :-- | :-- | :-- |
| Nesting depth (subagents spawning subagents) | 3 layers | `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` |
| Concurrent subagents | 20 | `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` |
| Foreground vs background | background | `background: true` in frontmatter, or Ctrl+B |
| Model per context | inherits session | `model:` frontmatter |
| Effort per context | inherits session | `effort:` frontmatter |
| Isolated checkout | off | `isolation: worktree` |

Two notes from experience with this setup:

- **Model per context is where the savings are.** `faceplant-scout` runs on
  Haiku because grepping and mapping does not need a frontier model, and it is
  the agent you call most often. Judgment-heavy contexts stay on Sonnet or
  higher. Set this per agent rather than turning the whole session down.
- **Background is the default, and background subagents run with a narrower
  built-in tool set.** Usually invisible, and the win is real — you keep
  working while they run. But when a context needs a tool outside that set, ask
  for it in the foreground explicitly; otherwise Claude backgrounds it and only
  foregrounds when it needs the result to continue.

For genuinely parallel long-running work — several features at once, each with
its own branch — the next tier up is `isolation: worktree` (each context gets
its own checkout) or agent teams, where sessions run independently and message
each other. Same principles, heavier machinery.

---

## 8. The same shape, one level down

Worth noticing: Faceplant already *is* an orchestrator over delegated contexts.
It is the product.

`enqueue_reactions_for_post()` in `backend/app/bots/reactions.py` takes one
human post, decides which personas should respond, and schedules a wave of
independent jobs. Each job builds its own prompt from that bot's `persona` and
`voice_notes` plus the shared `house_style.py` prefix, calls the model in
isolation, and returns one comment. No bot sees another bot's context. The
orchestrator holds the thread; the personas hold their voices; the results
compose into a feed.

Every constraint in this guide has a counterpart in that engine — a fixed
contract (the comment row), an ownership seam (one bot, one reply), a spend
ceiling, and a gate before anything ships. If you want to see why bounded
delegated contexts are worth the ceremony, read `reactions.py`: it is the same
architecture, doing it in production, for a swarm that would otherwise cost you
real money.
