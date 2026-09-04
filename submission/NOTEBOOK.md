# NOTEBOOK — chronological lab log

Single working session, 2026-08-31 (~15:20 onward). Entries in the order they
happened; hypotheses recorded before their experiments; wrong guesses kept.

---

**~15:20 — read everything, wrote down suspicions before touching code.**
From reading `fertility.py` and `REPORT_v0.md` alone, candidate flaw list:
`split(" ")` (empty-string words), `lower()` before a cased BPE, macro-averaging of
per-line ratios, NFC call (suspicious: Devanagari nukta consonants like फ़ are
composition exclusions, so NFC *decomposes* them and could shift byte counts →
tokens), `random.seed(1337)` (suspicious: seeded RNG in a deterministic script —
leftover sampling code?), and the big one: tokens-per-word compared across
languages at all. Also — the brief calls `corpus_sample/` "parallel line-by-line",
but translating the Hindi file line by line, it isn't: only 5 of 10 sentences have
an English counterpart, in scrambled order (3↔3, 4↔7, 5↔6, 7↔10, 8↔4), two of them
loose paraphrases. Revised plan: no per-sentence metric is computable on the toys;
need a real parallel corpus (FLORES) for anything content-constant.

**15:28 — environment.** Python 3.14.4, pip OK, `dl.fbaipublicfiles.com` reachable
(FLORES-200 tarball, 24.4 MB). Installed tiktoken 0.14.0 / transformers 5.16.1 /
regex 2026.8.31.

**15:30 — A0: pin the baseline.** Ran the shipped script on the shipped corpora:
eng 1.27/0.226, hin 7.45/1.579, "5.89x" — **exact match** to REPORT_v0. Numbers are
reproducible; every flaw claim can now be a measured delta. (Full precision:
1.2652 / 7.4485 / 5.8871.)

**15:31 — A2 experiment runner.** Wrote `partA/audit/experiments.py`:
re-implements v0, asserts equality against the shipped module's own functions
(passed), then toggles one candidate at a time. Results, with my priors marked:

* E1 `split()` fix: ratio 5.887 → 5.922 (+0.59%); both files carry exactly one
  double-space line (eng L7, hin L10 — the same sentence pair; looks planted).
  Expected direction ✓.
* E2 no `lower()`: eng fertility −2.84%, hin exactly 0, ratio → 6.059 (+2.92%).
  **Prior wrong**: I'd assumed the lowercase bug made Hindi look *worse*; it's the
  opposite — it inflates only English fertility, so v0 *understated* the ratio.
  Three eng lines change token count, all via cased proper nouns (Quarterly/NASA/GPU).
* E3 micro aggregation: +0.35% on the ratio. **Prior wrong-ish**: expected a bigger
  mean-of-ratios effect; toy lines are too uniform in length for it to bite.
* E4 no NFC: all deltas exactly 0.00% — both toy files are already NFC. My फ़-
  decomposition theory produced nothing here. → NFC is *cleared* on this data.
* Seed check: deleted `random.seed(1337)` from a copy; stdout SHA-256 identical;
  `random.` appears nowhere else. → cleared, it's just dead code.
* Bootstrap the toy headline (10k resamples): 95% CI [5.37×, 6.43×]. Had to use
  independent (not paired) resampling *because* the toys aren't aligned — the data
  flaw forces the weaker statistic, which is itself evidence for A1.

Net of all code fixes on the toys: 5.887× → 6.114×. Honest summary: the code bugs
are real but small and mutually offsetting; if that were the whole audit it would
be a nothingburger. The metric itself has to be the story.

**15:33 — A1: corpus.** FLORES-200 devtest, eng/hin/kan/tam/tel. **Dead end #1:**
my extractor assumed member paths `flores200_dataset/devtest/...`; tarfile threw
`KeyError` — actual members are prefixed `./`. Listed members, fixed, extracted
1012 aligned lines per language. The stats table surprised me twice: (1) for the
same content Hindi uses *more* words than English (25.3 vs 21.6 per sentence) while
Dravidian languages use far *fewer* (~16); (2) NFC changes **93/1012 Hindi lines**
in FLORES — so the NFC call that was a no-op on the toys is actually doing real
work on real data (measured token effect: +0.11%, harmless). Revised the cleared-
verdict from "harmless" to "harmless and actually useful". Surprise (1) became the
core of the denominator argument: per-word error has *opposite signs* for hin vs
kan/tam/tel.

