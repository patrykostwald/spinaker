"""Maile social mediów do osoby z SOCIAL_VIDEO_EMAIL (tata właściciela) idą mimo STAFF_MAIL_ENABLED=false."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from news import social_publish as sp


def run_manual(tmp_path, monkeypatch, social_email):
    monkeypatch.setenv('STAFF_MAIL_ENABLED', 'false')
    monkeypatch.delenv('X_POST_ALERT_EMAIL', raising=False)
    if social_email:
        monkeypatch.setenv('SOCIAL_VIDEO_EMAIL', social_email)
    else:
        monkeypatch.delenv('SOCIAL_VIDEO_EMAIL', raising=False)
    video = Path(tmp_path) / '1-film.mp4'
    video.write_bytes(b'mp4')
    smtp = MagicMock()
    with patch('news.clinic._smtp_ready', return_value=True), patch('smtplib.SMTP_SSL', return_value=smtp):
        sp.post_manual(video, 'Opis', 'https://spin.clinic/klinika/1')
    return smtp


def test_social_manager_gets_video_mail_while_staff_mail_is_off(tmp_path, monkeypatch):
    smtp = run_manual(tmp_path, monkeypatch, 'tata@example.com')
    message = smtp.__enter__.return_value.send_message.call_args.args[0]
    assert message['To'] == 'tata@example.com' and 'TikTok' in message['Subject']


def test_without_social_manager_nothing_is_sent(tmp_path, monkeypatch):
    smtp = run_manual(tmp_path, monkeypatch, '')
    smtp.__enter__.return_value.send_message.assert_not_called()
