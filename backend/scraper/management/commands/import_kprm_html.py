import json
import time
from django.core.management.base import BaseCommand, CommandError
from scraper.html_archive import run_kprm_listing
from news.models import Source

class Command(BaseCommand):
    help = 'Import a bounded number of explicit KPRM HTML listing pages into the archive URL queue.'
    def add_arguments(self, parser):
        parser.add_argument('--source-id',type=int,required=True)
        parser.add_argument('--pages',type=int,default=1)
    def handle(self,*args,**options):
        if not 1 <= options['pages'] <= 10: raise CommandError('Use 1..10 pages per run.')
        for index in range(options['pages']):
            if index: time.sleep(3)
            try: result = run_kprm_listing(options['source_id'])
            except Source.DoesNotExist: raise CommandError('Source ID does not exist.')
            self.stdout.write(json.dumps(result,ensure_ascii=False))
            if result['status'] != 'ok': break
