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

> The logic (**1 + 2**) does **not** change from one tool to another. Only the table's **column** in step **3** changes. Filling in/adapting that column for your tool is the same operation as choosing where to drop the framework.
