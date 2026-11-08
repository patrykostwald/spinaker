"""API REST spina3 v2 (JSON, kursory). Odczyt publiczny z migawki rankingu; zapis tylko dla zalogowanych.

Publiczne API zwraca wyłącznie pola dozwolone flagami praw (spina3.public). Odpowiedzi zapisu (box z przypięciem, ocena)
zawierają przeliczoną spinkę: frontend liczy optymistycznie tą samą funkcją, backend potwierdza, rozjazd nadpisuje widok.
"""
from __future__ import annotations

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.middleware.csrf import get_token
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, PolymorphicProxySerializer, extend_schema
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import comments, metrics, moderation, pins, ranking, ratings, sso, url_queue
from .config import NICK_COLOR_DEFAULT, NICK_COLOR_RESERVED, NICK_COLORS, flags, public_config, public_silence
from .models import Appeal, Box, BoxLink, Comment, Pin, Rating, Report, Spina3Profile, UrlCheck
from .public import box_item, comment_item, pin_item, spinka_payload
from .serializers import (AppealIn, BoxDetailOut, BoxWithPinIn, BoxWithPinOut, CodeIn, CommentCreateOut, CommentIn, CommentPatchIn,
                          CommentOut, CommentsOut, ConsentIn, DecisionIn, PinPatchIn, PinPatchOut, ProfileIn, ProfileOut, RatingIn,
                          RatingOut, ReportIn, SearchOut, UrlDecisionIn, WallOut, ConfigOut, SilenceOut,
                          GuestProfileOut, MyBoxesOut, MyRatingsOut)
from .sso import SsoBearerAuthentication
from .throttles import (AuthExchangeThrottle, CommentsReadThrottle, CommentWriteThrottle, PinWriteThrottle, RatingWriteThrottle,
                        RelatedThrottle, ReportThrottle, SearchThrottle, WallThrottle)
from .trust import trust_for

TAG = 'spina3'
TEAM = 'spina3 zespół'


class Spina3View(APIView):
    """Sesja (domyślnie) albo token Bearer ze wspólnego logowania (auth_mode=token)."""
    authentication_classes = [SsoBearerAuthentication, SessionAuthentication]


def _error(exc):
    return Response({'detail': exc.detail, 'code': getattr(exc, 'code', '')}, status=exc.status)


def _disabled():
    if not flags().enabled:
        return Response({'detail': 'spina3 jest wyłączone.'}, status=404)
    return None


def _my_rating(user, pin: Pin | None) -> int | None:
    row = ratings.my_rating(user, pin) if pin is not None else None
    return row.stance if row else None


QUESTIONS = {'diagnosis': 'Czy zgadzasz się z diagnozą Dr. Spina?', 'url': 'Czy ten dowód potwierdza tezę autora?',
             'box': 'Czy ten dowód potwierdza tezę autora?', 'image': 'Czy to zdjęcie potwierdza tezę autora?'}


# --- odczyt ---------------------------------------------------------------------------------------------------

class ConfigView(Spina3View):
    permission_classes = [AllowAny]

    @extend_schema(summary='Publiczna konfiguracja modelu oceny, kolory nicków, flagi i stan ciszy wyborczej', tags=[TAG], responses=ConfigOut)
    def get(self, request):
        return Response({**public_config(), 'csrf_token': get_token(request)}, headers={'Cache-Control': 'no-store'})


class SilenceView(Spina3View):
    permission_classes = [AllowAny]

    @extend_schema(summary='Stan ciszy wyborczej (co jest wstrzymane)', tags=[TAG], responses=SilenceOut)
    def get(self, request):
        return Response({'election_silence': public_silence()})


