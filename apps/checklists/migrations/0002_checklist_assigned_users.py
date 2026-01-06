# Generated manually

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('checklists', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='checklist',
            name='assigned_users',
            field=models.ManyToManyField(
                blank=True,
                help_text='Selecione os colaboradores que devem executar este checklist. Deixe vazio para tornar global (todos os colaboradores da empresa).',
                related_name='assigned_checklists',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Usuários Atribuídos'
            ),
        ),
    ]

