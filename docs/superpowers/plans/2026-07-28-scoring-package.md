# Scoring Package Implementation Plan

> **Tutoring mode — this plan deviates from the standard format.**
> Altus writes every line of test and implementation code. Tasks give behaviour,
> exact signatures, and exact test cases. They deliberately do **not** give
> implementation bodies. Claude explains concepts, reviews what is written, and
> pushes back — Claude does not implement.

**Goal:** A framework-free Python package that marks exam answers, correctly and
under test, before any Django exists.

**Architecture:** Plain Python. No Django import, no database, no HTTP. Plain data
in, plain data out. Marking algorithms live here; marking *numbers* live in the
database later and are passed in as arguments.

**Tech Stack:** Python 3.12, `pytest`, `Decimal` from the standard library. No
third-party runtime dependencies.

## Global Constraints

- **No Django, no SQLAlchemy, no I/O anywhere in `scoring/`.** If a module needs to
  import a framework, the boundary is wrong.
- **All money-like numbers are `Decimal`, never `float`.** Deductions such as
  `0.1` are not representable in binary floating point.
- **Never compare answers as strings.** Finding F3 is exactly this bug.
- **Percentages are `Decimal` in the range 0–100 inclusive.**
- **Marking tables and grade bands are always arguments, never literals.** FIG
  republishes them each cycle.

## Why this package first

Three of the eight findings in the spec live here (F3, F4, F5), and a fourth (F6)
is that this code has never had a test. It is also the only part of the system that
can be built with nothing installed but pytest.

## Where this lives

Everything in this plan is inside `rhythmic/`, and **every path and command below
is relative to that directory.** Start with `cd rhythmic`.

Note the spelling: the sport is *rhythmic*. New code uses the correct spelling;
`legacy/flask_backend/` keeps the old one.

## File structure

```
scoring/
├── __init__.py      public API — re-exports only
├── types.py         frozen dataclasses: MarkingTable, BandRow, GradeBand
├── values.py        text → Decimal normalisation
├── tables.py        band lookup
├── marking.py       mark_choice, mark_numeric
└── aggregate.py     score_component, grade

tests/
├── test_values.py
├── test_tables.py
├── test_marking.py
├── test_aggregate.py
└── test_legacy_parity.py
```

Each module has one job. `values` knows nothing about tables; `tables` knows nothing
about marking; `marking` composes the two.

---

### Task 1: Project skeleton and a working test loop

**Files:**
- Create: `pyproject.toml`, `scoring/__init__.py`, `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing
- Produces: a `pytest` command that runs and a `scoring` package that imports

**Concepts you need:** `pyproject.toml` replaces `setup.py` and `requirements.txt`.
An editable install (`pip install -e .`) puts your package on the path so `import
scoring` works from the tests without path hacks.

- [ ] **Step 1: Write `pyproject.toml`**

Must declare: project name `rhythmic-scoring`, `requires-python = ">=3.12"`,
a `[project.optional-dependencies]` group `dev` containing `pytest`, and
setuptools configured to find the `scoring` package. No runtime dependencies.

- [ ] **Step 2: Install it**

Run: `pip install -e ".[dev]"`
Expected: succeeds, and `pytest --version` prints a version.

- [ ] **Step 3: Write a smoke test**

One test that imports `scoring` and asserts nothing else. Its only job is proving
the loop works.

- [ ] **Step 4: Run it**

Run: `pytest -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml scoring/ tests/
git commit -m "chore(scoring): add package skeleton and pytest setup"
```

**Review gate:** Claude checks the `pyproject.toml` before you move on.

---

### Task 2: Answer normalisation (fixes F3)

**Files:**
- Create: `scoring/values.py`, `tests/test_values.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  ```python
  class UnparseableAnswer(ValueError): ...

  def to_decimal(raw: str | Decimal | None) -> Decimal | None
  ```

**Behaviour:**
- Blank or `None` returns `None`, meaning *no answer given*.
- Unparseable text raises `UnparseableAnswer`.
- Otherwise returns a `Decimal`.

