from spina3.comment_filter import check_comment, pesel_valid


def test_pesel_checksum():
    assert pesel_valid('44051401359')
    assert not pesel_valid('44051401358')
    assert not pesel_valid('12345678901')


def test_blocks_pesel_holds_phone_and_email():
    assert check_comment('Mój PESEL to 44051401359').status == 'blocked'
    assert check_comment('Zadzwoń 600 700 800').status == 'held'
    assert check_comment('pisz na jan@example.org').status == 'held'
    assert check_comment('ul. Długa 12/3 Poznań').status == 'held'
    assert check_comment('Zwykły komentarz o dokumencie.').status == 'ok'
    assert check_comment('').status == 'empty'
    assert check_comment('x' * 281).status == 'blocked'
