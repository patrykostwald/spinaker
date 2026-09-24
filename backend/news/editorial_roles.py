"""Author rights are granted by staff through the journalists group, never signup."""

JOURNALISTS_GROUP = 'journalists'


def is_journalist(user):
    return bool(user.is_authenticated and user.is_active
                and any(group.name == JOURNALISTS_GROUP for group in user.groups.all()))


def can_author_threads(user):
    return bool(user.is_authenticated and user.is_active
                and (user.is_staff or is_journalist(user)))


def role_data(user):
    active = bool(user.is_authenticated and user.is_active)
    staff = bool(active and user.is_staff)
    journalist = is_journalist(user)
    author = staff or journalist
    return {
        'role': 'editor' if staff else 'journalist' if journalist else 'reader' if active else 'guest',
        'is_editor': author,
        'is_journalist': journalist,
        'can_edit_threads': author,
        'can_create_threads': author,
        'can_publish': staff,
        'can_manage_sponsorship': staff,
    }
