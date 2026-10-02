"""Only finished social assets and the caller's own inbox are exposed here."""
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Case, When, Value, IntegerField
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.permissions import BasePermission, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from news.clinic_models import SocialPost
from news.social_models import SocialMaterial, SocialTask
from news import social_assistant, social_publish
from news.account_lifecycle import PasswordResetConfirmView, ResetConfirmInput


def is_social_manager(user):
    return bool(user.is_authenticated and user.is_active and
                (user.is_staff or user.groups.filter(name='social').exists()))


class IsSocialManager(BasePermission):
    def has_permission(self, request, view):
        return is_social_manager(request.user)


class SocialThrottle(UserRateThrottle):
    scope = 'social'
    rate = '120/hour'


class SocialWriteThrottle(UserRateThrottle):
    scope = 'social_write'
    rate = '30/hour'


@method_decorator(never_cache, name='dispatch')
class SocialView(APIView):
    permission_classes = [IsSocialManager]
    throttle_classes = [SocialThrottle]

    def get_throttles(self):
        return super().get_throttles() + ([SocialWriteThrottle()] if self.request.method != 'GET' else [])


def unavailable(row):
    d = row.diagnosis
    return not d.post.available or d.withdrawn_at is not None or d.hidden_at is not None or d.status != 'approved'


def material_data(row):
    d = row.diagnosis
    removed = unavailable(row)
    posts = list(d.social_posts.filter(platform__in=['tiktok', 'shorts']).values('platform', 'url', 'posted_at', 'deleted_at'))
    if removed:
        return {'id': d.pk, 'title': f'Materiał #{d.pk}', 'remove_required': True, 'posts': posts}
    caption, link = row.caption, row.link
    if not caption:
        # Legacy mail deliveries: reconstruct from saved synthesis, never call AI in a GET.
        from news.clinic import detail_data
        if not d.x_thread:
            return None
        text = social_publish.texts_from_data(detail_data(d))
        caption, link = text.get('instagram', ''), text.get('link', '')
    if not caption or not (social_publish.video_dir() / social_publish.video_name(d.pk)).is_file():
        return None
    return {'id': d.pk, 'title': d.headline, 'caption': caption, 'link': link,
            'thumbnail': f'/api/clinic/spins/{d.pk}/card.png',
            'video': f'/api/social/video/{social_publish.video_name(d.pk)}',
            'remove_required': False, 'posts': posts}


class SocialQueueView(SocialView):
    def get(self, request):
        rows = SocialMaterial.objects.filter(removed_at__isnull=True).select_related('diagnosis__post__account')
        # Removal notices must survive both skipping and publication to both platforms.
        removal = Q(diagnosis__post__available=False) | Q(diagnosis__withdrawn_at__isnull=False) | Q(diagnosis__hidden_at__isnull=False) | ~Q(diagnosis__status='approved')
        rows = rows.filter(removal | Q(skipped_at__isnull=True)).annotate(
            priority=Case(When(removal, then=Value(0)), default=Value(1), output_field=IntegerField())
        ).order_by('priority', 'created_at', 'pk')
        items = []
        for row in rows:
            if not unavailable(row) and all(row.diagnosis.social_posts.filter(platform=p).exists() for p in ('tiktok', 'shorts')):
                continue
            data = material_data(row)
            if data:
                items.append(data)
            if len(items) >= 100:
                break
        return Response({'items': items, 'is_staff': request.user.is_staff})


class PublicationInput(serializers.Serializer):
    action = serializers.ChoiceField(choices=['tiktok', 'shorts', 'skip', 'removed'])
    url = serializers.URLField(max_length=500, required=False)

    def validate(self, values):
        platform = values['action']
        if platform in ('tiktok', 'shorts'):
            url = urlsplit(values.get('url', ''))
            hosts = ('tiktok.com', 'www.tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com') if platform == 'tiktok' else ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be')
            if url.scheme != 'https' or url.hostname not in hosts or url.username or url.password or not url.path.strip('/'):
                raise serializers.ValidationError('Podaj adres HTTPS posta na wybranej platformie.')
        return values


