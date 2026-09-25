import pytest
from django.db import IntegrityError, transaction

from exams.models import CategoryRequirement, Cycle, Dimension


@pytest.fixture
def two_cycles():
    return (
        Cycle.objects.create(name="XVI", first_year=2025, last_year=2028),
        Cycle.objects.create(name="XVII", first_year=2029, last_year=2032),
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("year", "expected"),
    [(2025, "XVI"), (2028, "XVI"), (2029, "XVII"), (2032, "XVII")],
    ids=["first-year", "last-year", "next-first-year", "next-last-year"],
)
def test_a_year_finds_its_cycle(two_cycles, year, expected):
    # Both edges of both cycles: an exclusive comparison at either end moves a
    # boundary year into the wrong cycle or into none.
    assert Cycle.objects.for_year(year).name == expected


@pytest.mark.django_db
def test_a_year_outside_every_cycle_raises(two_cycles):
    with pytest.raises(Cycle.DoesNotExist):
        Cycle.objects.for_year(2040)


@pytest.mark.django_db
def test_a_cycle_cannot_end_before_it_starts():
    with pytest.raises(IntegrityError), transaction.atomic():
        Cycle.objects.create(name="Backwards", first_year=2029, last_year=2025)


@pytest.mark.django_db
def test_a_category_has_one_minimum_per_dimension(two_cycles):
    cycle, _ = two_cycles
    CategoryRequirement.objects.create(
        cycle=cycle,
        category=1,
        dimension=Dimension.DIFFICULTY,
        minimum_grade="Excellent",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        CategoryRequirement.objects.create(
            cycle=cycle,
            category=1,
            dimension=Dimension.DIFFICULTY,
            minimum_grade="Very Good",
        )


@pytest.mark.django_db
@pytest.mark.parametrize("category", [0, 5], ids=["zero", "five"])
def test_a_category_outside_one_to_four_is_refused(two_cycles, category):
    cycle, _ = two_cycles

    with pytest.raises(IntegrityError), transaction.atomic():
        CategoryRequirement.objects.create(
            cycle=cycle,
            category=category,
            dimension=Dimension.EXECUTION,
            minimum_grade="Pass",
        )


@pytest.mark.django_db
def test_an_unknown_dimension_is_refused(two_cycles):
    cycle, _ = two_cycles

    with pytest.raises(IntegrityError), transaction.atomic():
        CategoryRequirement.objects.create(
            cycle=cycle, category=1, dimension="BALANCE", minimum_grade="Pass"
        )
