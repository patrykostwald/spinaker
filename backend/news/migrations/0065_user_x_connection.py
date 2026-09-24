from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('news', '0064_public_figure_roster_link')]

    operations = [
        migrations.CreateModel(
            name='UserXConnection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('x_user_id', models.CharField(max_length=32, unique=True)),
                ('username', models.CharField(max_length=15)),
                ('connected_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='x_connection', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
