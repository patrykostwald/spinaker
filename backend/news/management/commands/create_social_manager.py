import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from news.account_mail import send_account_mail


class Command(BaseCommand):
    help = 'Tworzy konto social bez hasła i wysyła jednorazowy link do ustawienia hasła.'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--name', required=True)

    def handle(self, *args, **options):
        email, name = options['email'].strip().lower(), options['name'].strip()
        try:
            validate_email(email)
        except ValidationError:
            raise CommandError('Podaj poprawny e-mail.') from None
        if not name or len(name) > 150:
            raise CommandError('Imię musi mieć od 1 do 150 znaków.')
        if len(email) > 254:
            raise CommandError('E-mail może mieć najwyżej 254 znaki.')
        with transaction.atomic():
            if get_user_model().objects.filter(email__iexact=email).exists():
                raise CommandError('Konto z tym adresem już istnieje. Nie zmieniono jego uprawnień ani hasła.')
            user = get_user_model().objects.create_user(username='social_' + secrets.token_hex(12),
                email=email, first_name=name, password=None, is_staff=False, is_superuser=False)
            user.groups.add(Group.objects.get_or_create(name='social')[0])
        url = settings.ACCOUNT_PUBLIC_URL.rstrip('/') + '/panel/social/haslo?' + urlencode({
            'uid': urlsafe_base64_encode(force_bytes(user.pk)), 'token': default_token_generator.make_token(user)})
        if send_account_mail(email, 'Dostęp do social media spin.clinic',
                f'Ustaw hasło do konta social: {url}\n\nLink jest jednorazowy. Potem zaloguj się adresem e-mail w /panel/social.'):
            self.stdout.write(self.style.SUCCESS('Konto social utworzone. Wysłano link do ustawienia hasła.'))
        else:
            self.stdout.write('Konto social utworzone. Poczta jest niedostępna. Jednorazowy link do ustawienia hasła:')
            self.stdout.write(url)
