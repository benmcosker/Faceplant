---
name: orchestrate
description: Run a Faceplant feature as an orchestrator over delegated contexts — scout the ground, split the work along ownership seams, delegate each slice to its specialist subagent, then gate the result through the verifier. Use for changes that span backend and frontend, or any change large enough that reading all of it would crowd the main conversation.
argument-hint: [what you want built]
disable-model-invocation: true
---

You are the orchestrator for this change:

**$ARGUMENTS**

Your context is the project's most expensive resource. Spend it on decisions,
not on file contents. Everything you can hand to a delegated context, hand off.

## The one rule

You may read files to make a routing decision. You may not implement. If you
find yourself writing code, you have stopped orchestrating — that work belongs
to `faceplant-backend`, `faceplant-frontend`, or `faceplant-persona`.

The exception is a change so small that delegating costs more than doing it: a
one-line typo, a single constant. Below roughly one file and ten lines, just do
it and say you skipped the ceremony.

## Protocol

### 1. Scout

Delegate to `faceplant-scout` before deciding anything, unless the target files
are already named in the request. Ask for the blast radius: entry points, what
else touches them, which tests cover them, which contracts are in play.

You get back a file map, not a pile of code. That map is what you plan against.

### 2. Split along ownership seams

Cut the work by **who owns the file**, never by "step 1, step 2":

| Slice | Context | Owns |
| :-- | :-- | :-- |
| API, DB, engine, settings, pytest | `faceplant-backend` | `backend/app/**`, `backend/tests/**` |
| Components, theme, api.ts, vitest | `faceplant-frontend` | `frontend/src/**`, `frontend/cypress/**` |
| Bot voice | `faceplant-persona` | `roster.py`, `house_style.py` |

Two contexts must never be able to write the same file. If a slice needs a file
another context owns, that is a dependency, not a slice — sequence it.

### 3. Fix the contract before you fan out

This is the step that decides whether the result composes.

If the change crosses the API boundary, **write the JSON shape down yourself,
in your delegation prompts, before either side starts.** Give the backend the
exact response shape to produce and the frontend the exact shape to expect. Two
contexts that each invent a plausible field name produce two correct halves
that do not fit — and nothing catches it until the app is running, because both
suites pass.

### 4. Delegate

Run independent slices in parallel — spawn them in a single message. Sequence
only real dependencies: schema before client, model before router, engine
before persona.

Every delegation prompt carries, in this order:

1. **Goal** — the outcome, not the steps. They are the specialist, not you.
2. **Contract** — exact shapes, names, settings, defaults.
3. **Boundary** — the files this context may write, stated explicitly.
4. **Done means** — the checks that must pass before it reports back.

Delegated contexts start fresh. They load `CLAUDE.md` and nothing else from
this conversation — not the scout's map, not the user's phrasing, not what a
sibling just decided. Anything they need, you restate. This is the single most
common way an orchestration goes wrong.

### 5. Fan in

Read each report. You are looking for exactly three things:

- **Contract drift** — did the shapes come back matching what you specified?
- **Left undone** — a request one context handed to another. Route it now.
- **Red checks** — send the failure back to the context that owns it, with the
  evidence. Do not fix it yourself, and do not accept "I will fix it next."

Resume a context with `SendMessage` rather than spawning a fresh one. The
original still has its context loaded; a new one starts blind and re-derives
everything you already paid for.

### 6. Gate

Delegate to `faceplant-verifier` last, always, even when every slice reported
green. Each context only ran its own checks; the verifier is the first thing to
see the change whole, and the audit it runs — wire contract, metering, spend
brakes, off-by-default, weakened tests — is exactly the class of bug that
survives a suite of individually-passing slices.

FAIL means route the failure back and re-gate. Do not commit on a FAIL.

### 7. Report

Tell the user what changed, what each context did, what the verdict was, and
what you chose not to do. Name the files. Do not paste the reports.

## Budget

Stop and check in with the user if you cross any of these:

- More than 8 delegations for one feature
- The same slice failing verification twice
- A slice that comes back asking for a file another context owns, twice

All three mean the seams are wrong. Re-cut the work rather than delegating
harder at it.
