from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrywatnyMagazynZrzutow(FileSystemStorage):
    def __init__(self):
        super().__init__(file_permissions_mode=0o600, directory_permissions_mode=0o700)

    @property
    def base_location(self):
        return settings.TERAZ_ZRZUTY_ROOT

    @property
    def location(self):
        # Keep settings overrides effective in tests and management commands.
        return str(settings.TERAZ_ZRZUTY_ROOT.resolve())

    def url(self, name):
        raise ValueError("Zrzuty Teraz nie mają publicznego adresu.")
