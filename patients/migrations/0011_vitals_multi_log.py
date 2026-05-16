from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("patients", "0010_make_notes_issued_by_nullable"),
    ]

    operations = [
        # 1. Add new nullable fields before changing the relation
        migrations.AddField(
            model_name="vitals",
            name="label",
            field=models.CharField(
                blank=True,
                null=True,
                max_length=100,
                help_text="E.g. 'Morning', 'Evening', 'Day 2 AM'",
            ),
        ),
        migrations.AddField(
            model_name="vitals",
            name="recorded_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text="When this vitals reading was taken",
            ),
        ),
        # 2. Remove the unique constraint implicit in OneToOneField
        #    by altering to a plain ForeignKey.
        migrations.AlterField(
            model_name="vitals",
            name="visitation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="vitals",
                to="patients.visitation",
            ),
        ),
    ]
