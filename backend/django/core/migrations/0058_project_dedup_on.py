# Generated by Django 3.2.3 on 2021-09-01 13:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0057_metadatafield_use_with_dedup'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='dedup_on',
            field=models.CharField(choices=[('Text', 'Text only'), ('ID', 'Unique ID Only (not valid if data does not have ID field)'), ('Metadata_Text', 'Text and all Metadata fields'), ('Text_Some_Metadata', 'Text and selected Metadata fields')], default='Text', max_length=19),
        ),
    ]
