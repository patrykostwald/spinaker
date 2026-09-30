import base64
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Wypisz klucze VAPID do .env.production; nie zapisuj plików.'

    def handle(self, *args, **options):
        try:
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        except ImportError as exc:
            raise CommandError('Brak cryptography w środowisku.') from exc
        key = ec.generate_private_key(ec.SECP256R1())
        encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b'=').decode()
        self.stdout.write('VAPID_PUBLIC_KEY=' + encode(key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)))
        self.stdout.write('VAPID_PRIVATE_KEY=' + encode(key.private_numbers().private_value.to_bytes(32, 'big')))