**15:35 — A3: corrected engine.** `fertility_v1.py`: 4 tokenizers × 4 denominators
× 5 languages, paired bootstrap (2000, seed 42) on parity. Headline results:

* gpt2 content-constant parity: hin **7.42×** [7.34, 7.51] — the report's 5.89×
  *understated* its own tokenizer's Hindi premium. kan 13.59×, tam 15.54×,
  tel 12.97× — the languages the report never measured are 2× worse than Hindi.
* Tokenizer swap on identical content: hin 7.42× (gpt2) → 4.77× (cl100k) → 1.57×
  (o200k) → **1.25×** (xlm-r). "Property of the script" is dead: 5.9× spread with
  script and content held constant.
* Denominator games on the same gpt2 data: hin is 6.34× per word, 11.4× per
  grapheme, 2.9× per byte, 7.42× per content. Under xlm-r, per-byte *flips the
  sign* (hin 0.113 vs eng 0.232 tok/byte — "Hindi is 2× cheaper"). Any of these
  could have been the deck headline. Only the parallel-sentence one is a cost.
* Also ran the *unmodified* v0 script on the FLORES files for the record:
  hin 6.11×, kan 17.53×, tam 19.52×, tel 15.97× — v0's method errs −18% to +29%
  depending on language, both directions, on the same data.

**15:37 — Part B.** `kv_math.py` from the spec alone: 2·28·8·128·2 = **114,688
B/token** (112 KiB); KV budget 0.92·24 − 8.4 − 1.6 = 12.08 GB → **25.7 → ~25**
concurrent 4096-token seqs. Then `reconcile.py` replays the log: predicted
`kv_cache_util` matches all 13 rows within 2-decimal rounding (max err 0.0046), and
predicted preemptions max(0, n−25) is **exact everywhere** — 7 = 32−25, 23 = 48−25.
I expected the GB-vs-GiB ambiguity to stay unresolved; the log resolved it (GiB
reading predicts util 0.82 / 3 preemptions at the knee — rejected by 0.93 / 7).
`reported_tok_s` = (prompt+gen)·n/wall on all 13 rows within 0.022% → Section 2's
counter counts prefill. Batch-24 goodput: 200.9 tok/s by definition, 200.9 by
counter decomposition (1607.4/8), 200.5 from ITL — three routes agree. B2
mechanism: preemption recompute (≥7×3584 = 25k wasted prefill tokens, +22% prefill
work vs +16% wall-clock excess over linear scaling — same order). Fix prediction:
`max_num_seqs=24` → batch-48 as two waves ≈ 122.3 s (−19% wall, +24% goodput, 0
preemptions).