class WallView(Spina3View):
    permission_classes = [AllowAny]
    throttle_classes = [WallThrottle]

    @extend_schema(summary='Ściana kafelków z migawki rankingu (kursor z wersją); kafelek = box + skrót przypięcia + spinka z ocen', tags=[TAG],
                   responses=WallOut, parameters=[
                       OpenApiParameter('cursor', str), OpenApiParameter('sort', str, description='level | newest | today (domyślnie wg min_rated_share)'),
                       OpenApiParameter('type', str, description='all | post | diagnosis | article | video | documents'),
                       OpenApiParameter('person', str), OpenApiParameter('topic', str), OpenApiParameter('level', str),
                       OpenApiParameter('doc_kind', str), OpenApiParameter('period', int), OpenApiParameter('with_diagnosis', bool),
                       OpenApiParameter('limit', int)])
    def get(self, request):
        if (blocked := _disabled()) is not None:
            return blocked
        params = request.query_params
        try:
            limit = int(params.get('limit') or 0) or None
            period = int(params['period']) if params.get('period') else None
        except ValueError:
            return Response({'detail': 'limit i period muszą być liczbami.'}, status=400)
        data = ranking.wall(cursor=params.get('cursor'), sort=params.get('sort'), kind=params.get('type'),
                            facets=ranking.parse_facets(params), limit=limit, period_days=period, user=request.user)
        if data.get('error'):
            return Response({'detail': data['error']}, status=data.get('status', 400))
        if not params.get('cursor'):
            data['today'] = ranking.today_row()
        return Response(data)


class FacetsView(Spina3View):
    permission_classes = [AllowAny]
    throttle_classes = [WallThrottle]

    @extend_schema(summary='Liczności wymiarów (osoba lub podmiot, temat, okres, poziom, rodzaj dokumentu lub źródło, z diagnozą)',
                   tags=[TAG], responses=OpenApiTypes.OBJECT, parameters=[OpenApiParameter('type', str), OpenApiParameter('period', int)])
    def get(self, request):
        if (blocked := _disabled()) is not None:
            return blocked
        period = request.query_params.get('period')
        return Response(ranking.facets(kind=request.query_params.get('type'), period_days=int(period) if period else None))


class SearchView(Spina3View):
    permission_classes = [AllowAny]
    throttle_classes = [SearchThrottle]

    @extend_schema(summary='Wyszukiwanie z normalizacją polskich znaków; wynik w strukturze ściany', tags=[TAG],
                   responses=SearchOut, parameters=[OpenApiParameter('q', str, required=True), OpenApiParameter('limit', int)])
    def get(self, request):
        if (blocked := _disabled()) is not None:
            return blocked
        q = (request.query_params.get('q') or '').strip()
        if len(q) < 2:
            return Response({'items': [], 'suggestions': [], 'query': q, 'detail': 'Wpisz co najmniej 2 znaki.'})
        limit = min(int(request.query_params.get('limit') or 48), 96)
        return Response(ranking.search(q, limit=limit, user=request.user))


class BoxView(Spina3View):
    permission_classes = [AllowAny]
    throttle_classes = [WallThrottle]

    @extend_schema(summary='Box, jedyne przypięcie autora z ocenami, spinka, moja ocena, czy mogę przypiąć lub ocenić', tags=[TAG], responses=BoxDetailOut)
    def get(self, request, box_id):
        if (blocked := _disabled()) is not None:
            return blocked
        box = get_object_or_404(Box.objects.select_related('spinka'), pk=box_id, status='published')
        metrics.count_view(box)
        pin = Pin.objects.filter(box=box, status='published').select_related('user__spina3_profile', 'pinned_box__spinka').first()
        mine = _my_rating(request.user, pin)
        sp = getattr(box, 'spinka', None)
        data = box_item(box, sp, my_rating=mine, detail=True, pin=pin,
                        has_diagnosis=BoxLink.objects.filter(box=box, kind='diagnosis_of', is_current=True).exists())
        user = request.user
        can_pin = can_rate = False
        if user.is_authenticated:
            fl = flags()
            if pin is None and not Pin.objects.filter(box=box).exclude(status='removed').exists() and box.source_status == 'active':
                own_box = box.added_by == 'user' and box.added_by_user_id == user.pk
                can_pin = fl.pins_enabled and (own_box or (box.added_by != 'user' and fl.adopt_authorless_boxes))
            can_rate = bool(pin and fl.ratings_enabled and pin.ratable and pin.user_id != user.pk and box.source_status == 'active')
        data.update({
            'pin': pin_item(pin, viewer=user, my_rating=mine, sp=sp) if pin else None,
            'can_pin': can_pin, 'can_rate': can_rate,
            'question': QUESTIONS.get(pin.kind, QUESTIONS['box']) if pin else 'Ten box nie ma jeszcze przypięcia.',
            'diagnosis_history': [{'version': l.version, 'target_id': l.target_id, 'current': l.is_current, 'created_at': l.created_at.isoformat()}
                                  for l in BoxLink.objects.filter(box=box, kind='diagnosis_of').order_by('version')],
        })
        return Response(data)


