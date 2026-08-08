# Repo-Root Swap Phase Implementation Plan

> **Correction (2026-08-08).** This document treats `PhaseDB` and `PhasePDB`
> as two source databases (or counts six sources where there are five). They
> were two ingestion tags for one resource, **PhaSepDB**, whose two parsers
> read byte-identical copies of the same export files — so every PhaSepDB
> annotation was loaded twice. The document is left as written because it
> records a past design decision; the tags no longer exist in the data. See
> `docs/issues/001-phasedb-phasepdb-duplicate-ingestion.md`.


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire everything at the repo root that predates `refactor/` into `OLD/`, then promote `refactor/`'s contents to become the actual repo root — a pure structural relocation, no application code or behavior changes — and bring every "living" doc up to date with the dropped `refactor/` prefix.

**Architecture:** Two strictly-ordered `git mv` passes (retire, then promote — root paths must be vacated before `refactor/*` can occupy them), each immediately paired with the `.gitignore` edit it requires to keep `git status` clean (heavy gitignored data trees would otherwise become visible/untracked the moment their containing directory moves, since the relevant patterns are root-anchored). No code is touched — every path in this codebase is resolved relative to `__file__`, which is exactly why every prior phase's port step needed zero path fixups, and why this one shouldn't either; that assumption gets verified, not assumed, in Task 3.

**Tech Stack:** `git mv` / plain `mv` for the relocation itself; `pytest` and a manual `uvicorn`/`curl` boot check for verification (no code changes are expected, so there's nothing to TDD in the usual sense — every task's "test" is a verification command against the moved tree).

## Global Constraints

- **Strict ordering**: the retire pass (Task 1) must complete before the promote pass (Task 2) — `api`, `frontend`, `database`, `scripts`, `parsers`, and the root `.md` files all need their current root slot vacated before `refactor/`'s versions can take it.
- **`docs/` never moves.** It documents the refactor process itself, not retired application code.
- **No individual curation during the retire pass.** Every current root-level item (including ones already known to be dead, like `fetch_interpro.log`) moves to `OLD/` uniformly. No deletions in this phase.
- **No deleting anything from `OLD/`** in this phase, including the ~20GB of gitignored `cache/`/`crossref/`/`raw/` data that ends up duplicated between `OLD/database/` and the promoted `database/` — `git mv` is a rename (no extra disk used; this duplication already exists today, just under different names). That's a separate, later, explicitly out-of-scope decision.
- **No rewriting historical docs.** `docs/superpowers/specs/*.md`, `docs/superpowers/plans/*.md`, and every *existing* entry in `REFACTOR_LOG.md`/`DEVLOG.md` describe decisions made when `refactor/`-prefixed paths were correct at the time — they are not retroactively edited. Only a **new** `REFACTOR_LOG.md` entry (Task 5) documents this phase, explicitly noting that entries after it drop the prefix.
- **"Living" docs must be 100% accurate post-swap**: the root `CLAUDE.md`, every per-directory `CLAUDE.md` (`api/`, `database/`, `scripts/`, `parsers/`, `frontend/`), `BIOLOGY.md`, `SCHEMA.md`, and a newly-written `README.md`. Every `refactor/`-prefixed path reference in these must be corrected.
- **No application code or behavior changes anywhere in this plan.** If Task 3's verification finds a path that *doesn't* resolve correctly post-move, stop and report it rather than "fixing" it as if it were expected — that would be a real, unplanned finding, not a scripted step.
- **Claude never runs `npm`** (established project convention) — Task 6 asks the user to run it.

---

## File Structure

This phase creates and deletes directories rather than files with new responsibilities — there's no new "file structure" to design. The end state is:

