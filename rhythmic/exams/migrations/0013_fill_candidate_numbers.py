import secrets

from django.db import migrations


def fill_candidate_numbers(apps, schema_editor):
    # Row by row, each its own number. A callable default on AddField is evaluated
    # ONCE for every existing row, which would give them all the same "unique"
    # number -- Django's how-to, "Migrations that add unique fields". The generator
    # is inlined rather than imported from models.py, which may change later.
    Sitting = apps.get_model("exams", "Sitting")
    for sitting in Sitting.objects.filter(candidate_number__isnull=True):
        taken = set(
            Sitting.objects.filter(exam_id=sitting.exam_id).values_list(
                "candidate_number", flat=True
            )
        )
        number = secrets.token_hex(4).upper()
        while number in taken:
            number = secrets.token_hex(4).upper()
        sitting.candidate_number = number
        sitting.save(update_fields=["candidate_number"])


class Migration(migrations.Migration):
    dependencies = [
        ("exams", "0012_sitting_candidate_number_and_override"),
    ]

    operations = [
        migrations.RunPython(fill_candidate_numbers, migrations.RunPython.noop),
    ]
