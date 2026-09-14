"""One fail-closed access decision for every automated source channel."""

from urllib.parse import urlsplit

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


def approved_instruction(source, channel, request_url=None):
    """Return the current instruction, or ``None`` without performing I/O.

    The query repeats the critical checks from ``clean()`` because ORM bulk
    operations do not call model validation.  A configured source alone never
    authorizes a request.
    """
    if (not source or not source.is_active or not source.scrape_enabled
            or source.catalog_stage != 'configured'):
        return None
    # The newest version for this channel is authoritative.  Filtering to
    # approved rows first would incorrectly revive version 1 after version 2
    # has been suspended or moved to contact_required.
    instruction = SourceAccessInstruction.objects.filter(
        source=source, channel=channel).order_by('-version').first()
    if instruction is None or instruction.status != SourceAccessInstruction.Status.APPROVED:
        return None
    if (instruction.minimum_interval_seconds < 3 or not instruction.terms_url
            or not instruction.reviewed_at or not instruction.reviewed_by
            or not instruction.evidence):
        return None
    if request_url and not _same_endpoint_or_child(request_url, instruction.endpoint):
        return None
    return instruction


def require_approved_instruction(source, channel, request_url=None):
    instruction = approved_instruction(source, channel, request_url)
    if instruction is None:
        raise AccessDenied('no_approved_instruction')
    return instruction