**Concepts you need:** `Decimal("0.30") == Decimal("0.3")` is `True` — `Decimal`
compares numerically, so the F3 bug cannot survive this conversion. Note this is
*not* true of `str`, which is what the old code compared. The old
`_sanatize_user_answer` also handled a South African habit of writing `0,3`, and a
leading bare `.3`; keep both behaviours.

- [ ] **Step 1: Write the failing tests**

Write one test per row. The last column is why the row exists.

| Input | Expected | Reason |
|---|---|---|
| `"0.30"` | `Decimal("0.30")` | baseline |
| `"0.3"` | equal to `Decimal("0.30")` | **F3 regression** |
| `".3"` | `Decimal("0.3")` | judge omitted the leading zero |
| `"0,3"` | `Decimal("0.3")` | comma decimal separator |
| `"0/3"` | `Decimal("0.3")` | old input habit, preserved |
| `" 0.3 "` | `Decimal("0.3")` | stray whitespace |
| `""` | `None` | not answered |
| `None` | `None` | not answered |
| `"abc"` | raises `UnparseableAnswer` | garbage is not a zero |

The F3 row should assert `to_decimal("0.3") == to_decimal("0.30")`. That single
assertion is the regression test for a bug that scored correct answers zero.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_values.py -v`
Expected: all fail with `ModuleNotFoundError: No module named 'scoring.values'`

- [ ] **Step 3: Write `scoring/values.py`**

Your implementation. Keep it under about fifteen lines. Resist adding cases the
tests don't ask for.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_values.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add scoring/values.py tests/test_values.py
git commit -m "feat(scoring): normalise answers to Decimal before comparison (F3)"
```

**Review gate:** Claude reviews. Expect pushback if you used `float` anywhere, or
returned a sentinel number instead of raising.

---

### Task 3: Band lookup (fixes F4)

**Files:**
- Create: `scoring/types.py`, `scoring/tables.py`, `tests/test_tables.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  ```python
  @dataclass(frozen=True)
  class BandRow:
      expert_minimum: Decimal      # inclusive lower bound of the expert-score band
      percentages: tuple[Decimal, ...]   # one per difference column

  @dataclass(frozen=True)
  class MarkingTable:
      difference_steps: tuple[Decimal, ...]   # inclusive lower bound of each column
      rows: tuple[BandRow, ...]               # ascending by expert_minimum

      def lookup(self, expert: Decimal, difference: Decimal) -> Decimal
  ```

**Behaviour — this is the important part:**

Both dimensions are **half-open bands**, and both are **open-ended at the top**.

- Column `i` covers `[difference_steps[i], difference_steps[i+1])`.
- The last column covers `[difference_steps[-1], ∞)`.
- Row selection works identically on `expert_minimum`.
- A value below the first band uses the first band.

**This is the structural fix for F4.** The old code did
`diff_arr.index(difference)`, which requires an exact hit and raised `ValueError`
on `0.07`. A band lookup has no index to miss, so `0.07` cannot crash — it lands
in whichever band contains it.

**A decision you should understand rather than accept:** bands *floor*, they don't
round. A difference of `0.08` against columns `0.00, 0.05, 0.10` lands in the
`0.05` column, not `0.10`. Flooring gives the candidate the benefit of the doubt,
and it's consistent with how FIG's own open-ended "1.4 and more" top band behaves.

- [ ] **Step 1: Write the failing tests**

Build one small fixture table in the test file and reuse it:

```
difference_steps = (0.0, 0.1, 0.2)
rows:
  expert_minimum 0.0  → percentages (100, 90, 50)
  expert_minimum 2.0  → percentages (100, 100, 80)
