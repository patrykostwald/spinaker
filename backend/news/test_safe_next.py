from news.account_security import safe_next


def test_safe_next_only_internal_paths():
    assert safe_next('/klinika/wywiady/glosowanie?day=2026-10-03') == '/klinika/wywiady/glosowanie?day=2026-10-03'
    for bad in ('https://evil.example', '//evil.example', '/\evil', 'javascript:alert(1)', '', None, '/a\nb', '/' + 'x' * 400):
        assert safe_next(bad) == ''
