"""Konto testera podglądu fazy 2: zwykły użytkownik (bez uprawnień personelu) w grupie „testerzy”, z potwierdzonym e-mailem."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news.account_models import AccountIdentity
from news.preview import TESTERS_GROUP


class Command(BaseCommand):
    help = 'Zakłada albo aktualizuje konto testera: create_tester LOGIN --password HASŁO [--email ADRES]'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--password', required=True)
        parser.add_argument('--email', default='')

    def handle(self, *args, username, password, email, **options):
        username = username.strip().lower()
        if not username.replace('_', '').isalnum() or not 3 <= len(username) <= 30:
            raise CommandError('Login: 3–30 znaków, litery bez polskich znaków, cyfry lub podkreślenie.')
        user, created = get_user_model().objects.get_or_create(username=username, defaults={'is_staff': False, 'is_superuser': False})
        user.set_password(password)
        user.is_active = True
        user.save()
        user.groups.add(Group.objects.get_or_create(name=TESTERS_GROUP)[0])
        AccountIdentity.objects.update_or_create(user=user, defaults={
            'email': email or f'{username}@testerzy.spin.clinic', 'email_verified': True,
            'accepted_terms_version': '2026-09-30', 'accepted_privacy_version': '2026-09-30', 'accepted_at': timezone.now()})
        self.stdout.write(f"{'Utworzono' if created else 'Zaktualizowano'} testera {username} (grupa „{TESTERS_GROUP}”, bez uprawnień personelu).")