```

| expert | difference | Expected | Reason |
|---|---|---|---|
| `0.0` | `0.0` | `100` | exact, first row |
| `0.0` | `0.1` | `90` | exact column boundary |
| `0.0` | `0.15` | `90` | **floors into the 0.1 band** |
| `0.0` | `0.07` | `100` | **F4 regression — must not raise** |
| `0.0` | `5.0` | `50` | above top column, uses last |
| `2.0` | `0.1` | `100` | second row selected |
| `3.5` | `0.1` | `100` | above top row, uses last |
| `1.9` | `0.1` | `90` | just below second row, uses first |

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tables.py -v`
Expected: all fail — `scoring.tables` does not exist.

- [ ] **Step 3: Write `scoring/types.py` and `scoring/tables.py`**

Your implementation. Hint on approach, not code: walk the bands from the top down
and take the first whose lower bound the value meets or exceeds. That handles the
open-ended top and the below-the-bottom case without special-casing either.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tables.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add scoring/types.py scoring/tables.py tests/test_tables.py
git commit -m "feat(scoring): look up marking tables by band, not exact index (F4)"
```

**Review gate:** Claude reviews. This is the task most likely to have an
off-by-one at a band boundary, so expect close reading of the `0.1` and `1.9`
cases.

---

### Task 4: Marking a single answer

**Files:**
- Create: `scoring/marking.py`, `tests/test_marking.py`

**Interfaces:**
- Consumes: `scoring.values.to_decimal`, `scoring.tables.MarkingTable`
- Produces:
  ```python
  def mark_choice(response: str | None, correct_option: str) -> Decimal
  def mark_numeric(
      response: str | None,
      expert_score: Decimal,
      table: MarkingTable,
  ) -> Decimal
  ```
  Both return a percentage in the range 0–100.

**Behaviour:**
- `mark_choice` returns `100` on an exact match, `0` otherwise, `0` for `None`.
- `mark_numeric` returns `0` when the response is `None`. Otherwise it computes
  `abs(response - expert_score)` and looks it up in the table.
- An `UnparseableAnswer` from `to_decimal` propagates. It is a data error, not a
  wrong answer, and silently marking it zero is how F3 hid for years.

- [ ] **Step 1: Write the failing tests**

Reuse the fixture table from Task 3 — move it into `tests/conftest.py` as a
fixture so both files share it.

| Function | Inputs | Expected | Reason |
|---|---|---|---|
| `mark_choice` | `"B"`, `"B"` | `100` | correct |
| `mark_choice` | `"A"`, `"B"` | `0` | wrong |
| `mark_choice` | `None`, `"B"` | `0` | not answered |
| `mark_numeric` | `"0.30"`, `Decimal("0.30")` | `100` | exact |
| `mark_numeric` | `"0.3"`, `Decimal("0.30")` | `100` | **F3 regression** |
| `mark_numeric` | `"0.23"`, `Decimal("0.30")` | `100` | **F4 regression — no crash** |
| `mark_numeric` | `None`, `Decimal("0.30")` | `0` | not answered |
| `mark_numeric` | `"0.45"`, `Decimal("0.30")` | `90` | difference 0.15 floors to the 0.1 column |
| `mark_numeric` | `"0.50"`, `Decimal("0.30")` | `50` | difference 0.2 hits the open-ended last column |
| `mark_numeric` | `"abc"`, `Decimal("0.30")` | raises `UnparseableAnswer` | data error surfaces |

Check the expected values against the Task 3 fixture yourself before writing them
down — if my arithmetic is wrong, the test is wrong, and you should catch it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_marking.py -v`
Expected: all fail.

- [ ] **Step 3: Write `scoring/marking.py`**

