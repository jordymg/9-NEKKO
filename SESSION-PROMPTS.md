# Session prompts

## Session-start (paste into any AI: Claude, Claude Code, Cursor, Gemini)

---
You are working on NEKKO. Repo: [GitHub URL or local path].

Before doing anything:
1. Read `docs/STATUS.md` — current state and next actions.
2. Read `docs/PRD.md` — what we're building and why.
3. Read `docs/ARCHITECTURE.md` — stack and conventions. Follow them.
4. Skim `docs/decisions/` — these decisions are SETTLED. Do not re-open them; if you disagree, propose a new ADR instead.

Today's session goal: [what you want to accomplish].

Constraints: work only within the current phase in `docs/ROADMAP.md`. Anything out of scope goes to the icebox, not into the code. This project has a kill date (2026-08-12) — bias toward the cheapest path to answering the thesis.
---

## Session-close (paste before ending any session)

---
We're closing this session. Update the project docs:
1. Update `docs/STATUS.md`: "Last updated" line, move completed items to Done, rewrite "Next up" for a cold start, update Blocked, append a Session log row.
2. Capture decisions: any significant decision → new `docs/decisions/NNNN-title.md` (ADR format), referenced in the session log.
3. Check `docs/ROADMAP.md`: tick completed tasks; if the phase exit criterion is met, mark the next phase CURRENT.
4. Show me the diff of what you changed before finishing.
---
