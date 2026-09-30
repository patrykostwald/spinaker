"""Stały token strony Facebook (i identyfikator konta Instagram) z krótkiego tokenu użytkownika.

  python manage.py meta_setup <krótki_token_z_Graph_API_Explorer>

Wymaga META_APP_ID i META_APP_SECRET w .env.production. Krótki token (ważny ok. godzinę) wymieniamy na długi token
użytkownika, a z niego bierzemy token strony — ten nie wygasa (dopóki nie zmienisz hasła ani nie odbierzesz aplikacji
uprawnień). Wynik wklejasz do .env.production. Nie rób zrzutów ekranu z tokenem i nie wysyłaj go nikomu.
"""
import os

import requests
from django.core.management.base import BaseCommand, CommandError

GRAPH = 'https://graph.facebook.com'


class Command(BaseCommand):
    help = 'Zamienia krótki token Meta na stały token strony i pokazuje wiersze do .env.production.'

    def add_arguments(self, parser):
        parser.add_argument('user_token')

    def handle(self, *args, user_token, **options):
        app_id, secret = os.environ.get('META_APP_ID', '').strip(), os.environ.get('META_APP_SECRET', '').strip()
        version = os.environ.get('META_GRAPH_VERSION', '').strip() or 'v23.0'
        if not app_id or not secret:
            raise CommandError('Brak META_APP_ID albo META_APP_SECRET w .env.production.')
        response = requests.get(f'{GRAPH}/{version}/oauth/access_token', timeout=30, params={
            'grant_type': 'fb_exchange_token', 'client_id': app_id, 'client_secret': secret, 'fb_exchange_token': user_token})
        if response.status_code != 200:
            raise CommandError(f'Wymiana tokenu nie powiodła się: {response.text[:200]}')
        long_user = response.json()['access_token']
        pages = requests.get(f'{GRAPH}/{version}/me/accounts', timeout=30, params={
            'fields': 'id,name,access_token,instagram_business_account{id,username}', 'access_token': long_user}).json()
        rows = pages.get('data') or []
        if not rows:
            raise CommandError(f'Nie widzę żadnej strony. Czy token ma uprawnienia pages_show_list i pages_manage_posts? {str(pages)[:200]}')
        for page in rows:
            self.stdout.write(f"\nStrona: {page['name']}")
            self.stdout.write('Wklej do .env.production:')
            self.stdout.write(f"META_PAGE_ID={page['id']}")
            self.stdout.write(f"META_PAGE_TOKEN={page['access_token']}")
            instagram = page.get('instagram_business_account') or {}
            if instagram.get('id'):
                self.stdout.write(f"META_IG_USER_ID={instagram['id']}   # @{instagram.get('username', '')}")
            else:
                self.stdout.write('# Instagram nie jest połączony z tą stroną (Ustawienia strony → Połączone konta).')
