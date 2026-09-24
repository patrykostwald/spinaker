"""One fail-closed access decision for every automated source channel."""

from urllib.parse import urlsplit

from django.utils import timezone

from news.models import SourceAccessInstruction


class AccessDenied(Exception):
    """The source has no reviewed instruction for this operation."""


def has_current_approved_instruction(source):
    """Whether a source has at least one current, reviewed access card.

    This does not authorise a request.  Importers must still call
    ``approved_instruction`` with their exact channel and endpoint.
    """
    if not source:
        return False
    return SourceAccessInstruction.objects.filter(
        source=source,
        status=SourceAccessInstruction.Status.APPROVED,
        minimum_interval_seconds__gte=3,
        daily_request_cap__gte=1,
        valid_until__gt=timezone.now(),
        reviewed_at__isnull=False,
    ).exclude(terms_url='').exclude(reviewed_by='').exclude(evidence={}).exists()


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
    """Match explicit path segments; placeholders never span a slash."""
    if not patterns:
        return True
    request_parts = [item for item in urlsplit(request_url).path.split('/') if item]
    for pattern in patterns:
        pattern_parts = [item for item in pattern.split('/') if item]
        if len(request_parts) != len(pattern_parts):
            continue
        if all(
            (expected == '{int}' and actual.isdecimal())
            or (expected == '{token}' and 1 <= len(actual) <= 200
                and all(char.isascii() and (char.isalnum() or char in '-_') for char in actual))
            or expected == actual
            for actual, expected in zip(request_parts, pattern_parts)
        ):
            return True
    return False


def reviewed_instruction_for_endpoint(source, channel, request_url=None):
    """Return a valid reviewed card without authorising a fetch.

    This is used while configuring a candidate after a technical audit.  It
    deliberately ignores the source operational state, because that state is
    changed *after* the editorial card has been found.  It never performs I/O
    and it does not itself permit an importer to run.
    """
    if not source:
        return None
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
    return instruction


def approved_instruction(source, channel, request_url=None):
    """Return the current operational instruction, or ``None`` without I/O."""
    if (not source or not source.is_active or not source.scrape_enabled
            or source.catalog_stage != 'configured'):
        return None
    return reviewed_instruction_for_endpoint(source, channel, request_url)


def require_approved_instruction(source, channel, request_url=None):
    instruction = approved_instruction(source, channel, request_url)
    if instruction is None:
        raise AccessDenied('no_approved_instruction')
    return instruction