Your implementation. It should be short — this module composes Tasks 2 and 3
rather than doing arithmetic of its own.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_marking.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add scoring/marking.py tests/test_marking.py tests/conftest.py
git commit -m "feat(scoring): mark choice and numeric answers"
```

**Review gate:** Claude reviews, with attention to whether `mark_numeric` grew
logic that belongs in `tables.py`.

---

### Task 5: Aggregation and grading (fixes F5)

**Files:**
- Create: `scoring/aggregate.py`, `tests/test_aggregate.py`
- Modify: `scoring/types.py` — add `GradeBand`

**Interfaces:**
- Consumes: nothing from earlier tasks; operates on percentages
- Produces:
  ```python
  @dataclass(frozen=True)
  class GradeBand:
      name: str
      minimum: Decimal      # inclusive

  def score_component(item_percentages: Sequence[Decimal]) -> Decimal
  def grade(percentage: Decimal, bands: Sequence[GradeBand]) -> str
  ```

**Behaviour:**
- `score_component` returns the **arithmetic mean** of the per-item percentages,
  rounded to two decimal places.
- An empty sequence raises `ValueError`. A component with no items is a
  programming error, and returning `0` would silently report every candidate as
  having failed.
- `grade` returns the name of the highest band whose `minimum` the percentage
  meets or exceeds. Below every band, raise `ValueError` — a bands list with no
  floor is misconfigured data.

**Why the mean matters:** F5. The old code summed marks and called the total a
percentage. It read correctly only because there were exactly 20 items worth 5
marks. The mean is correct for any number of items, which is the whole point.

- [ ] **Step 1: Write the failing tests**

For `score_component`:

| Input | Expected | Reason |
|---|---|---|
| `[100]` | `100` | single item |
| `[100, 50]` | `75` | mean, not sum |
| `[100] * 20` | `100` | **F5 regression — not 2000** |
| `[100] * 25` | `100` | **F5 regression — item count is irrelevant** |
| `[100, 100, 50]` | `83.33` | rounds to 2dp |
| `[]` | raises `ValueError` | empty component is a bug |

For `grade`, use the FIG Execution bands from the spec:
`Excellent ≥ 90`, `Very Good ≥ 80`, `Good ≥ 65`, `Pass ≥ 50`, `Fail ≥ 0`.

| Input | Expected | Reason |
|---|---|---|
| `100` | `"Excellent"` | top |
| `90` | `"Excellent"` | boundary is inclusive |
| `89.99` | `"Very Good"` | just below boundary |
| `65` | `"Good"` | boundary |
| `49.99` | `"Fail"` | just below pass |
| `0` | `"Fail"` | floor |

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_aggregate.py -v`
Expected: all fail.

- [ ] **Step 3: Write `scoring/aggregate.py`**

Your implementation. For the rounding, look at `Decimal.quantize` with
`ROUND_HALF_UP` — Python's built-in `round()` uses banker's rounding, which will
surprise you on `2.5`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_aggregate.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add scoring/aggregate.py scoring/types.py tests/test_aggregate.py
git commit -m "feat(scoring): average component percentages instead of summing marks (F5)"
```

**Review gate:** Claude reviews the rounding decision specifically.

---

### Task 6: Public API surface

**Files:**
- Modify: `scoring/__init__.py`
- Create: `tests/test_public_api.py`

**Interfaces:**
- Consumes: everything above
- Produces: the names Django will import later —
  `to_decimal`, `UnparseableAnswer`, `MarkingTable`, `BandRow`, `GradeBand`,
  `mark_choice`, `mark_numeric`, `score_component`, `grade`

**Why this is its own task:** it fixes the import surface *before* Django depends
on it. Later code should write `from scoring import mark_numeric`, never
`from scoring.marking import mark_numeric`, so internal modules can be reorganised
without breaking callers.

- [ ] **Step 1: Write the failing test**

One test that imports every name above directly from `scoring`, plus an assertion
that `scoring.__all__` contains exactly those nine names.

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_public_api.py -v`
Expected: FAIL on `ImportError`.

- [ ] **Step 3: Write the re-exports**

`scoring/__init__.py` contains imports and `__all__`. No logic.

- [ ] **Step 4: Run it to verify it passes**

Run: `pytest -v`
Expected: everything passes — 41 tests (1 smoke + 9 values + 8 tables + 10 marking + 12 aggregate + 1 public API).

- [ ] **Step 5: Commit**

```bash
git add scoring/__init__.py tests/test_public_api.py
git commit -m "feat(scoring): define the public API surface"
```

---

### Task 7: Legacy parity — prove the migration is safe

**Files:**
- Create: `tests/test_legacy_parity.py`, `scoring/legacy.py`

