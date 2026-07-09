# lib/reporter.py
#
# Renders the list of per-group score dicts (see `lib/scorer.score_group` /
# `lib/sufficiency.score_sufficiency`) as a markdown report: a recap table, then one
# detail section per group. Tolerant to `None` values — a "Not evaluated" group still
# renders (it just shows `None` in place of the missing numbers), it never raises.
def render(results):
    lines = ["# Index-eval report", ""]
    lines += ["| Group | Verdict | lift (±CI) | diag_name_intent | N |",
              "|---|---|---|---|---|"]
    for r in sorted(results, key=lambda x: (x.get("lift") is not None, x.get("lift"))):
        ci = r.get("ci", [None, None])
        partial = " *(partial)*" if r.get("partial") else ""
        lines.append(
            f"| `{r['group']}`{partial} | {r['verdict']} | "
            f"{r['lift']} [{ci[0]}, {ci[1]}] | {r['diag_name_intent']} | {r['n_queries']} |"
        )
    lines.append("")
    for r in results:
        lines.append(f"## `{r['group']}` — {r['verdict']}"
                     + (" *(partial — stratified sample)*" if r.get("partial") else ""))
        lines.append(f"- diag_names={r['diag_names']} · diag_name_intent={r['diag_name_intent']} "
                     f"· lift={r['lift']} CI[{r['ci'][0]}, {r['ci'][1]}] · N={r['n_queries']}")
        if r.get("rewrite"):
            lines.append("- **Lines to rewrite:**")
            for w in r["rewrite"]:
                lines.append(f"  - `{w['file']}` misses {w['misses']} queries, "
                             f"caught by `{w['into']}`")
        lines.append("")
    return "\n".join(lines)