**~15:40 — writing pass, two self-caught errors.** (Dead end #2, small but real.)
While writing `findings.md` I derived per-word ratios from the *rounded* table
(22.82/1.23 = 18.55) instead of full-precision totals (18.48) — fixed against
`results.csv`. Same class of error in `results.md`: quoted the v0-on-FLORES error
range as "−18% to +23%" from eyeballing tel instead of kan; recomputed: −18% (hin)
to **+29%** (kan). Both caught by re-deriving every quoted number once before
submitting — the same discipline the defense will apply.

**~15:45 — memos.** A4 (routing: direction of v0 survives, all its numbers don't;
budget per *target* tokenizer; monitor tokens-per-request by language/script) and
Part C (SFT via LoRA on self-casualized pairs, gated day-1 by a prompt-only
baseline; reviewer bandwidth, not GPU, is the binding constraint: 1,800 judgments
vs ~100 possible training runs).

**15:46 — self-caught error #3, in this very file.** The first draft of this
notebook carried entry timestamps ("15:55", "16:05") *ahead of the wall clock* —
reconstructed optimistically instead of recorded. Checked `Get-Date` (15:46) while
finalizing and corrected every stamp against the shell history. Kept here because
fabricated-looking chronology is exactly what this notebook exists to avoid.

---

## Round 2 (~16:00-16:30) — review pass: "not enterprise level"

Reviewer feedback on the first complete draft: not impressed. Sat down and
audited my own audit the way I audited the intern. The gap list, in order of how
much each one would have hurt in a defense:

1. **My A4 memo violated my own evidence rule.** It asserted "romanized Hindi
   tokenizes like English" with zero measurement — precisely the crime the
   assignment punishes with negative points. **Measured it**
   (`partA/audit/romanization.py`, IAST → strip diacritics → lowercase): the
   claim was *wrong twice*. Romanized Hindi costs **2.27×** English on gpt2 (a
   huge cut from 7.42×, but not "like English"), and on o200k romanization is
   **worse than native script** (1.88× vs 1.57×). The corrected, conditional
   statement went into the memo and REPORT_v1; the original overclaim is logged
   in AI_USAGE.
2. **The audit produced findings but no product.** Leadership reads a report, not
   an evidence tree. Wrote **REPORT_v1.md** — the corrected replacement for
   REPORT_v0 with figures — including the A×B synthesis both halves implied but
   neither stated: at 7.4× tokens per content, one L4's ~25-session long-context
   ceiling is ~3 sessions for content-equivalent Hindi, and >552 English tokens
   of content cannot fit in Hindi inside the 4096 window at all.
3. **Nothing enforced number integrity.** Wrote **verify.py**: 40 assertions that
   re-derive every headline figure (baseline, per-bug deltas, corpus hashes,
   parity grid, romanization, all 13 bench rows, roofline). First run: all green.
4. **Part B explained *what* but not *why*.** Added the roofline
   (`reconcile.py` §6): decode-step bytes = weights + resident KV; a **single
   65% MBU** parameter reproduces all 13 measured ITLs within ±2.8% (compute is
   1.7 ms vs ~63 ms of memory traffic at batch 24 — memory-bound 40×). Surprise:
   I expected the preempted rows (32/48) to break the fit; they don't (0.636,
   0.647) because resident sequences cap at 25 either way. The same model then
   *prices* the fp8-KV option: 2× capacity, ~70 ms ITL at batch 24, ~2× decode
   throughput at batch 48.
5. **xlm-r was carrying the "Indic-aware" label it doesn't quite deserve, and
   Part C's six languages weren't all measured.** Extended the corpus to
   **7 languages** (added ben, mar — hashes of the original five unchanged, so
   no number drift) and the tokenizer set to **MuRIL** (genuinely Indic-focused)
   with a new **unk% integrity column**, since WordPiece `<unk>` collapse could
   fake good fertility. Result: MuRIL parity **1.00-1.20×** across all six
   product languages (Bengali literally 1.00×), worst unk cell 0.38% (tel) —
   the "property of the script" claim is now dead by a 6.4× spread, integrity-
   checked. Bonus: Bengali arrives 609/1012 lines non-NFC — the intern's cleared
   NFC call earns its keep a third time.
6. **Figures for the deck** (`figures/make_figures.py`, palette validated with
   the dataviz gate): the parity collapse and the counter-vs-goodput divergence.
   Two label collisions caught by actually rendering and looking, then fixed.

**Open ends I did not close** (honest scope): parity on *conversational/organic*
code-mixed text — the romanization measurement uses a clean transliteration
scheme, which bounds but does not settle messy chat spelling (flagged in the
memo; production monitor proposed instead); MuRIL is an encoder vocab — evidence
about vocabulary allocation, not a drop-in serving tokenizer (stated in
REPORT_v1 §4); B2's `max_num_seqs=24` and fp8-KV predictions are stated but not
re-runnable here (no L4/serving stack in this environment) — they are falsifiable
forecasts, with the confirming counter named (B4).

---

## Round 3 (~16:45-18:50) — the audit gets audited

