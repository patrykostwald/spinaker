import json
from types import SimpleNamespace

from news import clinic_interview


def test_long_video_is_transcribed_in_chunks_and_a_too_long_chunk_is_split(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    monkeypatch.setattr(clinic_interview, 'video_seconds', lambda url: 1500)  # 25 minut → 3 kawałki po 10 min
    asked = []

    def fake_post(url, json=None, timeout=None, headers=None):
        parts = json['contents'][0]['parts']
        meta = parts[0]['video_metadata']
        start, end = int(meta['start_offset'][:-1]), int(meta['end_offset'][:-1])
        asked.append((start, end))
        if (start, end) == (600, 1200):  # za długa odpowiedź — Gemini urywa JSON
            payload = {'candidates': [{'content': {'parts': [{'text': '{"segments": [{"time": "10:0'}]}, 'finishReason': 'MAX_TOKENS'}]}
        else:
            # drugi kawałek podaje czas od początku FRAGMENTU (0:05), a nie filmu — musimy go przesunąć
            time = '00:05' if start == 900 else clinic_interview._fmt_time(start + 5)
            body = {'guest_name': 'Leszek Miller' if start == 0 else '', 'host_name': 'Robert Mazurek',
                    'segments': [{'time': time, 'speaker': 'guest', 'text': f'fragment {start}'}]}
            payload = {'candidates': [{'content': {'parts': [{'text': _json(body)}]}}],
                       'usageMetadata': {'promptTokenCount': 10, 'candidatesTokenCount': 5}}
        return SimpleNamespace(status_code=200, json=lambda: payload, text='')

    monkeypatch.setattr(clinic_interview.requests, 'post', fake_post)
    data, usage = clinic_interview.transcribe('https://www.youtube.com/watch?v=2CecmzNERSI')
    assert asked == [(0, 600), (600, 1200), (600, 900), (900, 1200), (1200, 1500)]
    assert [row['text'] for row in data['segments']] == ['fragment 0', 'fragment 600', 'fragment 900', 'fragment 1200']
    assert [row['time'] for row in data['segments']] == ['00:05', '10:05', '15:05', '20:05']
    assert data['guest_name'] == 'Leszek Miller' and data['host_name'] == 'Robert Mazurek'
    assert usage['input_tokens'] == 40 and usage['output_tokens'] == 20


def test_short_video_is_one_request(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-key')
    monkeypatch.setattr(clinic_interview, 'video_seconds', lambda url: 480)
    calls = []

    def fake_post(url, json=None, timeout=None, headers=None):
        calls.append('video_metadata' in json['contents'][0]['parts'][0])
        body = {'guest_name': 'A', 'host_name': 'B', 'segments': [{'time': '00:01', 'speaker': 'host', 'text': 'Dzień dobry'}]}
        return SimpleNamespace(status_code=200, json=lambda: {'candidates': [{'content': {'parts': [{'text': _json(body)}]}}]}, text='')

    monkeypatch.setattr(clinic_interview.requests, 'post', fake_post)
    data, _ = clinic_interview.transcribe('https://www.youtube.com/watch?v=2CecmzNERSI')
    assert calls == [False] and data['segments'][0]['text'] == 'Dzień dobry'


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)