class RelatedView(Spina3View):
    permission_classes = [AllowAny]
    throttle_classes = [RelatedThrottle]

    @extend_schema(summary='Półka podobnych (do 6): dla wpisu najpierw diagnoza i dokumenty źródłowe', tags=[TAG], responses=OpenApiTypes.OBJECT)
    def get(self, request, box_id):
        if (blocked := _disabled()) is not None:
            return blocked
        box = get_object_or_404(Box, pk=box_id, status='published')
        return Response({'items': ranking.related(box, user=request.user)})


# --- box z przypięciem (autor) ----------------------------------------------------------------------------------

class BoxCreateView(Spina3View):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PinWriteThrottle]

    @extend_schema(summary='Dodaj box z JEDNYM przypięciem (jedna operacja): kotwica (box z bazy bez przypięcia | URL | zdjęcie) + dowód (box | URL | zdjęcie) z komentarzem',
                   tags=[TAG], request=BoxWithPinIn, responses={201: BoxWithPinOut, 403: OpenApiTypes.OBJECT, 409: OpenApiTypes.OBJECT, 423: OpenApiTypes.OBJECT, 429: OpenApiTypes.OBJECT})
    def post(self, request):
        if (blocked := _disabled()) is not None:
            return blocked
        data = BoxWithPinIn(data=request.data)
        data.is_valid(raise_exception=True)
        b, p = data.validated_data['box'], data.validated_data['pin']
        try:
            box, pin, info = pins.create_box_with_pin(
                request.user, box_kind=b['kind'], box_target=b['target'], box_title=b.get('title', ''), box_type=b.get('type', 'article'),
                pin_kind=p['kind'], pin_target=p['target'], comment=p.get('comment', ''), title=p.get('title', ''), subtitle=p.get('subtitle', ''), stance=p.get('stance'))
        except pins.PinError as exc:
            return _error(exc)
        sp = info['spinka']
        payload = {'box': box_item(box, sp, pin=pin, comment_count=0), 'pin': pin_item(pin, viewer=request.user, sp=sp),
                   'spinka': spinka_payload(sp), **{k: v for k, v in info.items() if k != 'spinka'}}
        return Response(payload, status=status.HTTP_201_CREATED)


