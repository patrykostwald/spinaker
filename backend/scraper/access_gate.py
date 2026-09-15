"""One fail-closed access decision for every automated source channel."""

from urllib.parse import urlsplit

from django.utils import timezone

from news.models import SourceAccessInstruction


class AccessDenied(Exception):
    """The source has no reviewed instruction for this operation."""


def _same_endpoint_or_child(request_url, endpoint):
    """Keep a reviewed endpoint on its own host and path subtree."""
    request = urlsplit(request_url)
    allowed = urlsplit(endpoint)
    if request.scheme != allowed.scheme or request.hostname != allowed.hostname:
        return False
    base = allowed.path.rstrip('/') or '/'
    path = request.path.rstrip('/') or '/'
    return path == base or path.startswith(base.rstrip('/') + '/')


def _matches_allowed_path(request_url, patterns):
    """Match explicit path segments; ``{int}`` accepts one decimal segment."""
    if not patterns:
        return True
    request_parts = [item for item in urlsplit(request_url).path.split('/') if item]
    for pattern in patterns:
        pattern_parts = [item for item in pattern.split('/') if item]
        if len(request_parts) != len(pattern_parts):
            continue
        if all(
            (expected == '{int}' and actual.isdecimal()) or expected == actual
            for actual, expected in zip(request_parts, pattern_parts)
        ):
            return True
    return False


def approved_instruction(source, channel, request_url=None):
    """Return the current instruction, or ``None`` without performing I/O.

    The query repeats the critical checks from ``clean()`` because ORM bulk
    operations do not call model validation.  A configured source alone never
    authorizes a request.
    """
    if (not source or not source.is_active or not source.scrape_enabled
            or source.catalog_stage != 'configured'):
        return None
    # A source may expose separate, independently reviewed API endpoints.
    # The most-specific matching endpoint wins; its newest version is
    # authoritative.  A suspension on that endpoint must not revive an older
    # version nor silently spill into a different documented endpoint.
    candidates = list(SourceAccessInstruction.objects.filter(
        source=source, channel=channel).order_by('-version'))
    if request_url:
        candidates = [item for item in candidates
            if _same_endpoint_or_child(request_url, item.endpoint)
            and _matches_allowed_path(request_url, item.allowed_path_patterns)]
        if candidates:
            specificity = max(len(urlsplit(item.endpoint).path.rstrip('/')) for item in candidates)
            candidates = [item for item in candidates
                if len(urlsplit(item.endpoint).path.rstrip('/')) == specificity]
    instruction = candidates[0] if candidates else None
    if instruction is None or instruction.status != SourceAccessInstruction.Status.APPROVED:
        return None
    if (instruction.minimum_interval_seconds < 3 or instruction.daily_request_cap < 1 or not instruction.terms_url
            or not instruction.reviewed_at or not instruction.reviewed_by
            or not instruction.evidence or not instruction.valid_until
            or instruction.valid_until <= timezone.now()):
        return None
    if request_url and not _same_endpoint_or_child(request_url, instruction.endpoint):
        return None
    return instruction


def require_approved_instruction(source, channel, request_url=None):
    instruction = approved_instruction(source, channel, request_url)
    if instruction is None:
        raise AccessDenied('no_approved_instruction')
    return instruction