```
<repo-root>/
├── OLD/                    # NEW — everything retired in Task 1, verbatim
│   ├── api/  frontend/  database/  scripts/  parsers/
│   ├── BIOLOGY.md  SCHEMA.md  README.md  integrate.py
│   ├── CLAUDE_db.md  CLAUDE_features.md  CLAUDE_orthologs.md  CLAUDE_ppi_orthologs.md
│   ├── fetch_interpro.log  stats.json
├── api/                    # PROMOTED from refactor/api/ (Task 2)
├── frontend/                # PROMOTED from refactor/frontend/ (Task 2)
├── database/                # PROMOTED from refactor/database/ (Task 2)
├── scripts/                 # PROMOTED from refactor/scripts/ (Task 2)
├── parsers/                 # PROMOTED from refactor/parsers/ (Task 2)
├── tests/                    # PROMOTED from refactor/tests/ (Task 2)
├── policy.py                 # PROMOTED from refactor/policy.py (Task 2)
├── BIOLOGY.md  SCHEMA.md  DEVLOG.md  REFACTOR_LOG.md  CLAUDE.md   # PROMOTED (Task 2), edited (Tasks 4-5)
├── README.md                # NEW content (Task 4) — old stub retired to OLD/README.md
├── docs/                     # UNCHANGED location (never moves)
├── .gitignore                 # EDITED (Tasks 1 and 2)
# refactor/ no longer exists after Task 2
```

---

### Task 1: Retire pass — `git mv` current root into `OLD/`

**Files:**
- Create: `OLD/` (new directory, populated entirely via `git mv`)
- Modify: `.gitignore` (add `OLD/` mirror patterns for heavy gitignored data)