class SocialPublicationView(SocialView):
    def post(self, request, diagnosis_id):
        data = PublicationInput(data=request.data)
        data.is_valid(raise_exception=True)
        action = data.validated_data['action']
        with transaction.atomic():
            row = get_object_or_404(SocialMaterial.objects.select_for_update(), diagnosis_id=diagnosis_id)
            if action == 'removed':
                if not unavailable(row):
                    return Response({'detail': 'Ten materiał nie oczekuje na usunięcie.'}, status=400)
                row.removed_at = timezone.now()
                row.save(update_fields=['removed_at'])
                row.diagnosis.social_posts.filter(platform__in=['manual', 'tiktok', 'shorts'], deleted_at__isnull=True).update(deleted_at=row.removed_at)
            elif unavailable(row) or row.removed_at:
                return Response({'detail': 'Usuń film. Materiał został wycofany.'}, status=409)
            elif action == 'skip':
                row.skipped_at = timezone.now()
                row.save(update_fields=['skipped_at'])
            else:
                if not material_data(row):
                    return Response({'detail': 'Materiał nie jest gotowy.'}, status=409)
                SocialPost.objects.update_or_create(diagnosis_id=diagnosis_id, platform=action,
                    defaults={'url': data.validated_data['url']})
        return Response({'detail': 'Zapisano.'})


class SocialPublishedView(SocialView):
    def get(self, request):
        rows = SocialPost.objects.filter(platform__in=['tiktok', 'shorts']).order_by('-posted_at', '-pk')[:50]
        return Response({'items': list(rows.values('id', 'diagnosis_id', 'platform', 'url', 'posted_at', 'deleted_at'))})


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialTask
        fields = ['id', 'content', 'kind', 'status', 'answer', 'answered_by', 'created_at', 'updated_at', 'answered_at']
        read_only_fields = ['id', 'status', 'answer', 'answered_by', 'created_at', 'updated_at', 'answered_at']


class SocialTasksView(SocialView):
    def get(self, request):
        rows = SocialTask.objects.filter(author=request.user)
        return Response({'items': TaskSerializer(rows[:100], many=True).data})

    def post(self, request):
        data = TaskSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        task = data.save(author=request.user)
        if task.kind == 'question':
            task.answer = social_assistant.answer_question(task.content)
            task.answered_by = 'assistant'
            task.answered_at = timezone.now()
            task.status = 'new' if task.answer == 'Odpowiem później' else 'done'
            task.save()
        return Response(TaskSerializer(task).data, status=201)


class TaskReplyInput(serializers.Serializer):
    status = serializers.ChoiceField(choices=['new', 'progress', 'done'], required=False)
    answer = serializers.CharField(max_length=8000, required=False)
    answered_by = serializers.ChoiceField(choices=['owner', 'claude'], required=False)

    def validate(self, values):
        if not values or ('answered_by' in values and 'answer' not in values):
            raise serializers.ValidationError('Podaj odpowiedź lub status.')
        return values


class StaffSocialTasksView(SocialView):
    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'head', 'options']

    def get(self, request):
        rows = SocialTask.objects.select_related('author').annotate(
            priority=Case(When(status='new', then=Value(0)), When(status='progress', then=Value(1)),
                          default=Value(2), output_field=IntegerField())
        ).order_by('priority', '-created_at', '-pk')[:100]
        return Response({'items': [{**TaskSerializer(row).data, 'author': row.author.get_full_name() or row.author.username} for row in rows],
                         'new_count': SocialTask.objects.filter(status='new').count()})

    def patch(self, request, task_id):
        data = TaskReplyInput(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            task = get_object_or_404(SocialTask.objects.select_for_update(), pk=task_id)
            values = data.validated_data
            if 'status' in values:
                task.status = values['status']
            if 'answer' in values:
                task.answer = values['answer']
                task.answered_by = values.get('answered_by', 'owner')
                task.answered_at = timezone.now()
            task.save()
        return Response(TaskSerializer(task).data)


class StaffSocialTaskDetailView(StaffSocialTasksView):
    http_method_names = ['patch', 'options']


def panel_section():
    from news.admin_status import card, metric
    count = SocialTask.objects.filter(status='new').count()
    return {**card('Zadania od social media', 'warn' if count else 'ok',
                   'Pytania i zadania czekające na odpowiedź.', metrics=[metric('Nowe', count)]),
            'href': '/panel#social-tasks', 'link_label': 'Otwórz skrzynkę'}


# Reuse phase-2 password validation and one-use Django tokens even when reader accounts are disabled.
class SocialPasswordResetConfirmView(PasswordResetConfirmView):
    permission_classes = [AllowAny]

    def post(self, request):
        data = ResetConfirmInput(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            uid = urlsafe_base64_decode(data.validated_data['uid']).decode()
            get_user_model().objects.get(pk=uid, is_active=True, groups__name='social')
        except (ValueError, TypeError, OverflowError, UnicodeDecodeError, get_user_model().DoesNotExist):
            return Response({'detail': 'Link jest nieprawidłowy lub wygasł.'}, status=400)
        return super().post(request)
