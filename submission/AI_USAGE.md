# AI_USAGE

Honest account, as the assignment asks.

## What AI did

**Claude (Fable 5, via Claude Code) produced nearly everything in this repo under
direction**: it read the brief and the starter kit, proposed the flaw hypotheses,
wrote every script, ran them in this repo's environment, drafted all documents
including this one — and, in a third round, ran a nine-agent adversarial review
of its own submission and fixed the 30 verified findings that survived. The
chronology in `NOTEBOOK.md` is the actual working order, dead ends included, not
a reconstruction.

## Where AI was wrong, concretely (all caught inside the sessions)

1. **Wrong priors, corrected by measurement** — the failure mode the assignment
   warns about, avoided only because every hypothesis was forced through an
   experiment: predicted the NFC call could distort Hindi numbers (measured:
   zero on the toys → cleared, not claimed); assumed the `lower()` bug made
   Hindi look worse (measured: the opposite); expected macro-vs-micro to matter
   on the toys (measured: +0.35%).
2. **Rounded-number arithmetic, repeatedly.** Round 1: derived 22.82/1.23 =
   "18.55×" from a 2-decimal table (true: 18.48×). Round 3's red-team found the
   same disease had re-infected other prose: a "7.0×" per-code-point figure that
   was actually v0's toy number pasted into a FLORES claim (true: 7.46×), a
   "−14% to +37%" range contradicting its own evidence table (true: −15% to
   +36%), "9.6-15.5×" attached to a list whose minimum is 7.86×, and "~13×
   (Tamil)" where the repo's own tables say 14.7×. Every such figure now has a
   `verify.py` assertion; the lesson is structural, not personal: **prose that
   quotes a number a script doesn't emit will eventually be wrong.**
3. **An unmeasured claim shipped in round 1** — the worst incident. The first A4
   memo asserted "romanized Hindi tokenizes like English". Measured: 2.25× on
   gpt2 (not ~1×), and on o200k romanization is *worse* than native for Hindi
   (1.87× vs 1.57×) — wrong in magnitude and, for modern vocabularies,
   conditionally wrong in direction.
4. **The AI's fix for that claim had its own flaws**, found by the round-3
   panel: sanscript's Tamil→IAST invents aspirates Tamil script cannot express
   (inflating Tamil's romanized parity ~24%; now published as a measured range),
   candra vowels were left as raw Devanagari in "romanized" text (now mapped;
   residuals measured at zero), and the script's own docstring example didn't
   match its output (now generated from a live run).
5. **Circular corroboration, in the submission's own Part B.** "Three
   independent derivations agree (±0.4 tok/s)" — two of the three were
   algebraically identical and the third cancelled the latency data out. The
   audit's own C2 finding ("shared numerator ⇒ agreement is not confirmation")
   applied verbatim to its author. Rewritten as one definition, one genuinely
   independent latency route, and one labelled identity.
6. **A planted inconsistency initially missed**: the serving spec says vocab =
   128k, which cannot be gpt2 — so pricing the "current stack" off gpt2 parity
   was unjustified. The red-team caught it; REPORT_v1 now brackets the premium
   and makes measuring the real tokenizer an explicit recommendation.
7. **Invented chronology**: the notebook's first draft carried timestamps ahead
   of the wall clock — plausible-looking reconstruction instead of record.
   Caught against `Get-Date`; corrected.

## What kept the AI honest here

The evidence rule, applied mechanically and then adversarially: byte-exact
baseline before any claim; one-toggle deltas for every claimed flaw; cleared
items cleared by experiment; all 13 bench rows predicted before the mechanism
was asserted; and finally a nine-lens red-team (50 raw findings → 30 verified)
followed by fixes and a re-run of the 50-assertion harness. Nothing in the
submission rests on an unverified model statement — including the model's
statements about its own work.

## What the candidate must do before submitting (defense prep checklist)

The defense is the candidate's, not the AI's. **`python submission/defense_drill.py`
walks every item below interactively (~10 minutes)** — it runs the real commands
and shows expected vs actual; the understanding it builds is the deliverable:

- [ ] run `python submission/verify.py` yourself and read what each PASS means
- [ ] re-run the A0 repro command from `partA/audit/repro_v0.md`
- [ ] toggle one experiment live (e.g. `experiments.py --hin <edited file>`)
- [ ] re-derive B1 on paper: 2·28·8·128·2 = 114,688 B; 0.92·24 − 8.4 − 1.6 = 12.08 GB; ÷ 0.4698 GB → 25.7
- [ ] pick one bench row and verify its `kv_cache_util` and `preempted_seqs` by hand
- [ ] read `REPORT_v1.md` end to end and note anything you would phrase differently — say so in the defense; disagreement with the AI's drafts is evidence of ownership, not weakness