**Interfaces:**
- Produces: a repo root with `OLD/api/`, `OLD/frontend/`, `OLD/database/`, `OLD/scripts/`, `OLD/parsers/`, and the ten retired root files, all still git-tracked at their new paths; `refactor/` completely untouched (Task 2's job).

- [ ] **Step 1: Pre-flight checks**

```bash
cd <repo-root>
git status --short
```

Expected: empty output (clean tree). If anything is dirty, stop and ask before proceeding — do not stash or discard without checking what it is first.

```bash
git branch --show-current
```

Expected: `audit/full-repo-review` (or whatever the current branch is — confirm it's the one this phase is meant to fork from, per the design spec).

```bash
ls -la database/cache database/crossref database/raw | head -5
du -sh database/cache database/crossref database/raw
```

Expected: ordinary directories (permissions starting `d`, not `l` for symlink), sizes approximately 5.5G / 14G / 32M — confirms the assumption the design spec's verification plan calls out explicitly (already checked once this session, re-confirm now since a fresh implementer is starting cold).

- [ ] **Step 2: Create the branch**

```bash
git checkout -b swap-to-root
```

- [ ] **Step 3: Verify `git mv` on a mixed tracked/gitignored directory before doing the rest**

Pick the largest, highest-risk directory (`database/`, which has both tracked small files and gitignored multi-GB subdirectories) and move it first, alone, to confirm the assumption in the design spec's verification plan — that `git mv` on a directory moves the *entire* filesystem tree (tracked and gitignored content alike) and updates the index only for the tracked paths:

```bash
mkdir OLD
git mv database OLD/database
git status --short | head -20
```

Expected: `git status` shows renames for the small number of tracked files (roughly 34, matching `git ls-files -- database | wc -l` counted before the move) as `R  database/X -> OLD/database/X`, and critically shows **no untracked files** for `OLD/database/cache/`, `OLD/database/crossref/`, `OLD/database/raw/`, `OLD/database/*.db` — because those are still matched by the *old* `.gitignore` patterns (`database/cache/` etc.), which are root-anchored and don't yet match the new `OLD/database/...` location... **wait, they won't match the new location, so this check will actually show a large number of untracked files at this point** — that's expected and is exactly what Step 4 fixes. Don't be alarmed by it; just confirm the *directories and their contents physically exist* at the new path:

```bash
ls OLD/database/cache | wc -l
ls OLD/database/crossref | wc -l
du -sh OLD/database/cache OLD/database/crossref OLD/database/raw
```

Expected: non-zero file counts, and the same ~5.5G / 14G / 32M sizes as Step 1 — confirms the physical move happened correctly for gitignored content, not just the tracked files.

- [ ] **Step 4: Immediately add `OLD/` mirror `.gitignore` patterns for `database/`'s heavy content**

This must happen before moving anything else, and before ever running a broad `git status`/`git add` — otherwise `OLD/database/cache/`, `OLD/database/crossref/`, `OLD/database/raw/` (20GB) sit untracked-and-unignored, one accidental `git add -A` away from a catastrophic commit.

In `.gitignore`, find this existing block (search for `refactor/database/mlosmetadb.db`):

```
# --- refactor/ data layer: same heavy/generated files, mirrored ---
# (patterns above are anchored to the repo-root database/, NOT recursive --
#  a mid-pattern slash makes a gitignore rule root-relative -- so refactor/'s
#  copies need their own entries)
refactor/database/mlosmetadb.db
refactor/database/*.db
refactor/database/cache/
refactor/database/crossref/
refactor/database/raw/
refactor/database/interim/*.tsv
# Trailing-slash patterns above never match a symlink (even one pointing
# to a directory) -- worktrees set up for this refactor symlink cache/,
# crossref/, raw/ back to the main checkout's copy, so mirror each as a
# no-trailing-slash pattern too, or `git add -A` would stage the symlinks.
refactor/database/cache
refactor/database/crossref
refactor/database/raw
```

Immediately after it, add a new block (this one is temporary — Task 2 removes the `refactor/database/...` block above entirely once `refactor/` stops existing, but this new `OLD/database/...` block stays, since `OLD/` is permanent for this phase):

```
# --- OLD/ retired database/: same heavy/generated files, mirrored ---
# (root-anchored patterns above don't match OLD/database/... either --
#  same reasoning as the refactor/ block above)
OLD/database/mlosmetadb.db
OLD/database/*.db
OLD/database/cache/
OLD/database/crossref/
OLD/database/raw/
OLD/database/interim/*.tsv
```

(No symlink-mirror no-trailing-slash variants needed here — those existed only because a worktree symlinked `cache/`/`crossref/`/`raw/` back to the main checkout; `OLD/database/` holds real directories, not symlinks, per Step 1's confirmation.)

- [ ] **Step 5: Verify Step 4's edit worked, then move the rest of the root**

```bash
git status --short
```

Expected: only the `database/` renames from Step 3 show up now (as clean `R` renames, no stray untracked heavy directories) — confirms the new `.gitignore` block is effective before proceeding.

```bash
git mv api OLD/api
git mv frontend OLD/frontend
git mv scripts OLD/scripts
git mv parsers OLD/parsers
git mv BIOLOGY.md OLD/BIOLOGY.md
git mv SCHEMA.md OLD/SCHEMA.md
git mv CLAUDE_db.md OLD/CLAUDE_db.md
git mv CLAUDE_features.md OLD/CLAUDE_features.md
git mv CLAUDE_orthologs.md OLD/CLAUDE_orthologs.md
git mv CLAUDE_ppi_orthologs.md OLD/CLAUDE_ppi_orthologs.md
git mv integrate.py OLD/integrate.py
git mv stats.json OLD/stats.json
git mv README.md OLD/README.md
mv fetch_interpro.log OLD/fetch_interpro.log
```

`fetch_interpro.log` uses plain `mv`, not `git mv` — it's untracked (matches the `*.log` gitignore pattern; confirmed via `git ls-files -- fetch_interpro.log` returning nothing), and `git mv` refuses untracked sources.

Also check for a possible `api/static/` leftover (an old frontend build's output, gitignored, root-anchored pattern `api/static/`) — this one similarly needs an `OLD/` mirror since it has real content (`assets/`, `favicon.ico`):

```bash
ls OLD/api/static/ 2>&1
```

If it shows real files (expected, per this session's own check earlier), add one more line to the `OLD/` mirror block from Step 4:

```
OLD/api/static/
```

- [ ] **Step 6: Verify the full retire pass**

```bash
git status --short
```

Expected: a clean list of `R` (rename) entries for every tracked file that moved, plus the `.gitignore` modification, and **no untracked entries at all** (confirming the `OLD/` mirror patterns cover everything heavy). If any untracked heavy directory appears, stop and add the missing pattern before continuing — do not commit with untracked multi-GB content sitting in the working tree.

```bash
ls <repo-root>
```

Expected: `OLD/`, `docs/`, `refactor/`, `.gitignore`, and the dotfiles (`.claude/`, `.git/`, `.mcp.json`, `.pytest_cache/`, `.superpowers/`, `.worktrees/`) — nothing else. Every application directory/file that used to sit at the root is now gone from view (moved into `OLD/`).

```bash
git log --follow --oneline -3 -- OLD/api/main.py
```

Expected: shows commit history predating this phase (e.g. entries about the original `api/` build), proving `git mv` preserved provenance rather than registering as a delete+add.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: retire pre-refactor root (api/, frontend/, database/, scripts/,
parsers/, and loose root docs) into OLD/

First of two passes for the repo-root swap (see
docs/superpowers/specs/2026-08-06-repo-root-swap-design.md). Everything at
the repo root that predates refactor/ moves into OLD/ uncurated via git mv
-- including files already known to be dead (fetch_interpro.log,
integrate.py) -- no individual curation in this pass, no deletions.

.gitignore gained an OLD/database/... mirror block (same reasoning as the
existing refactor/database/... block this repo has carried since the api/
phase, Entry 9): root-anchored gitignore patterns don't follow a directory
when it moves, so the ~20GB of cache/crossref/raw data would otherwise
sit untracked-and-unignored the moment database/ became OLD/database/.

The refactor/ directory itself is untouched -- promoting it to the actual
root is Task 2, which must happen after this pass vacates the root paths
it needs to occupy.
EOF
)"
```

---

### Task 2: Promote pass — `git mv refactor/*` up to become the root

**Files:**
- Modify: `.gitignore` (remove the now-obsolete `refactor/database/...` mirror block and other stale entries)
- Delete: `refactor/` (once empty)

**Interfaces:**
- Consumes: a repo root vacated by Task 1 (no path collisions).
- Produces: `api/`, `frontend/`, `database/`, `scripts/`, `parsers/`, `tests/`, `policy.py`, `BIOLOGY.md`, `SCHEMA.md`, `DEVLOG.md`, `REFACTOR_LOG.md`, `CLAUDE.md` all sitting directly at the repo root, git history intact; `refactor/` no longer exists.

- [ ] **Step 1: Confirm Task 1 landed and the root is clear to receive `refactor/*`**

```bash
git status --short
```

Expected: empty (Task 1's commit is clean). If not, stop.

```bash
ls <repo-root>
```

Expected: `OLD/`, `docs/`, `refactor/`, dotfiles, `.gitignore` — confirms no `api`/`frontend`/`database`/`scripts`/`parsers`/`BIOLOGY.md`/etc. remain at the root to collide with what's about to move in.

- [ ] **Step 2: Move everything up one level**

```bash
git mv refactor/api api
git mv refactor/frontend frontend
git mv refactor/database database
git mv refactor/scripts scripts
git mv refactor/parsers parsers
git mv refactor/BIOLOGY.md BIOLOGY.md
git mv refactor/SCHEMA.md SCHEMA.md
git mv refactor/DEVLOG.md DEVLOG.md
git mv refactor/REFACTOR_LOG.md REFACTOR_LOG.md
git mv refactor/policy.py policy.py
git mv refactor/tests tests
mv refactor/CLAUDE.md CLAUDE.md
```

`refactor/CLAUDE.md` uses plain `mv` — it's untracked (this repo's bare `CLAUDE.md` gitignore rule, `REFACTOR_LOG.md` Entry 9; confirmed via `git ls-files -- refactor/CLAUDE.md` returning nothing), and `git mv` refuses untracked sources.

- [ ] **Step 3: Clean up and remove the now-empty `refactor/` directory**

```bash
rm -rf refactor/__pycache__
ls -la refactor/
```

Expected: empty (or only `.` and `..`). If anything else remains, stop and investigate what it is before deleting — it may be something the plan's file inventory missed.

```bash
rmdir refactor
```

- [ ] **Step 4: Remove the now-obsolete `.gitignore` block and other stale entries**

Delete this entire block (it referred to `refactor/database/`, which no longer exists):

```
# --- refactor/ data layer: same heavy/generated files, mirrored ---
# (patterns above are anchored to the repo-root database/, NOT recursive --
#  a mid-pattern slash makes a gitignore rule root-relative -- so refactor/'s
#  copies need their own entries)
refactor/database/mlosmetadb.db
refactor/database/*.db
refactor/database/cache/
refactor/database/crossref/
refactor/database/raw/
refactor/database/interim/*.tsv
# Trailing-slash patterns above never match a symlink (even one pointing
# to a directory) -- worktrees set up for this refactor symlink cache/,
# crossref/, raw/ back to the main checkout's copy, so mirror each as a
# no-trailing-slash pattern too, or `git add -A` would stage the symlinks.
refactor/database/cache
refactor/database/crossref
refactor/database/raw
```

Also search for and remove other now-stale duplication while you're in this file (read the whole file — it's not long): a second, duplicate `.mcp.json` entry, and two duplicate `frontend/DEVLOG.md` lines (both predate this phase; `frontend/DEVLOG.md` should actually stay gitignored-nowhere, since the promoted `frontend/DEVLOG.md` is deliberately git-tracked — confirm via `git ls-files -- frontend/DEVLOG.md` returning a match after this task's moves, and if a `frontend/DEVLOG.md` ignore line is still present, remove it: an ignore rule doesn't untrack an already-tracked file, but it's misleading dead weight to leave in place).

Leave the base (non-`refactor/`, non-`OLD/`) `database/...`/`frontend/...`/`api/static/` patterns exactly as they are — they're root-anchored and now correctly apply to the *promoted* `database/`/`frontend/`/`api/` directories automatically, with zero edits needed (same "resolves correctly one level shallower" reasoning as the code paths in Task 3).

- [ ] **Step 5: Verify**

```bash
git status --short
```

Expected: clean `R` renames for every moved file, the `.gitignore` edit, and no untracked heavy content (the promoted `database/cache/`/`crossref/`/`raw/` should already be correctly ignored by the base patterns Step 4 left untouched — confirm this explicitly):

```bash
git status --short | grep -c "^??" # should be 0, or only trivial/expected entries
du -sh database/cache database/crossref database/raw
```

Expected: same ~5.5G/14G/32M sizes, now correctly ignored (not appearing as `??` in git status).

```bash
git log --follow --oneline -3 -- api/main.py
```

Expected: shows history from the `refactor/api/` phase (e.g. the port commit, schema-drift fixes) — confirms provenance survived the second move too.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: promote refactor/*'s contents to the repo root

Second of two passes (see
docs/superpowers/specs/2026-08-06-repo-root-swap-design.md). Everything
under refactor/ (api/, frontend/, database/, scripts/, parsers/, tests/,
policy.py, BIOLOGY.md, SCHEMA.md, DEVLOG.md, REFACTOR_LOG.md, CLAUDE.md)
moves up one level to become the actual root, now that Task 1's retire
pass vacated every path it needs. refactor/ no longer exists.

.gitignore's refactor/database/... mirror block (added during the api/
phase, Entry 9) is removed -- refactor/ is gone, so it's dead. The base
(non-prefixed) database/.../frontend/.../api/static/ patterns are left
untouched: they're root-anchored and now correctly apply to the promoted
directories with zero edits, same reasoning as every path-resolving
script in this codebase (see Task 3).
EOF
)"
```

---

### Task 3: Verify path-resolution — confirm zero code changes are needed

**Files:** none expected to change. This task is pure verification; if it finds something that needs a code change, STOP and report rather than silently fixing it (per Global Constraints — an actual path-resolution failure here would be a real, unplanned finding).

**Interfaces:**
- Consumes: the promoted tree from Task 2.
- Produces: confidence (with evidence) that the design spec's "expected to require zero code changes" claim holds, before any docs get rewritten against a structure that might not actually work yet.

- [ ] **Step 1: Run the Python test suites from the new root**

```bash
cd <repo-root>
python3 -m pytest tests/ api/tests/ -q
```

Expected: same pass count as before this phase (16 in `api/tests/` + 8 in `tests/` = 24, per the frontend phase's own final `pytest` run — confirm this matches; if the count differs, something about the move broke test discovery or an import, and that's a real finding to report, not to silently patch around).

- [ ] **Step 2: Boot the API from its new root-level location**

```bash
cd <repo-root>/api
python3 -c "from config import DB_PATH; print(DB_PATH)"
```

Expected: an absolute path ending in `<repo-root>/database/mlosmetadb.db` — **with no `refactor/` anywhere in it**. This is the exact check the `api/` phase itself ran after its own port (Entry 11) and after the `frontend/` phase's port (this session) — same reasoning, one level shallower now.

```bash
python3 -c "from config import _REFACTOR_ROOT; print(_REFACTOR_ROOT)"
```

Expected: prints `<repo-root>` itself (the variable name is stale now — it says `_REFACTOR_ROOT` but there's no `refactor/` anymore; leave the *value* correct for this verification step, note the stale *name* as a candidate rename, but do not rename it in this task — Task 4 handles doc/naming cleanup, and renaming a variable referenced by both `config.py` and every file under `api/queries/`/`api/routers/` that imports `policy` through it is a code change, explicitly out of scope for this plan).

```bash
nohup python3 -m uvicorn main:app --host 127.0.0.1 --port 8765 > /tmp/swap-verify-api.log 2>&1 &
sleep 4
curl -s --noproxy '*' "http://127.0.0.1:8765/stats" | python3 -c "import json,sys; print(json.load(sys.stdin)['proteins']['total'])"
```

Expected: `15879` (or whatever the current real count is — confirm it matches what `GET /stats` returned before this phase, via `git log`/the frontend phase's own verification evidence if you need a reference number). Use `--noproxy '*'` — this environment's `HTTP_PROXY`/`HTTPS_PROXY` breaks plain `127.0.0.1` requests otherwise.

```bash
pkill -f "uvicorn main:app.*8765"
```

- [ ] **Step 3: No commit for this task** — it's a verification-only gate. If everything above passed, proceed to Task 4. If anything failed, stop and report the specific failure (file, expected vs. actual) rather than guessing at a fix.

---

### Task 4: Update living docs + write a real `README.md`

**Files:**
- Modify: `CLAUDE.md` (root), `api/CLAUDE.md`, `database/CLAUDE.md`, `scripts/CLAUDE.md`, `parsers/CLAUDE.md`, `frontend/CLAUDE.md`, `BIOLOGY.md`, `SCHEMA.md`
- Create: `README.md` (root — the retired stub is now `OLD/README.md`)

**Interfaces:**
- Consumes: the verified-working promoted tree from Task 3.
- Produces: docs that accurately describe the repo as it now stands — no consumer beyond human readers and future Claude sessions.

- [ ] **Step 1: Find every remaining `refactor/` reference in the living docs**

```bash
grep -rn "refactor/" CLAUDE.md api/CLAUDE.md database/CLAUDE.md scripts/CLAUDE.md parsers/CLAUDE.md frontend/CLAUDE.md BIOLOGY.md SCHEMA.md
```

This is your worklist. For each match, read enough surrounding context to understand what it's claiming, then fix it against the *actual current* file layout (verify with `ls`/`cat`, don't guess) — common patterns you'll hit:
- Directory maps and "Where to look" tables showing a path like `refactor/api/CLAUDE.md` → becomes `api/CLAUDE.md`.
- Prose like "`refactor/policy.py` lives one level up" (from `api/CLAUDE.md`, describing where `policy.py` sits relative to `api/`) — the *relationship* ("one level up from `api/`") is still true after promotion, since `policy.py` and `api/` are still siblings-of-the-same-parent; only the word `refactor/` needs to go, not the sentence's substance.
- Root `CLAUDE.md`'s directory map currently shows `refactor/` as a subdirectory tree with an inner nested structure — the whole nested-tree framing goes away; the map should show `api/`, `frontend/`, `database/`, `scripts/`, `parsers/`, `tests/`, `policy.py`, `BIOLOGY.md`, `SCHEMA.md`, `DEVLOG.md`, `REFACTOR_LOG.md`, `CLAUDE.md`, `docs/` as flat top-level entries.
- Any "later phase"/"doesn't exist yet" framing (e.g. root `CLAUDE.md` likely still has old leftover language about `frontend/` being a separate future phase, or about `refactor/` itself being incremental/future work) — this repo has no more phases pending after this one; drop language that frames anything as not-yet-built.

- [ ] **Step 2: Confirm zero `refactor/` references remain (except inside verbatim historical quotes)**

```bash
grep -rn "refactor/" CLAUDE.md api/CLAUDE.md database/CLAUDE.md scripts/CLAUDE.md parsers/CLAUDE.md frontend/CLAUDE.md BIOLOGY.md SCHEMA.md
```

Expected: no output, OR only lines that are explicitly quoting historical text (e.g. a "See Entry 11" pointer that itself quotes an old path inside a code block describing what a past command's output looked like) — use judgment, but the bar is that nothing describing *current* structure still says `refactor/`.

- [ ] **Step 3: Write `README.md`**

Base content (adapt exact numbers/links to what's actually true after you've read the current `CLAUDE.md`/`BIOLOGY.md`/`SCHEMA.md` — don't invent facts, pull them from those files):

```markdown
# MLOsMetaDB

A meta-database unifying protein annotations from six source databases
(PhaseDB, PhasePDB, DrLLPS, LLPSDB, PhasePro, CD-CODE) related to
liquid-liquid phase separation (LLPS) and membraneless organelles (MLOs),
enriched with UniProt metadata, InterPro/MobiDB sequence features, BioGRID
protein-protein interactions, and OMA orthologs.

Serves `mlos.leloir.org.ar`'s public REST API and SPA frontend.

## Structure

- `api/` — FastAPI backend. See `api/CLAUDE.md`.
- `frontend/` — Vue 3 SPA. See `frontend/CLAUDE.md`.
- `database/` — data, mappings, cache, the built SQLite DB. See `database/CLAUDE.md`.
- `scripts/` — fetch/parse/build pipeline. See `scripts/CLAUDE.md`.
- `parsers/` — per-source raw-to-interim parsers. See `parsers/CLAUDE.md`.
- `policy.py` — shared serving policy (`dataset_active` filtering, MLO category exclusion), imported by both `api/` and `scripts/build_summary.py`.
- `BIOLOGY.md` — biological classification rules (driver/client, MLO mapping decisions).
- `SCHEMA.md` — full database schema.
- `CLAUDE.md` — start here for anything not covered above.
- `REFACTOR_LOG.md` — narrative history of how this repo reached its current structure.
- `OLD/` — the pre-refactor codebase, retired. Nothing here is depended on by anything current.

## Running it

```bash
cd api && python3 -m uvicorn main:app --host 127.0.0.1 --port 8765
cd frontend && npm install && npm run dev
```

See `api/CLAUDE.md` and `frontend/CLAUDE.md` for details (in-memory DB load,
API contract, frontend conventions).

## Contact

See `CLAUDE.md`'s footer / the frontend's About page for citation and
contact details.
```

Adjust the "Contact"/citation section against what `frontend/CLAUDE.md` or the frontend's actual footer/About page content says (pull the real citation/contact info you find there — don't leave it as a vague pointer if the real text is short enough to inline).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md api/CLAUDE.md database/CLAUDE.md scripts/CLAUDE.md parsers/CLAUDE.md frontend/CLAUDE.md BIOLOGY.md SCHEMA.md README.md
git commit -m "$(cat <<'EOF'
docs: drop refactor/ prefix from living docs, write a real README.md

Every CLAUDE.md (root and per-directory), BIOLOGY.md, and SCHEMA.md
still referenced the refactor/-prefixed paths that stopped existing in
Task 2 -- corrected every occurrence against the actual current layout,
not just search-and-replaced blindly. root README.md was a two-line
"[Completar]" stub (now retired to OLD/README.md); replaced with real
project-overview content pulled from CLAUDE.md/BIOLOGY.md/SCHEMA.md.

Per this plan's Global Constraints: docs/superpowers/specs/*.md,
docs/superpowers/plans/*.md, and REFACTOR_LOG.md's/DEVLOG.md's existing
entries are NOT touched here -- they're historical narrative, not living
reference docs.
EOF
)"
```

---

### Task 5: `REFACTOR_LOG.md` new entry + `DEVLOG.md` note

**Files:**
- Modify: `REFACTOR_LOG.md` (append new entry — the last one; do not edit any existing entry)
- Modify: `DEVLOG.md`

**Interfaces:**
- Consumes: verification evidence from Tasks 1-4 (commit SHAs, `pytest`/`curl` output, the `git log --follow` provenance checks).
- Produces: the durable record of this phase, in the same narrative style as every prior entry.

- [ ] **Step 1: Append the new `REFACTOR_LOG.md` entry**

Read the file's last 2-3 entries first for tone/format (concrete before/after evidence, real command output, honest disclosure of anything that didn't go as planned — same as every entry so far). Write a new entry covering:
- What moved where (both passes), with the exact `git mv` command groups from Tasks 1-2.
- The `OLD/` `.gitignore` mirror addition and why (the root-anchored-pattern hazard, same shape as the `refactor/database/...` mirror this log already documented once before).
- Task 3's verification evidence verbatim (the `pytest` pass count, the `DB_PATH` print, the `/stats` count).
- Task 4's doc corrections, summarized (which files, roughly how many `refactor/` references each had).
- **An explicit statement**: "Entries above this one predate the swap and correctly use `refactor/`-prefixed paths for what was true when they were written — they are not rewritten. Entries from here on describe the promoted, unprefixed layout."
- Any incident encountered during Tasks 1-4 that didn't go exactly as this plan predicted, disclosed in full — matching every prior entry's own standard (e.g. Entry 9's `.gitignore` incident, Entry 12's wrong-script incident).

- [ ] **Step 2: Add a short `DEVLOG.md` note**

One or two lines, same terse style as its existing entries, pointing at the new `REFACTOR_LOG.md` entry for detail.

- [ ] **Step 3: Commit**

```bash
git add REFACTOR_LOG.md DEVLOG.md
git commit -m "$(cat <<'EOF'
docs: log the repo-root swap in REFACTOR_LOG.md

New entry only -- every entry before it is untouched, per this plan's
Global Constraints. Documents both git mv passes, the .gitignore
mirror-pattern fix, and Task 3's path-resolution verification evidence.
EOF
)"
```

---

### Task 6: Frontend live verification

**Files:** none expected — verification only, same shape as Task 3.

**Interfaces:**
- Consumes: the promoted, doc-corrected tree from Tasks 1-5.
- Produces: end-to-end confidence that the SPA still works against the promoted `api/`, from a human who actually looked at it (Claude cannot run `npm`).

- [ ] **Step 1: Ask the user to boot the frontend from its new root-level location**

> "El swap está hecho — `frontend/` y `api/` ya están en la raíz del repo, no bajo `refactor/`. ¿Podés correr esto y confirmarme que anda?
> ```bash
> cd api && python3 -m uvicorn main:app --host 127.0.0.1 --port 8765
> ```
> y, en otra terminal:
> ```bash
> cd frontend && npm install && npm run dev
> ```
> Fijate que levante sin errores y que la app cargue en `localhost:5173` con datos reales — no hace falta un recorrido exhaustivo, solo confirmar que sigue funcionando igual que antes del swap."

- [ ] **Step 2: If anything is reported broken**, diagnose with the same curl-first method every prior phase used — reproduce against the real API before guessing at a fix, and if a fix is needed, treat it as a new, disclosed finding (append to the `REFACTOR_LOG.md` entry from Task 5, don't silently patch and move on).

- [ ] **Step 3: No commit for this task** unless Step 2 produced a fix, in which case commit that fix on its own with a message describing exactly what was found and changed.

---

### Task 7: Final full-branch review

**Files:** none — review only, unless it finds something.

**Interfaces:**
- Consumes: the complete diff of every commit from this plan (Tasks 1-6), compared against the design spec's Global Constraints.
- Produces: either a clean bill of health, or findings to fix before this phase is considered done — same pattern as the `api/` and `frontend/` phases' own final reviews (both of which found something a per-task review missed).

- [ ] **Step 1: Dispatch a review pass over the full diff**, checking specifically:
- Every file that was tracked before Task 1 is still tracked after Task 2, at its new path, with `git log --follow` provenance intact (spot-check beyond the two files Tasks 1-2 already checked — pick one file each from `frontend/`, `scripts/`, `parsers/`, `tests/`).
- `git status` is clean, with no untracked heavy content anywhere (`OLD/database/...`, promoted `database/...`).
- No living doc still references a `refactor/`-prefixed path (re-run Task 4 Step 2's grep).
- No historical doc (`docs/superpowers/specs/*.md`, `docs/superpowers/plans/*.md`, any `REFACTOR_LOG.md`/`DEVLOG.md` entry *before* Task 5's) was modified — `git diff <branch-start>..HEAD -- docs/superpowers/specs docs/superpowers/plans` should show no changes to pre-existing files in those directories (only new files, if any were added), and `git log -p -- REFACTOR_LOG.md` should show Task 5's commit as a pure append (no changed lines above the new entry).
- The two `.gitignore` edits (Task 1's addition, Task 2's removal) leave the file internally consistent — no dangling comment referencing a block that no longer exists, no duplicate patterns.

- [ ] **Step 2: Fix anything the review finds**, following the same curl-first (or `git`-command-first, for structural claims) verification pattern as every other task, committing each fix individually.

- [ ] **Step 3: If the review is clean, log that fact in `REFACTOR_LOG.md`'s Task 5 entry** (append to it, don't create a new one) — one sentence, e.g. "Final full-branch review (Task 7): clean, no additional findings." If it found something, describe what and how it was fixed.

- [ ] **Step 4: Commit** (only if Step 2 produced changes beyond the log update)

This is the last task of the repo-root swap phase. What happens to this branch (`swap-to-root`) next — merge to `main`, PR, or hold — is a separate decision made via `finishing-a-development-branch`, not part of this plan (per the design spec's explicit deferral).
