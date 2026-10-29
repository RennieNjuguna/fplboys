from django.db import migrations


def run_fix_neglected_fines(apps, schema_editor):
    from treasury.services.payment_allocation import audit_and_fix_neglected_fines
    audit_and_fix_neglected_fines()


def reverse_fix(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('treasury', '0008_transactionallocation_allocation_type'),
    ]

    operations = [
        migrations.RunPython(run_fix_neglected_fines, reverse_fix),
    ]
