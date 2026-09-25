# Judge records — roster, enrolment and certification

Designed 2026-09-25. **Plan 1 of the two accounts plans** — the records, with no network.
Plan 2 is sign-in (allauth, Google, matching the verified email against the roster) and
comes after this one, because matching against a roster needs a roster to exist.

This document **amends** `2026-07-28-rhythmic-exam-rebuild-design.md` where the two
disagree; the corrections are listed at the end and noted in that spec as well.

## Source

FIG General Judges' Rules 2025–2028, chapter 2, read 2026-09-25 (`specs/en_1.2 - General
Judges' Rules 2025-2028 (Mark-up).pdf`, a public FIG document). **SAGF runs a national
copy of the FIG brevet** (confirmed by Altus, 2026-09-25): it awards Categories 1–4 itself,
capped the way FIG caps them, and adopts these four chapter-2 procedures —

| procedure | FIG text | consequence here |
|---|---|---|
| Latest sitting is final | §2.7.1, §2.7.2: *"The retest result will be valid and final."* | a certification points at the most recent submitted sitting — found by ordering, never by `max()` over grades |
| One retest per cycle | §2.7: *"Only one Retest opportunity will be permitted per judge per cycle"* | enrolment refuses a third practical sitting in a cycle unless overridden |
| No results before certification | §2.2.1: *"No results will be communicated at the end of any course."* | no candidate-facing path reads a result until the sitting is `CERTIFIED` |
| Review by judge number | §2.2.1: results *"reflected only by judge number not name"* | the review screen shows an opaque candidate number; the name appears only once certified |

## Level and category are different ladders

The original spec's `Certification · level` conflated them. §2.4 makes *"Minimum national
level"* the entry condition for an examination and Categories 1–4 the brevet awarded after
it. In this system:

- **Level** chooses which paper a judge sits. It lives on `Exam`, as it already does.
- **Category** is what a certification awards: 1, 2, 3, 4 or `FAIL`. Category 1 is best.

Eligibility therefore stops consulting certification history — "level" has no history to
be supported by — and history moves into the **award**, where the first-cycle cap and the
drop floor need it.

## Apps and dependency direction

- **`accounts`** holds identity: `User` (exists), `JudgeProfile`, `RosterEntry`. Plan 2 adds
  allauth here.
- **`exams`** holds everything with a sitting in it: enrolment, `Certification`, the award.

The direction is `exams → accounts`, one way. Putting `Certification` in `accounts` would
make it point at `Sitting` while enrolment in `exams` reads `RosterEntry` — a cycle.

**Rules are pure functions; services are thin.** `exams/eligibility.py` and
`exams/awards.py` take plain values and import no model, tested without a database like
`scoring/`. `exams/enrolment.py` and `exams/certification.py` load rows, call the rules and
write the results — the `tables.py` / `freeze.py` split again. The rules are about judges,
not marks, so they do not belong in `scoring/`.

## Data model

### `accounts`

| model | fields | notes |
|---|---|---|
| `JudgeProfile` | `user` (1:1, **nullable**, unique), `sagf_id` (unique) | a judge exists as a person before they have a login; the category import creates profiles with no user, and Plan 2 attaches one |
| `RosterEntry` | `sagf_id`, `email`, `year`, `levels` (array of level numbers) | unique `(sagf_id, year)`; `HistoricalRecords()`; email stored lowercased. Joined to a judge **by `sagf_id` value**, not by FK — the roster predates the account |

