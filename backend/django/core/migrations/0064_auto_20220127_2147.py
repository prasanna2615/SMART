# Generated by Django 3.2.9 on 2022-01-27 21:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0063_externaldatabase"),
    ]

    operations = [
        migrations.AddField(
            model_name="externaldatabase",
            name="database_type",
            field=models.CharField(
                choices=[("none", "No Database Connection"), ("microsoft", "MS SQL")],
                default="none",
                max_length=9,
            ),
        ),
        migrations.AlterField(
            model_name="externaldatabase",
            name="export_schema",
            field=models.CharField(max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name="externaldatabase",
            name="export_table_name",
            field=models.CharField(max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name="externaldatabase",
            name="ingest_schema",
            field=models.CharField(max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name="externaldatabase",
            name="ingest_table_name",
            field=models.CharField(max_length=50, null=True),
        ),
    ]