Second reviewer pass: still not at bar. Instead of guessing what "better" means,
turned the assignment's own method on the submission: a nine-agent adversarial
review (rubric grader, tokenizer expert, statistician, serving-infra staff,
defense interrogator, forensic numbers auditor, code reviewer, engineering
bar-raiser, Part C lead), findings merged and each one adversarially verified
(accuracy + materiality lenses). **50 raw findings → 31 merged → 30 confirmed,
1 refuted.** The submission's earlier entries above are left as written — they
are the record this round corrects. What the panel caught, and what changed:

* **The 128k-vocab trap (missed until now).** `bench/model_spec.md` lists vocab
  = 128k — which cannot be gpt2 (50k). Every "current stack" pricing in the
  repo silently assumed v0's tokenizer *is* the serving tokenizer. All coupling
  claims are now hedged and bracketed (REPORT_v1 §4), the table label reads
  "v0's tokenizer", and measuring FLM-4B's real tokenizer is recommendation 6.
  The one claim that survives every measured tokenizer is kept as such (a
  3584-token English prompt's content cannot fit in Hindi: min premium 1.16 >
  1.14).
* **My own C2 logic, turned on Part B.** "Three independent goodput derivations"
  were one definition, one algebraic identity of it, and an ITL formula in
  which ITL cancels. Rewritten: definition + genuinely independent latency
  route (n/itl = 249.8 tok/s steady decode + the roofline) + a labelled
  identity. verify.py check renamed accordingly.
* **Prose-number drift, the class, not just instances**: "7.0× per code point"
  (v0's toy number pasted into a FLORES claim; true 7.46×), "−14%/+37%" leftover
  pre-fix values, "9.6-15.5×" over a list whose minimum is 7.9×, "~13× (Tamil)"
  vs the tables' 14.7×, "±1.2% CIs" vs measured worst 1.28%. All corrected AND
  all now asserted — verify.py grew 40 → **50 checks** precisely so this class
  dies (every corrected figure has an assertion; the CI bound is asserted from
  results.csv itself).
* **Tamil romanization was partly an artifact**: sanscript invents aspirates
  Tamil script cannot express. Reproduced the reviewer's probe exactly
  (de-aspirated bound 2.37× gpt2 / 2.03× o200k vs shipped 3.09/2.69) and now
  publish Tamil as a range. Also fixed: candra vowels left as raw Devanagari in
  190/1012 "romanized" Hindi lines (now mapped, residuals measured at 0), danda
  → '.', and the docstring example is now the function's real output. Ran a
  chat-conventions probe myself before quoting it (hin o200k 1.87 → 1.76 —
  organic spelling is *cheaper* than the clean scheme, so "optimistic bound"
  was the wrong direction; direction-neutral wording now).
* **B2's accounting compared percentages over different bases** (+22% prefill
  vs +16% wall). Redone in seconds: ~3.5 s of re-prefill against a 13.2 s
  excess — the trigger and a lower bound; the bulk is the evicted sequences'
  serialized tail. B4's counter prediction corrected to ≥7/≥23 (events ≥
  unique sequences).
* **Part C's gates were tie-inflated** — a null SFT would have passed
  "win-or-tie ≥70%". Restated on non-ties with a tie-rate cap and an absolute
  rubric clause; LoRA arithmetic corrected to full-sequence tokens (5 h/run,
  ~65 runs — conclusion unchanged at 3× margin); (b)'s rejection anchored to
  the L4 spec with its arithmetic shown, its universal softened, and its one
  real advantage conceded.
* **Deliverability was broken in ways no document admitted**: nothing committed
  to git (a git link would have shipped an empty repo), core.autocrlf=true
  would rewrite the hash-pinned corpus on any Windows clone, four scripts
  hardcoded the doubled starter_kit path with no CLI overrides, and
  experiments.py's bootstrap hardcoded n=10 six times (a pasted line would
  silently not change the CI). Fixed: shared `_paths.py` resolver + STARTER_KIT
  env var, `--log`/`--eng`/`--hin`/`--corpus LANG=PATH` flags, derived sizes,
  root `.gitattributes` (`* -text`) and `.gitignore`, a CI workflow running
  verify.py, and a local commit of the whole tree.
