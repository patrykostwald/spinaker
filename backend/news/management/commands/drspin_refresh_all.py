"""Przepisanie wszystkich spinek Dr. Spina według jednego szablonu (właściciel 5.10): tytuł „Rodzaj: synteza”,
podtytuł „co zbadano. co znaleziono.”, diagnozy jako łańcuch rozumowania. Bez wywołań AI; Redaktor tytułów
poprawi teksty później w zwykłej recenzji (ta sama reguła)."""
from django.core.management.base import BaseCommand

from news.account_models import PersonalContextThread
from news.diagnosis_threads import short, sync_diagnosis_thread
from news.thread_review import draft_builder


@draft_builder
def refresh_signal(thread):
    from news.thread_review import enqueue
    from news.thread_review_models import ThreadReview
    data = thread.signal_data or {}
    if thread.signal_kind == 'new_narrative':
        title = short('Nowa narracja: ' + str(data.get('phrase', '')), 65)
        about = short(f"Fraza pojawiła się u {data.get('authors', 'kilku')} autorów. Pokazujemy, kto użył jej pierwszy, oraz kolejne wpisy.", 170)
    elif thread.signal_kind == 'lobbying':
        number = data.get('print', '')
        title = short(f'Sygnał lobbingu: druk {number}', 65)
        about = (f'Analiza druku {number}: zgłoszone zapisy zestawione ze stanowiskami organizacji. '
                 'Zbieżność tekstu nie wskazuje autora ani przyczyny.')
    else:
        return False
    if (thread.title, thread.description) == (title, about):
        return False
    thread.title, thread.description = title, about
    thread.save(update_fields=['title', 'description', 'updated_at'])
    review = ThreadReview.objects.filter(thread=thread).first()
    enqueue(thread, review.payload.get('evidence', {}) if review else {})
    return True


class Command(BaseCommand):
    help = 'Przepisz wszystkie spinki Dr. Spina według jednego szablonu (diagnozy, przekazy dnia, nowe narracje, lobbing).'

    def handle(self, *args, **options):
        from news.narrative_threads import sync_message
        diagnoses = narratives = signals = 0
        for pk in PersonalContextThread.objects.filter(diagnosis__isnull=False).values_list('diagnosis_id', flat=True).iterator():
            if sync_diagnosis_thread(pk, force_text=True):
                diagnoses += 1
        for pk in PersonalContextThread.objects.filter(narrative_message__isnull=False).values_list('narrative_message_id', flat=True).iterator():
            if sync_message(pk):
                narratives += 1
        for thread in PersonalContextThread.objects.filter(owner__isnull=True).exclude(signal_kind=''):
            if refresh_signal(thread):
                signals += 1
        self.stdout.write(self.style.SUCCESS(
            f'Przepisano: {diagnoses} spinek z diagnoz, {narratives} przekazów dnia, {signals} sygnałów (nowe narracje i lobbing).'))
