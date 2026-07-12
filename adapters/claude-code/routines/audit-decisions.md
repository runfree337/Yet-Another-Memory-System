# Routine "decisions audit" — prompt for a scheduled Claude Code session

> **Producer variant** of the decisions-journal audit — a scheduled AGENT session instead of
> the OS cron (see `checks/README.md §Semantic`, "Producer variant"). Use it when the team works
> in **ephemeral remote sessions** where a cron-written gitignored report would die with the
> container. The routine **produces and proposes**; **ratification stays human**
> (Safeguard of `checks/decisions-audit.md`): it merges nothing, deletes nothing, never touches
> the default branch.

## Recommended wiring

- **Model**: a cheap one (batch cross-checking, no need for a heavier tier).
- **Cadence**: weekly (`0 6 * * 1`) to start; move to monthly if the runs keep coming back empty.
- **Session**: fresh each firing (the prompt below is self-contained — it assumes no conversation
  context).

## The prompt

```
You are the decisions-journal audit routine for this repository. The journal lives under
decisions/ (INDEX.md + one D-YYYY-MM-DD-NN.md file per decision); the full protocol is in
decisions/README.md, the audit rubric in checks/decisions-audit.md.

ABSOLUTE RULE (Safeguard): you PRODUCE and you PROPOSE, you never RATIFY. Forbidden: merging a
branch, deleting a decision file, changing anything outside your proposal branch, promoting an
entry to `confidence: verified`, pushing to the default branch.

Run in order:

1. TIER 1 (mechanical) — `python3 checks/memory-audit.py --tier1`. Every blocking drift is
   REPORTED in your final report (file:line + rule id), never fixed.

2. TIER 2 (semantic) — `python3 checks/decisions-audit.py --plan`, then launch ONE sub-agent per
   batch (offset/limit from the plan). Each sub-agent cross-checks every decision in its batch
   against the real code (retrieve-then-verify, never a conclusion without grep/read evidence),
   applies the rubric of checks/decisions-audit.md, and returns STRICTLY the format
   `D-… | VERDICT | summary ≤8 words | evidence | confidence:…` plus a final `KEPT: …` line.
   Aggregate with `python3 checks/decisions-audit.py --merge <outputs>` and check coverage (each
   decision audited exactly once).

3. PROPOSAL BRANCH — only for ARCHIVE-1, ARCHIVE-4 and REDUNDANT verdicts at confidence:high:
   create the branch `routine/audit-decisions-<today>` and prepare the archival diffs conforming
   to decisions/README.md (status: archived + archival banner at the top of the body + flipping
   the INDEX.md line from ## Active to ## Archived), after the incoming-reference safeguard (a
   `// D-…` in code, or a living un-retired pointer, blocks that entry → leave it in the report,
   not in the diff). Verify `python3 checks/decisions-check.py` exits 0 on the branch, commit (the
   message cites each Id handled), push the branch. If there is no high-confidence candidate, no
   branch.

4. Verdicts CODE-DRIFT, CONFLICT, NOT-A-DECISION, DOUBT and any non-high candidate go to the
   REPORT ONLY — the human decides.

5. FINAL REPORT (your last message): tier 1 state · total audited + coverage · table of issues by
   verdict (id, summary, evidence, confidence) · the pushed branch name and its contents, or "no
   proposal" · one-line reminder: "ratification = human review and merge of the branch". If tier 1
   is clean AND tier 2 surfaces NOTHING, say so in three lines, no branch.
```
