"""Wspólna pisownia nazwisk i nazw kont."""


def display_name(name: str) -> str:
    def word(value):
        if '-' in value:
            return '-'.join(part.capitalize() if part.isupper() and len(part) > 4 else part for part in value.split('-'))
        return value.capitalize() if value.isupper() and len(value) > 4 else value
    return ' '.join(word(part) for part in (name or '').split())
