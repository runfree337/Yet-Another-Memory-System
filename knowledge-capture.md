# Knowledge capture — routing a method learning

> Complements `WORKFLOW.md`'s §Knowledge capture. At the closure of a work item: *did this work reveal a reusable **method** learning?*
> **The logic (steps 1–2) is agnostic**; only the **last step** (step 3: which concrete mechanism) depends on the tool → the same adapter as the framework's placement (`README.md`).
> Scope = **method / process** learning (how the team works). A *content* learning (what the project is) already goes into its architecture doc.

## 1. Is it even worth capturing? (the gate)

Don't tool by gut feel — **one verifiable trigger is enough**:

- **Repetition**: the same procedure redone **≥ 3 times**.
- **Trial and error**: the same command corrected **≥ 2 times** before it worked → capture the correct invocation.
- **Long deterministic procedure**: **≥ 5 steps**, reproducible (same input → same output).
- **Manually checked invariant**: a rule checked by hand that must *always* hold.
- **Regression**: an error already seen comes back.
- **Forgotten process step**, later caught.

**Anti-triggers (do NOT tool)**: a genuine one-off · the check requires **judgment** (→ no script, or it'll produce false positives) · maintenance cost > cumulative gain. **"Nothing to capture"** is a legitimate answer — but the question is *asked*, never skipped by default.

## 2. Which FUNCTION? (agnostic)

Classify the learning by what it should *become* — a **function**, not a tool:

| The learning is… | → Durable function |
|---|---|
| a normative, short rule/preference | **shared rule** |
| a **mechanical** invariant, checkable without judgment | **deterministic check** (zero false positive) |
| a recurring **semantic** judgment no script can settle | **review / delegation role** |
| a reusable procedure/recipe, not mechanizable | **documented recipe** |
| an invariant that must never break again | **regression test** |
| a structural choice | **decision** (`decisions/`) |
| personal, machine-local | **personal memory** (outside the repo) |
| a hole in the method itself | **improve the protocol concerned** |

> Several functions at once are possible (e.g. a deterministic check **+** the rule it protects). The lightest home that actually captures the learning wins.

## 3. Mapping the function to a mechanism (the ONLY tool-specific step)

| Function | Claude Code | GitHub Copilot | Other agent |
|---|---|---|---|
| documented recipe | skill | prompt file | doc / context file |
| deterministic check | script + hook (auto) | script + CI job | script + your scheduler |
| review / delegation role | subagent | chat mode | dedicated role / prompt |
| shared rule | `CLAUDE.md` / `.claude/rules/` | `copilot-instructions` / `.github/instructions` | system prompt / shared doc |
| regression test | project's test suite | same | same |
| personal memory | auto-memory | personal custom instructions | your tool's memory |

> **A recipe, once written, is a doc that prescribes — and it ages like any doc.** An agent
> applies a stale recipe to the letter: a skill citing a class deleted months earlier teaches a
> dead call to every agent that loads it. So wherever the recipes and shared rules land (the
> column above), put that place **inside the checks' corpus**: `doc-refs.extra-roots` in
> `checks-config.json` makes the default `doc-refs-check.py` run walk it, and the tier-2 doc
> review covers it like the durable docs. Measured on a host project: its skills sat outside
> every check for months, and the first pass over them found a three-month-old dead reference.

> The logic (**1 + 2**) does **not** change from one tool to another. Only the table's **column** in step **3** changes. Filling in/adapting that column for your tool is the same operation as choosing where to drop the framework.

## Capture policy — who may write what, and what enforces it

Steps 1–3 above answer *what kind of learning is this, and which function/mechanism does it
become*. A separate question sits underneath: **is the AI even allowed to write the resulting
entry to that channel, and in what state?** That's the **capture policy** — configured per
project in `capture-policy.json` <!-- template --> (root, copied from `capture-policy.example.json`
at adoption). Three levels, set per channel (`memory` / `feature` / `decision`):

| Level | Behavior at closure | Who ratifies, when | What enforces it |
|---|---|---|---|
| `off` | No capture to this channel — only entries already `confidence: verified` + `ratified` may exist; nothing new is expected. | N/A — the channel is closed to new writes. | `checks/capture-policy-check.py` <!-- template --> flags any entry that isn't already ratified. |
| `propose` (default) | The AI may draft the entry, but only a `confidence: verified` + `ratified` entry is allowed to persist — an `unverified` one is a standing finding until a human ratifies it. | A human, at (or shortly after) closure — same lifecycle as `ENTRY-TEMPLATE.md §Confidence lifecycle`. | `checks/capture-policy-check.py` <!-- template --> — post-hoc, deterministic: `confidence: unverified` (or `verified` without `ratified`) in an `off`/`propose` channel is a **BLOCKING** finding. |
| `draft` | The AI may write `confidence: unverified` entries freely — they land in the ratification inbox instead of failing the check. | A human, whenever they sweep the inbox — no closure-time gate. | `memory-audit --pending` (the ratification inbox) + the `SessionStart` sweep + the scheduled cron report (`INSTALL.md` step 5) all relay unratified entries forward until someone acts. |

**The safety asymmetry — why `memory`/`feature` default looser than `decision`.** A `memory` or
`feature` entry left `unverified` is safe to leave in `draft`: the provenance rule
(`MEMORY.md §Provenance & confidence`) already forbids treating an unverified entry as fact — it
sits inert until cross-checked, and the ratification inbox, the `SessionStart` sweep, and the
scheduled cron report all keep surfacing it, so it can't silently rot into "team truth" by mere
persistence. **Normative homes are different in kind, not degree.** An instruction file, a
`.claude/rules/*.md` rule, or a hook config **acts on the agent starting the very next session**
— even while `unverified` — because nothing reads a rule's `confidence` key before obeying it.
There is no inert state for a written rule. That's why `normative-paths` in `capture-policy.json` <!-- template --> (defaulting to the host project's instruction files, e.g. `CLAUDE.md`,
`.claude/rules/`) stays **confirmation-gated regardless of the channel level**: any Write/Edit
under one of those prefixes trips `hooks/normative-write-guard.py` <!-- template -->, an explicit
human "ask" decision at the harness level — independent of whether the model meant to draft
responsibly.

**Three enforcement depths, deliberately different in strength:**
- **Prose** (this document, `WORKFLOW.md`, the skill routing) = **trust** — the model reads the
  rule and follows it in good faith; nothing stops it from being wrong or careless.
- **Check** (`checks/capture-policy-check.py` <!-- template -->) = **certain post-hoc
  detection** — deterministic, zero-false-positive, runs after the fact; it cannot prevent a bad
  write, only guarantee it gets flagged.
- **Guard** (`hooks/normative-write-guard.py` <!-- template -->) = **prevention by the harness** —
  the write is intercepted *before* it lands, gated on human confirmation, independent of the
  model's goodwill or the check's next run.
