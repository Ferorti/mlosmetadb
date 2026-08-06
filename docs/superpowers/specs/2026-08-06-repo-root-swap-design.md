# Design: repo-root swap phase (`OLD/` + promote `refactor/*` to root)

Status: approved by user, pending write of implementation plan.
Related: `refactor/REFACTOR_LOG.md` (all prior entries — data layer, `api/`,
`frontend/` phases), `refactor/CLAUDE.md`, `docs/superpowers/specs/
2026-08-04-refactor-api-phase-design.md`, `docs/superpowers/specs/
2026-08-05-refactor-frontend-phase-design.md`.

## Context

`refactor/` was built incrementally as "the future clean root of
MLOsMetaDB" (per `refactor/CLAUDE.md`'s own framing since the first
commit). The data-layer phase, the `api/` phase, and the `frontend/` phase
are all complete and verified on branch `audit/full-repo-review`. This spec
covers the final structural step: making `refactor/` stop being a
subdirectory and become the actual repo root, with everything it superseded
retired to `OLD/`.

Unlike every prior phase, this is not a port of one subsystem — it is a
pure structural relocation across the whole repo. No application code
changes; no new features. The only category of change this phase permits
is: moving directories/files, and bringing "living" documentation (not
historical narrative) up to date with the new paths.

## Scope decision

**Two `git mv` passes, strictly ordered** (root paths must be vacated before
`refactor/*` can occupy them):

1. **Retire, uncurated.** Every current root-level item that predates
   `refactor/` moves into `OLD/` verbatim, via `git mv`, preserving history:
   `api/`, `frontend/`, `database/`, `scripts/`, `parsers/`, `BIOLOGY.md`,
   `SCHEMA.md`, `CLAUDE_db.md`, `CLAUDE_features.md`, `CLAUDE_orthologs.md`,
   `CLAUDE_ppi_orthologs.md`, `integrate.py`, `fetch_interpro.log`,
   `stats.json`, `README.md`. No file is individually judged for deletion in
   this pass, even ones already confirmed dead (e.g. `fetch_interpro.log`) —
   uniform, low-risk treatment now; any cleanup of `OLD/` is a separate,
   later, explicitly-not-this-phase decision.
