from decimal import Decimal

from exams.models import ExamComponent
from scoring.types import BandRow, GradeBand, MarkingTable


def build_marking_table(component: ExamComponent) -> MarkingTable:
    difference_steps = tuple(component.difference_steps)
    rows = tuple(
        BandRow(expert_minimum=row.expert_minimum, percentages=tuple(row.percentages))
        for row in component.marking_rows.all()
    )
    return MarkingTable(difference_steps=difference_steps, rows=rows)


def build_grade_bands(component: ExamComponent) -> list[GradeBand]:
    return [
        GradeBand(name=row.name, minimum=row.minimum)
        for row in component.grade_bands.all()
    ]


def marking_table_as_json(table: MarkingTable) -> dict:
    return {
        "difference_steps": [str(step) for step in table.difference_steps],
        "rows": [
            {
                "expert_minimum": str(row.expert_minimum),
                "percentages": [str(p) for p in row.percentages],
            }
            for row in table.rows
        ],
    }


def marking_table_from_json(data: dict) -> MarkingTable:
    return MarkingTable(
        difference_steps=tuple(Decimal(step) for step in data["difference_steps"]),
        rows=tuple(
            BandRow(
                expert_minimum=Decimal(row["expert_minimum"]),
                percentages=tuple(Decimal(p) for p in row["percentages"]),
            )
            for row in data["rows"]
        ),
    )


def grade_bands_as_json(bands: list[GradeBand]) -> list[dict]:
    return [{"name": band.name, "minimum": str(band.minimum)} for band in bands]


def grade_bands_from_json(data: list[dict]) -> list[GradeBand]:
    return [
        GradeBand(name=row["name"], minimum=Decimal(row["minimum"])) for row in data
    ]