Nothing else is collected (POPIA, per the original spec's data-protection note).

### `exams`

| model | fields | notes |
|---|---|---|
| `Cycle` | `name`, `first_year`, `last_year` | `CHECK (first_year <= last_year)`. An exam's cycle is the one whose range contains `Exam.year`. A table, because FIG sets cycles |
| `CategoryRequirement` | `cycle`, `category` (1–4), `dimension` (`DIFFICULTY`, `EXECUTION`, `ARTISTRY`), `minimum_grade` | §2.6 as rows, like grade bands. Category 1's asymmetry is data |
| `Certification` | `judge` (→ `JudgeProfile`), `cycle`, `category`, `source` (`EXAM`, `IMPORTED`), `sitting` (nullable, `PROTECT`, unique), `examination_category`, `suggested_category`, `floor`, `cap`, `reason`, `certified_by`, `certified_at` | **immutable event log**; the category for a cycle is the latest row, and a correction is a new row |

`Certification` constraints:

- `source = EXAM` ⇔ `sitting IS NOT NULL`.
- For `IMPORTED`: `examination_category`, `suggested_category`, `floor` and `cap` are all
  `NULL`, and `reason` is non-blank — it records where the category came from.
- For `EXAM`: `reason` is non-blank whenever `category ≠ suggested_category`.

`examination_category`, `suggested_category`, `floor` and `cap` are **stored**: they record
what the official saw when deciding. F1's rule, applied to the award.

**`Certification.judge` points at `JudgeProfile`, not `User`,** because imported history
belongs to judges who have not signed in yet. `Sitting.judge` stays on `User`: sitting an
exam needs an account; having a history does not.

### Changes to `Sitting`

- **Add `candidate_number`** — opaque, random, unique per exam, assigned at enrolment. Not
  the `pk`, which is sequential and reveals enrolment order.
- **Add `override_by` and `override_reason`.** `CHECK`: both set or both null, and the
  reason non-blank.
- **Remove `certified_by`, `certified_at` and `outcome`.** `Certification` holds who, when
  and what; two copies of who certified can disagree and nothing reconciles them.
  `status = CERTIFIED` remains the one thing the sitting knows.

## Enrolment

```
exams/eligibility.py  refusals(*, roster_levels, exam_level, prior_practical_sittings, has_open_sitting) -> list[Refusal]
exams/enrolment.py    enrol(judge, exam, *, official, override_reason=None) -> Sitting
```

| refusal | when |
|---|---|
| `NOT_ON_ROSTER` | no `RosterEntry` for the judge's `sagf_id` in `exam.year` |
| `LEVEL_NOT_PERMITTED` | an entry exists but `exam.level` is not in its `levels` |
| `RETEST_USED` | two practical sittings already exist in this exam's cycle — first attempt and the one retest |
| `ALREADY_ENROLLED` | a `PENDING` or `IN_PROGRESS` sitting for this exam exists |

- The retest limit counts **practical** sittings only; theory decides nothing.
- A judge with no `JudgeProfile` is an **error**, not a refusal: there is no `sagf_id` to
  consult, so no override can make it right.
- With refusals and no `override_reason`, `enrol` raises `EnrolmentRefused(refusals)`. With
  one, it enrols and records `override_by` / `override_reason`. The service **strips the
  reason** before saving, because `CHECK (reason <> '')` accepts a single space.
- `enrol` takes `select_for_update()` on the judge's `JudgeProfile` before counting, so two
  concurrent enrolments cannot both count one prior sitting.
- In this plan an **official** calls `enrol`, from the admin. Plan 2 adds candidate
  self-selection through the same function, without an override.

## Certification

### Pure rules — `exams/awards.py`

**Dimension grades.** Execution is the `EX` grade and Artistry the `AV` grade, from the
stored `ComponentResult`s. Difficulty is `score_component([DA, DB])` over the two **stored,
rounded** percentages — `scoring`'s own mean, quantized to 0.01 `ROUND_HALF_UP`, which is
the rounding order decided 2026-08-08 — graded against the Difficulty bands frozen on the
`DA` items. If `DA`'s and `DB`'s frozen bands differ, it raises rather than choosing one.

**`examination_category(grades, requirements)`** — the best category whose three minimums
are all met, else `FAIL`. Grades compare by **rank** — position in the band set ordered by
minimum — never by name; `"Pass" > "Good"` is true as strings, which is F3's shape. A
`minimum_grade` absent from the band set raises.

**`award_bounds(examination_category, history, cycle)` → `(floor, cap)`**

- **cap** — Category 3 when the judge has no certification in any earlier cycle (§2.6,
  *"A first time Brevet can achieve a maximum of Category 3 in his/her first cycle"*). An
  imported certification counts as history.
- **floor** — the previous cycle's latest category plus two, numerically (§2.6, *"a judge
  can only drop 2 categories in one cycle"*), applied on pass **and** fail. **It exists only
  for a previous Category 1 or 2** — §2.6's own examples are 1→3 and 2→4, and 3 + 2 names
  no category, so a previous Category 3 or 4 may fall to `FAIL`. No floor either when the
  previous cycle's category was `FAIL`, or when there is no certification in the
  immediately preceding cycle (§2.8, interruption).
- **suggested** — the examination category, lowered to the cap and raised to the floor.

**Floor and cap cannot conflict.** The cap requires no earlier certification; the floor
requires one in the previous cycle. The conflicts that remain — judging experience against
the floor, for one — are the official's, and are resolved in the reason.

### Service — `exams/certification.py`

`certify(sitting, *, official, category, reason="")`, inside `transaction.atomic()` with
`select_for_update()` on the sitting. Guards, each with its own test: status is
`SUBMITTED`; the exam is `PRACTICAL`; all four component results exist. It computes the
grades, examination category, bounds and suggestion, writes all of them onto the
`Certification`, and sets `status = CERTIFIED`.

Judging experience is **not modelled** (decided 2026-09-25). The system computes the
bounds it can derive from its own records; the official applies experience and writes the
reason.

### Review by number

The admin review list shows submitted practical sittings by `candidate_number`, with the
four grades, the examination category, the bounds and the suggestion. The judge's name does
not appear until the certification is recorded. Candidates have no path to a result in
this plan; the "no results before certification" rule is recorded for the React island.

## Imports

One pattern for both:

```
parse(rows)               -> (records, errors)              pure
diff(existing, incoming)  -> Changes(add, change, remove)   pure
apply(changes, official)  -> one transaction
```

- The **dry run** is the same diff with nothing written.
- **Apply recomputes the diff and refuses if it differs from the preview**, so an edit made
  between preview and confirm is never applied unseen.
- A **duplicate `sagf_id`** or **any malformed row** rejects the whole import. Last-row-wins
  discards a row silently; a half-applied roster is worse than none.

**Roster import** — one file per year: `sagf_id`, `email`, `levels`. Remove means present
for that year in the database and absent from the file.

**Category import** — SAGF's register of current categories: `sagf_id`, `category`, cycle.
Creates `JudgeProfile`s with no user where none exist, and `Certification(source=IMPORTED)`
rows. Without it, every judge certified before launch would read as a first-time brevet and
be capped at Category 3.

## Testing

- **Pure rules** — `parametrize` with `ids`, no database. Must pin: Category 1's asymmetry
  (Difficulty very good, the others excellent → Category 2); rank-not-name comparison; the
  Difficulty mean at the 80.00 edge; floor on `FAIL`; no floor after an interruption; cap
  on a first cycle; an imported row counting as history; **floor and cap mutually
  exclusive, checked exhaustively** over the small domain rather than argued.
- **Every guard its own test, shown red** — theory sitting, unsubmitted sitting, missing
  results, differing DA/DB bands, missing profile.
- **Constraints** — migration mutants for the blank reason, `source` ⇔ `sitting`, the
  imported-row nulls and the half-set override.
- **Dry runs** — assert nothing was written **and** that the diff was non-empty; `count()`
  is satisfied by emptiness.
- **Review screen** — a distinctive judge name asserted absent before certification,
  present after.
- **`select_for_update()` in `enrol`** — probably no single-threaded mutant reaches it;
  record it as such (see the `mutation-sweep` skill) rather than hunt one.

## Task order

Part A — rules and their tables, independently shippable:

1. `JudgeProfile` (nullable `user`) and `RosterEntry`
2. `Cycle` and `CategoryRequirement`
3. Eligibility rule (pure)
4. `enrol`; `candidate_number` and the override fields on `Sitting`
5. Dimension grades and `examination_category` (pure)
6. `award_bounds` (pure)

Part B — services and admin:

7. `Certification` and its constraints; `Sitting`'s certification fields removed
8. `certify` and its guards
9. Roster import
10. Category import
11. Review by number in the admin
12. Sweep and plan close

## Corrections to the original spec

1. **`Certification · level` → `Certification · category`.** Level chooses the paper;
   category is the award. `Certification.judge` points at `JudgeProfile`.
2. **The award formula.** The original gives
   `min(examination result, experience, first-cycle cap, previous − 2)`. The drop limit is
   a **floor**, not a cap: a previous Category 1 judge whose examination gives Category 4
   is awarded Category 3 under §2.6, and `min(…)` gives 4. The award is capped from above
   (experience, first cycle) and held from below (previous − 2).
3. **Eligibility no longer consults certification history.** "Roster and records must
   agree" becomes: the roster permits the level, and the retest limit is not exceeded.
4. **Certification lives in `exams`**, as the architecture tree already said; the domain
   model's "Accounts" heading was the inconsistent one.

## Open questions

1. **Cycle boundaries for exams sat late.** §2.6 lets a missing experience requirement be
   fulfilled "within two (2) years of the new cycle". Whether that ever makes a certification
   belong to a cycle other than its exam's is for SAGF.
2. **The online-examination cap.** FIG's online examination awards at most Category 4
   (§2.3). This system is an online examination; SAGF has not said whether it copies the
   cap. If it does, it is one more input to `award_bounds`.