2. **Promote.** Every item under `refactor/` moves up one level to become a
   root-level item, via `git mv`: `api/`, `frontend/`, `database/`,
   `scripts/`, `parsers/`, `BIOLOGY.md`, `SCHEMA.md`, `DEVLOG.md`,
   `REFACTOR_LOG.md`, `policy.py`, `tests/`. `refactor/CLAUDE.md` is
   gitignored (the repo's bare `CLAUDE.md` rule, `REFACTOR_LOG.md` Entry 9)
   and therefore untracked — it moves with a plain `mv`, not `git mv` (which
   requires a tracked source). After both passes, `refactor/` should contain
   only `__pycache__` (a build artifact, discarded, never moved).

**`docs/` does not move.** It documents the refactor process itself (specs,
plans), not retired application code — it stays at the root, in place,
through both passes.

**Explicitly out of scope** (do not touch in this phase):
- Deleting anything from `OLD/`, including the ~20GB of gitignored
  `cache/`/`crossref/`/`raw/` data now duplicated between the old and
  promoted `database/` trees. `git mv` is a rename, not a copy — this
  duplication already exists today (nothing in this phase increases disk
  usage) — whether to eventually delete the `OLD/` copies is a separate,
  later, low-urgency decision.
- Rewriting `docs/superpowers/specs/*.md` or `docs/superpowers/plans/*.md`
  — these describe decisions made when `refactor/`-prefixed paths were
  correct at the time. They remain historical snapshots, understood in
  context. Same treatment for `REFACTOR_LOG.md`'s and `DEVLOG.md`'s
  *existing* entries — per `REFACTOR_LOG.md`'s own stated principle
  ("written incrementally... not reconstructed afterward"), past entries
  are not retroactively rewritten to drop the prefix; a **new** entry
  documents the swap itself and states explicitly that entries after it
  drop the `refactor/` prefix, so a future reader isn't confused by the
  shift mid-log.
- Any code or behavioral change beyond what moving directories requires.
  This phase does not fix bugs, add features, or refactor logic.

**What must be brought fully up to date** ("living" docs, not historical
narrative): the root `CLAUDE.md` and every per-directory `CLAUDE.md`
(`api/CLAUDE.md`, `database/CLAUDE.md`, `scripts/CLAUDE.md`,
`parsers/CLAUDE.md`, `frontend/CLAUDE.md`), `BIOLOGY.md`, `SCHEMA.md`, and a
newly-written `README.md` (today's root `README.md` — itself about to move
to `OLD/` — is a two-line stub, "[Completar]"). These describe *current*
structure/conventions, so every `refactor/`-prefixed path reference in them
must be corrected to drop the prefix, and any claim that assumed the old
root layout (e.g. `refactor/CLAUDE.md`'s directory maps, "Where to look"
tables) must reflect the new one.

## Why this is expected to require zero code changes

Every prior phase's port step (`api/`'s `config.py` `DB_PATH`,
`frontend/`'s `vite.config.js` `outDir`/proxy target, every pipeline
script's `ROOT = Path(__file__).resolve().parent.parent`) resolved
correctly with **zero edits** purely because paths are computed relative to
`__file__`, not hardcoded — moving the whole tree one level shallower (from
`refactor/x/y` to `x/y`) preserves every one of those relative relationships
exactly the same way moving it one level deeper (from `x/y` to
`refactor/x/y`) did going the other direction. The implementation plan must
still *verify* this by booting each service post-move (this has held every
time so far, but "expected" is not "verified") — not add path-fixups
preemptively where none are needed.

## Verification plan

Following this project's established test-before-batch /
verification-before-completion conventions:

- Before any `git mv`, snapshot the current `git status` (must be clean)
  and confirm `refactor/database/{cache,crossref,raw}` really are ordinary
  directories, not symlinks (already confirmed in this session: real
  duplicated data, ~5.5GB/~14GB/~32MB on both sides).
- Immediately after each `git mv` of a directory containing both tracked
  and gitignored content (`database/`, `frontend/` with its
  `node_modules/`), confirm via `git status`/`ls` that the gitignored
  subdirectories physically moved along with the tracked files (a `git mv`
  on a mixed directory is expected to move the whole tree at the filesystem
  level and update the index only for tracked paths — verify this
  assumption on the first such move rather than trusting it for all of
  them unchecked).
- Run the existing `pytest` suites (`tests/`, `api/tests/`) against the
  promoted, unprefixed paths.
- Boot `api/` (`uvicorn main:app`) from its new root-level location and
  confirm `/stats` responds correctly against the promoted
  `database/mlosmetadb.db`.
- Ask the user to run `npm install`/`npm run dev` in the promoted
  `frontend/` (Claude never runs `npm`, per established project
  convention) and confirm the app still works end-to-end against the
  promoted `api/`.
- Confirm `.gitignore`'s patterns still correctly ignore
  `database/mlosmetadb.db`, `database/cache/`, `database/crossref/`,
  `database/raw/`, `database/interim/*.tsv`, `api/static/`,
  `frontend/node_modules/`, etc. at their new (unprefixed) locations, and
  that the now-redundant `refactor/database/...` mirror block and any other
  stale entries (e.g. the duplicated `frontend/DEVLOG.md` ignore line) are
  removed.
- Confirm `git log --follow` on a handful of representative moved files
  (e.g. the promoted `api/main.py`, the retired `OLD/frontend/App.vue`)
  still shows history through the move, proving `git mv` preserved
  provenance rather than appearing as a delete+add.

## Docs to update

- New `README.md` at the root (real content — project overview, how to run
  the API/frontend, pointers to `CLAUDE.md`/`BIOLOGY.md`/`SCHEMA.md`).
- Root `CLAUDE.md` (promoted from `refactor/CLAUDE.md`): directory map,
  "Where to look" table, and cross-project conventions section all lose
  the `refactor/` prefix and any "later phase" framing that no longer
  applies now that every phase is complete.
- `api/CLAUDE.md`, `frontend/CLAUDE.md`, `database/CLAUDE.md`,
  `scripts/CLAUDE.md`, `parsers/CLAUDE.md`: path references corrected.
- `REFACTOR_LOG.md`: new final entry documenting the swap itself (what
  moved where, verification evidence, the path-prefix note above). Past
  entries untouched.
- `refactor/frontend/DEVLOG.md`/`DEVLOG.md` at root: a short final line
  noting the promotion, consistent with how it already documents its own
  port.

## Out of scope for this phase

- Deleting `OLD/` contents (including the duplicated cache/crossref/raw
  data) — separate, later decision.
- Rewriting `docs/superpowers/specs/*.md`/`docs/superpowers/plans/*.md` or
  `REFACTOR_LOG.md`'s/`DEVLOG.md`'s existing entries.
- Any application code/behavior change.
- The `main` merge decision — handled via `finishing-a-development-branch`
  once this phase's own work is verified complete, same pattern as the
  `frontend/` phase. This phase runs on a new branch (`swap-to-root`,
  forked from `audit/full-repo-review`) specifically so
  `audit/full-repo-review` remains an intact rollback point until that
  merge decision is made.