**Interfaces:**
- Consumes: `MarkingTable`, `BandRow`, `mark_numeric`
- Produces:
  ```python
  def sagf_legacy_table() -> MarkingTable
  ```
  The existing SAGF scheme expressed as a single-row `MarkingTable`.

**Why this task exists:** it is the evidence that switching to the new scoring
package does not change any candidate's result, except where it fixes a bug. Without
it, "the new system scores differently" is an argument you cannot win.

**The legacy scheme, derived from `legacy/flask_backend/rhytmic_exam_app/main/exam_utils.py`:**
one mark of 5 for an exact match, then `0.25` fewer marks for each `0.05` of
difference, reaching `0` at a difference of `1.0` and above. As percentages that is
`100, 95, 90, …, 5` for differences `0.00, 0.05, 0.10, …, 0.95`, then `0`.

So: `difference_steps = (0.00, 0.05, 0.10, …, 0.95, 1.00)` — 21 columns — and a
single `BandRow` with `expert_minimum = 0` whose percentages are
`100, 95, 90, …, 5, 0`.

- [ ] **Step 1: Write the parity tests**

| Case | Expected | Reason |
|---|---|---|
| difference `0.00` | `100` | exact match |
| difference `0.05` | `95` | one increment |
| difference `0.50` | `50` | midpoint |
| difference `0.95` | `5` | last scoring band |
| difference `1.00` | `0` | cutoff |
| difference `2.00` | `0` | beyond cutoff |

Then the two **documented divergences** — cases where new behaviour is
deliberately different because the old behaviour was a bug:

| Case | Old behaviour | New behaviour | Finding |
|---|---|---|---|
| expert `0.30`, response `"0.3"` | `0` | `100` | F3 |
| expert `0.30`, response `"0.23"` | `ValueError` | `95` | F4 |

Write those two as ordinary passing tests with a comment naming the finding. They
are the record of what changed and why.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_legacy_parity.py -v`
Expected: fail — `scoring.legacy` does not exist.

- [ ] **Step 3: Write `scoring/legacy.py`**

Build the table. Generate the columns and percentages rather than typing out
twenty-one literals by hand.

- [ ] **Step 4: Run the whole suite**

Run: `pytest -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scoring/legacy.py tests/test_legacy_parity.py
git commit -m "feat(scoring): express the legacy SAGF scheme as a marking table"
```

**Review gate:** Claude reviews, then we run the *old* `get_practical_mark` against
the new table across every difference from 0.00 to 1.50 and diff the results. Any
divergence other than the two documented ones is a bug in the new code.

---

## What this plan deliberately leaves out

- **Difficulty marking and sequence alignment.** Out of scope per the spec —
  Execution only.
- **Anything that loads a table from a database.** Tables arrive as arguments.
  Persistence is the next plan's problem.
- **`score_sitting`.** It needs a `SittingItem`, which does not exist yet. It
  belongs in the plan that introduces the Django models.

## Next plans, in order

1. **Django project and the questions app** — models, admin, content blocks, media
   upload.
2. **Exams, sittings and the freeze** — including the snapshot integrity test that
   makes F1 an executable guarantee.
3. **Accounts, allauth and the roster** — Google OIDC, eligibility rules.
4. **The React island** — the practical runner. Last, because everything before it
   settles its requirements.

## Self-review notes

- **Spec coverage:** this plan covers the spec's "Scoring" section and findings
  F3, F4, F5, F6. F1, F2, F7, F8 belong to plans 2 and 3 above and are listed
  there. No scoring requirement is unaddressed.
- **Type consistency:** `MarkingTable`, `BandRow`, `GradeBand`, `to_decimal`,
  `UnparseableAnswer`, `mark_choice`, `mark_numeric`, `score_component`, `grade`
  are used with identical names and signatures in Tasks 3–7 and in
  `scoring/__init__.py`.
- **Deliberate format deviation:** implementation bodies are omitted by
  instruction. Test cases are fully specified so each task remains verifiable.