class PinDetailView(Spina3View):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PinWriteThrottle]

    @extend_schema(summary='Edytuj własne przypięcie (komentarz, stanowisko autora raz na 24 h, wymiana dowodu)', tags=[TAG], request=PinPatchIn, responses=PinPatchOut)
    def patch(self, request, pin_id):
        pin = get_object_or_404(Pin.objects.select_related('box__spinka'), pk=pin_id)
        data = PinPatchIn(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        try:
            pin, info = pins.update_pin(request.user, pin, stance=v.get('stance'), comment=v.get('comment'), title=v.get('title'), subtitle=v.get('subtitle'), kind=v.get('kind'), target=v.get('target'))
        except pins.PinError as exc:
            return _error(exc)
        sp = info['spinka']
        return Response({'pin': pin_item(pin, viewer=request.user, sp=sp), 'spinka': spinka_payload(sp), **{k: v for k, v in info.items() if k != 'spinka'}})

    @extend_schema(summary='Usuń własne przypięcie (box dodany przez autora znika ze ściany; oceny przestają się liczyć)', tags=[TAG], responses={204: None})
    def delete(self, request, pin_id):
        pin = get_object_or_404(Pin, pk=pin_id)
        try:
            pins.remove_pin(request.user, pin)
        except pins.PinError as exc:
            return _error(exc)
        return Response(status=204)


# --- oceny -----------------------------------------------------------------------------------------------------

class RatingView(Spina3View):
    permission_classes = [IsAuthenticated]
    throttle_classes = [RatingWriteThrottle]

    @extend_schema(summary='Oceń przypięcie autora: zgadzam się | nie zgadzam się (tworzy albo zmienia; 403 własne, 409 dowód niedostępny, 429 limit)',
                   tags=[TAG], request=RatingIn, responses={200: RatingOut, 403: OpenApiTypes.OBJECT, 409: OpenApiTypes.OBJECT, 423: OpenApiTypes.OBJECT, 429: OpenApiTypes.OBJECT})
    def put(self, request, pin_id):
        if (blocked := _disabled()) is not None:
            return blocked
        pin = get_object_or_404(Pin.objects.select_related('box__spinka'), pk=pin_id)
        data = RatingIn(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            rating, info = ratings.set_rating(request.user, pin, data.validated_data['stance'])
        except pins.PinError as exc:
            return _error(exc)
        sp = info['spinka']
        return Response({'my_rating': {1: 'agree', -1: 'disagree'}[rating.stance], 'changed': info['changed'], 'spinka': spinka_payload(sp),
                         'pin': pin_item(pin, viewer=request.user, my_rating=rating.stance, sp=sp)})

    @extend_schema(summary='Wycofaj swoją ocenę', tags=[TAG], responses={200: RatingOut, 404: OpenApiTypes.OBJECT})
    def delete(self, request, pin_id):
        pin = get_object_or_404(Pin.objects.select_related('box__spinka'), pk=pin_id)
        try:
            info = ratings.withdraw_rating(request.user, pin)
        except pins.PinError as exc:
            return _error(exc)
        sp = info['spinka']
        return Response({'my_rating': None, 'changed': True, 'spinka': spinka_payload(sp), 'pin': pin_item(pin, viewer=request.user, sp=sp)})


# --- komentarze --------------------------------------------------------------------------------------------------

class CommentsView(Spina3View):
    permission_classes = [AllowAny]

    def get_throttles(self):
        return [CommentWriteThrottle()] if self.request.method == 'POST' else [CommentsReadThrottle()]

    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method == 'POST' else [AllowAny()]

    @extend_schema(summary='Komentarze pod parą box + przypięcie: główne z odpowiedziami, sort newest | top, kursor', tags=[TAG], responses=CommentsOut,
                   parameters=[OpenApiParameter('sort', str), OpenApiParameter('cursor', str), OpenApiParameter('limit', int)])
    def get(self, request, box_id):
        if (blocked := _disabled()) is not None:
            return blocked
        box = get_object_or_404(Box, pk=box_id, status='published')
        try:
            limit = int(request.query_params.get('limit') or 0) or None
        except ValueError:
            return Response({'detail': 'limit musi być liczbą.'}, status=400)
        data = comments.list_comments(box, sort=request.query_params.get('sort') or 'newest', cursor=request.query_params.get('cursor'),
                                      limit=limit, viewer=request.user)
        if data.get('error'):
            return Response({'detail': data['error']}, status=data.get('status', 400))
        return Response(data)

    @extend_schema(summary='Dodaj komentarz (parent = odpowiedź do komentarza głównego); 409 duplikat, 423 cisza, 429 limit', tags=[TAG],
                   request=CommentIn, responses={201: CommentCreateOut, 400: OpenApiTypes.OBJECT, 423: OpenApiTypes.OBJECT, 429: OpenApiTypes.OBJECT})
    def post(self, request, box_id):
        if (blocked := _disabled()) is not None:
            return blocked
        box = get_object_or_404(Box, pk=box_id)
        data = CommentIn(data=request.data)
        data.is_valid(raise_exception=True)
        parent = None
        if data.validated_data.get('parent'):
            parent = Comment.objects.filter(pk=data.validated_data['parent']).first()
            if parent is None:
                return Response({'detail': 'Nie ma takiego komentarza.', 'code': 'parent'}, status=404)
        try:
            comment, info = comments.create_comment(request.user, box, data.validated_data['text'], parent=parent)
        except pins.PinError as exc:
            return _error(exc)
        return Response({'comment': comment_item(comment, viewer=request.user, replies=[]), **info}, status=201)


class CommentDetailView(Spina3View):
    permission_classes = [IsAuthenticated]
    throttle_classes = [CommentWriteThrottle]

    @extend_schema(summary='Edytuj własny komentarz', tags=[TAG], request=CommentPatchIn, responses=CommentCreateOut)
    def patch(self, request, comment_id):
        comment = get_object_or_404(Comment, pk=comment_id)
        data = CommentPatchIn(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            comment, info = comments.edit_comment(request.user, comment, data.validated_data['text'])
        except pins.PinError as exc:
            return _error(exc)
        return Response({'comment': comment_item(comment, viewer=request.user), **info})

    @extend_schema(summary='Usuń własny komentarz', tags=[TAG], responses={204: None})
    def delete(self, request, comment_id):
        comment = get_object_or_404(Comment, pk=comment_id)
        try:
            comments.remove_comment(request.user, comment)
        except pins.PinError as exc:
            return _error(exc)
        return Response(status=204)


class CommentHelpfulView(Spina3View):
    permission_classes = [IsAuthenticated]
    throttle_classes = [RatingWriteThrottle]

    @extend_schema(summary='Oznacz komentarz jako przydatny', tags=[TAG], responses=CommentOut)
    def put(self, request, comment_id):
        comment = get_object_or_404(Comment, pk=comment_id)
        try:
            comment = comments.vote_helpful(request.user, comment)
        except pins.PinError as exc:
            return _error(exc)
        return Response(comment_item(comment, viewer=request.user, voted={comment.pk}))

    @extend_schema(summary='Cofnij "przydatny"', tags=[TAG], responses=CommentOut)
    def delete(self, request, comment_id):
        comment = get_object_or_404(Comment, pk=comment_id)
        comment = comments.unvote_helpful(request.user, comment)
        return Response(comment_item(comment, viewer=request.user))


class CommentAppealView(Spina3View):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Odwołanie od ukrycia własnego komentarza (jedno na decyzję, 14 dni)', tags=[TAG], request=AppealIn, responses={201: OpenApiTypes.OBJECT})
    def post(self, request, comment_id):
        comment = get_object_or_404(Comment, pk=comment_id)
        data = AppealIn(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            row = moderation.appeal(request.user, comment=comment, text=data.validated_data['text'])
        except moderation.ModerationError as exc:
            return Response({'detail': exc.detail}, status=exc.status)
        return Response({'id': row.pk, 'status': row.status}, status=201)


# --- moje -------------------------------------------------------------------------------------------------------

class MyBoxesView(Spina3View):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Moje boxy (tylko właściciel konta)', tags=[TAG], responses=MyBoxesOut)
    def get(self, request):
        rows = Pin.objects.filter(user=request.user).exclude(status='removed').select_related(
            'box__spinka', 'pinned_box__spinka', 'user__spina3_profile').order_by('-created_at')
        return Response({'items': [box_item(pin.box, pin=pin) for pin in rows]})


class MyRatingsView(Spina3View):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Moje oceny (tylko właściciel konta)', tags=[TAG], responses=MyRatingsOut)
    def get(self, request):
        rows = Rating.objects.filter(user=request.user, status='active').select_related(
            'pin__box__spinka', 'pin__user__spina3_profile', 'pin__pinned_box').order_by('-created_at')
        return Response({'items': [
            {'box_id': rating.box_id, 'pin_id': rating.pin_id,
             'stance': {1: 'agree', -1: 'disagree'}[rating.stance], 'created_at': rating.created_at.isoformat(),
             'box': box_item(rating.pin.box, my_rating=rating.stance, pin=rating.pin)}
            for rating in rows]})


class ProfileView(Spina3View):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == 'GET' else [IsAuthenticated()]

    def _payload(self, request, profile):
        trust = trust_for(request.user)
        return {'nick': request.user.username, 'nick_color': profile.nick_color or ('spin' if profile.is_system else NICK_COLOR_DEFAULT),
                'badge': profile.badge, 'consent_art9': bool(profile.consent_art9_at), 'tier': trust.tier,
                'limits': {'daily_pins': trust.daily_limit, 'daily_ratings': trust.daily_ratings, 'daily_comments': trust.daily_comments},
                'public_profile': False, 'nick_colors': sorted(NICK_COLORS)}

    @extend_schema(summary='Mój profil spina3: kolor nicku, znaczek, zgoda, poziom i limity (nigdy publiczne)', tags=[TAG], responses=PolymorphicProxySerializer(
                       component_name='ProfileResponse', serializers=[ProfileOut, GuestProfileOut], resource_type_field_name=None))
    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'nick': None, 'anonymous': True, 'consent': False})
        return Response(self._payload(request, Spina3Profile.for_user(request.user)))

    @extend_schema(summary='Ustaw kolor nicku z listy dozwolonych identyfikatorów (spin zarezerwowany dla Dr. Spina: 403)', tags=[TAG], request=ProfileIn, responses=ProfileOut)
    def patch(self, request):
        raw = str(request.data.get('nick_color') or '')
        if raw in NICK_COLOR_RESERVED:
            return Response({'detail': 'Ten kolor jest zarezerwowany dla Dr. Spina.', 'code': 'reserved'}, status=403)
        data = ProfileIn(data=request.data)
        data.is_valid(raise_exception=True)
        profile = Spina3Profile.for_user(request.user)
        profile.nick_color = data.validated_data['nick_color']
        profile.save(update_fields=['nick_color'])
        return Response(self._payload(request, profile))


class ConsentView(Spina3View):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Zgoda przed pierwszą publikacją (stanowiska i komentarze publiczne przy nicku, bez profilu)', tags=[TAG], request=ConsentIn, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        data = ConsentIn(data=request.data)
        data.is_valid(raise_exception=True)
        profile = Spina3Profile.for_user(request.user)
        profile.consent_art9_at = timezone.now() if data.validated_data['accepted'] else None
        profile.save(update_fields=['consent_art9_at'])
        return Response({'consent_art9': bool(profile.consent_art9_at)})


class ReportView(Spina3View):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ReportThrottle]

    @extend_schema(summary='Zgłoś przypięcie, box albo komentarz (kategorie DSA, SLA 24 h dla pilnych)', tags=[TAG], request=ReportIn, responses={201: OpenApiTypes.OBJECT})
    def post(self, request):
        data = ReportIn(data=request.data)
        if not data.is_valid() and 'good_faith' in data.errors:
            return Response({'detail': 'Potwierdź działanie w dobrej wierze.', 'code': 'good_faith'}, status=400)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        pin = get_object_or_404(Pin, pk=v['pin']) if v.get('pin') else None
        box = get_object_or_404(Box, pk=v['box']) if v.get('box') else None
        comment = get_object_or_404(Comment, pk=v['comment']) if v.get('comment') else None
        try:
            row = moderation.report(request.user, pin=pin, box=box, comment=comment, reason=v['reason'], details=v.get('details', ''),
                                    name=v['name'], email=v['email'], good_faith=v['good_faith'],
                                    location=v['location'], explanation=v['explanation'])
        except moderation.ModerationError as exc:
            return Response({'detail': exc.detail}, status=exc.status)
        return Response({'id': row.pk, 'status': row.status, 'sla_deadline': row.sla_deadline}, status=201)


class AppealView(Spina3View):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Odwołanie od ukrycia własnego przypięcia (jedno na decyzję, 14 dni)', tags=[TAG], request=AppealIn, responses={201: OpenApiTypes.OBJECT})
    def post(self, request, pin_id):
        pin = get_object_or_404(Pin, pk=pin_id)
        data = AppealIn(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            row = moderation.appeal(request.user, pin=pin, text=data.validated_data['text'])
        except moderation.ModerationError as exc:
            return Response({'detail': exc.detail}, status=exc.status)
        return Response({'id': row.pk, 'status': row.status}, status=201)


# --- zespół ---------------------------------------------------------------------------------------------------

class ModerationQueueView(Spina3View):
    permission_classes = [IsAdminUser]

    @extend_schema(summary='Kolejki zespołu: zgłoszenia z SLA, odwołania, adresy, komentarze wstrzymane, boxy oczekujące', tags=[TEAM], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(moderation.queue())


class ReportDecisionView(Spina3View):
    permission_classes = [IsAdminUser]

    @extend_schema(summary='Decyzja w sprawie zgłoszenia (hide | dismiss) z uzasadnieniem', tags=[TEAM], request=DecisionIn, responses=OpenApiTypes.OBJECT)
    def post(self, request, report_id):
        row = get_object_or_404(Report, pk=report_id)
        data = DecisionIn(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            moderation.decide_report(row, request.user, data.validated_data['decision'], data.validated_data['reason'],
                                     sanction=data.validated_data.get('sanction', ''))
        except moderation.ModerationError as exc:
            return Response({'detail': exc.detail}, status=exc.status)
        return Response({'id': row.pk, 'status': row.status})


class AppealDecisionView(Spina3View):
    permission_classes = [IsAdminUser]

    @extend_schema(summary='Decyzja w sprawie odwołania (accept | reject) z uzasadnieniem', tags=[TEAM], request=DecisionIn, responses=OpenApiTypes.OBJECT)
    def post(self, request, appeal_id):
        row = get_object_or_404(Appeal, pk=appeal_id)
        data = DecisionIn(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            moderation.decide_appeal(row, request.user, data.validated_data['decision'], data.validated_data['reason'])
        except moderation.ModerationError as exc:
            return Response({'detail': exc.detail}, status=exc.status)
        return Response({'id': row.pk, 'status': row.status})


class UrlDecisionView(Spina3View):
    permission_classes = [IsAdminUser]

    @extend_schema(summary='Decyzja w sprawie adresu z kolejki (accept publikuje box kotwicę albo tworzy box z linku; reject: box ukryty, dowód 7 dni na wymianę)',
                   tags=[TEAM], request=UrlDecisionIn, responses=OpenApiTypes.OBJECT)
    def post(self, request, check_id):
        row = get_object_or_404(UrlCheck, pk=check_id)
        data = UrlDecisionIn(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        if row.status in ('accepted', 'rejected', 'duplicate'):
            return Response({'detail': 'Ten adres ma już decyzję.'}, status=409)
        url_queue.decide(row, request.user, v['decision'], v.get('reason', ''), title=v.get('title', ''), kind=v.get('kind', 'article'))
        return Response({'id': row.pk, 'status': row.status, 'box_id': row.box_id})


class PinHideView(Spina3View):
    permission_classes = [IsAdminUser]

    @extend_schema(summary='Szybkie ukrycie przypięcia z powodem (bez zgłoszenia) albo przywrócenie', tags=[TEAM], request=DecisionIn, responses=OpenApiTypes.OBJECT)
    def post(self, request, pin_id):
        pin = get_object_or_404(Pin, pk=pin_id)
        data = DecisionIn(data=request.data)
        data.is_valid(raise_exception=True)
        if data.validated_data['decision'] == 'restore':
            moderation.restore_pin(pin, request.user, data.validated_data['reason'])
        else:
            moderation.hide_pin(pin, request.user, data.validated_data['reason'], sanction=data.validated_data.get('sanction', ''))
        return Response({'id': pin.pk, 'status': pin.status})


class CommentHideView(Spina3View):
    permission_classes = [IsAdminUser]

    @extend_schema(summary='Ukryj komentarz z uzasadnieniem (DSA art. 17) albo przywróć / zatwierdź wstrzymany (restore)', tags=[TEAM], request=DecisionIn, responses=OpenApiTypes.OBJECT)
    def post(self, request, comment_id):
        comment = get_object_or_404(Comment, pk=comment_id)
        data = DecisionIn(data=request.data)
        data.is_valid(raise_exception=True)
        if data.validated_data['decision'] == 'restore':
            comments.restore_comment(comment, request.user, data.validated_data['reason'])
        else:
            comments.hide_comment(comment, request.user, data.validated_data['reason'], sanction=data.validated_data.get('sanction', ''))
        return Response({'id': comment.pk, 'status': comment.status})


class MetricsView(Spina3View):
    permission_classes = [IsAdminUser]

    @extend_schema(summary='Metryki jakości z agregatów (bez śledzenia) i alarmy', tags=[TEAM], responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(metrics.compute(days=int(request.query_params.get('days') or 7)))


# --- wspólne logowanie ------------------------------------------------------------------------------------

class AuthExchangeView(Spina3View):
    permission_classes = [AllowAny]
    throttle_classes = [AuthExchangeThrottle]
    authentication_classes = []

    @extend_schema(summary='Wymiana jednorazowego kodu z usługi kont na krótki token sesji (auth_mode=token)', tags=[TAG + ' auth'], request=CodeIn, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        if flags().auth_mode != 'token':
            return Response({'detail': 'Wspólne logowanie przez tokeny jest wyłączone (auth_mode=session).'}, status=404)
        data = CodeIn(data=request.data)
        data.is_valid(raise_exception=True)
        user = sso.redeem_code(data.validated_data['code'])
        if user is None:
            return Response({'detail': 'Kod nieważny albo przeterminowany.'}, status=401)
        return Response({'token': sso.issue_token(user), 'expires_in': settings.SPINA3_SSO_TOKEN_MAX_AGE,
                         'user': {'id': user.pk, 'nick': user.username}})


class AuthRefreshView(Spina3View):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Odświeżenie tokenu sesji', tags=[TAG + ' auth'], responses=OpenApiTypes.OBJECT)
    def post(self, request):
        if flags().auth_mode != 'token':
            return Response({'detail': 'auth_mode=session'}, status=404)
        return Response({'token': sso.issue_token(request.user)})


class AuthLogoutEverywhereView(Spina3View):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Wyloguj wszędzie (rotacja pseudonimu unieważnia wszystkie tokeny)', tags=[TAG + ' auth'], responses=OpenApiTypes.OBJECT)
    def post(self, request):
        sso.logout_everywhere(request.user)
        return Response({'ok': True})