* **AI_USAGE shipped a template placeholder** — replaced with an honest defense-
  prep checklist; the round-3 catches above are themselves its best material.

Final state: `python verify.py` → **ALL 50 NUMBERS VERIFIED**; figures
regenerated with data-derived annotations; all six product languages measured;
every prose figure traceable to a script.

---

## Round 4 (2026-09-04, ~16:45-17:50) — documentation pass, release gate, and the record set straight

Rounds 1-3 all ran on 2026-08-31 (commit `de0749e` that evening); today's pass
added the PDF documentation pack (`docs/`, commit `cd3e298`), a guided
`defense_drill.py`, and a three-agent release gate (fresh-clone verification /
docs-vs-ground-truth audit / link & staleness sweep). Facts recorded here so
every number in the PDFs traces to a repo artifact:

* **Red-team workflow scale (round 3)**: 59 agents (9 reviewers + 1 merge + 49
  verifiers), 784 tool calls, ~3.29M subagent tokens; release gate: 3 agents,
  65 tool calls. Verdict flow: 50 raw → 31 merged → 30 confirmed, 1 refuted.
* **The "35 checks" incident, restored.** In round 2 the draft documents
  published "35 checks" while the harness, once made to count itself, printed
  40. The bulk find-replace that corrected the documents also silently rewrote
  this notebook's own historical mention of 35 — corrupting the record it was
  supposed to keep. Caught by today's release gate ("the prior figure exists
  nowhere in the repo"); restored here. Lesson: never bulk-edit the log.
* **Two breakages during round-3 fixing, previously chat-only**: (1) minutes
  after fixing the hand-typed-numbers class, a "ben +1.2%, hin +0.1%" string
  was hardcoded into fertility_v1's *generator* — caught immediately, replaced
  with computed deltas; (2) a live-override smoke test (`experiments.py --hin`
  with an appended line: ratio 5.8871 → 6.2142 [note: that value was round 1's
  probe; today's smoke line gave 5.9268], bootstrap CI [5.37,6.43] →
  [5.32,6.37]) overwrote the canonical experiment_output.md — regenerated with
  defaults, then verified.
* **Scheme artifacts recorded precisely**: before the round-3 fix, sanscript
  rendered danda as "|" at line ends (hin/ben) and left candra vowels as raw
  Devanagari on 190/1012 hin and 333/1012 mar lines; both fixed, residuals now
  measured at 0 and asserted.
* **Roofline wording precision**: reconcile.py's computed ratio is 63.2/1.7 ≈
  **38×** memory-over-compute; earlier prose rounded it to "40×" — corrected to
  ~38× in capacity.md, REPORT_v1 and the PDFs (the generated output was always
  right).
* **Release gate results**: the six-step fresh-clone protocol passed 6/6 —
  (1) clone, (2) `verify.py` → **ALL 50 NUMBERS VERIFIED**, (3) all 7 corpus
  hashes intact (validates `.gitattributes`), (4) live `--hin` override moves
  the numbers then restores, (5) `STARTER_KIT` env resolution, (6) `reconcile.py`
  clean run;
  regenerated outputs byte-identical to committed ones; GitHub Actions green on
  both pushed commits (`de0749e`, `cd3e298`). Operator rejection wording, for
  the record ("not impressed. professional enterprise level is what i want";
  "still not okay and its no use also, this is not as per standards") — those
  two rejections triggered rounds 2 and 3.
* Housekeeping: `starter_kit (1).zip` renamed to `starter_kit_original.zip`
  (provenance of the audited inputs); drill script and this entry committed.
* **~18:00 — drill executed, transcript committed.** `defense_drill.py` run
  end-to-end through its interactive path (piped Enter): all five verifiable
  steps matched expected vs actual (`drill_transcript.txt`); AI_USAGE checklist
  updated to state precisely who executed what. The one box left open is the
  candidate's own read of REPORT_v1 — by design, that one cannot be delegated.
