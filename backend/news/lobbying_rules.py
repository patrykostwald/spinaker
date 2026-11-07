"""Conservative local-text adapters derived from the amendment pilot."""
import re

AUTH = re.compile(r'^\s*[–-]\s*(KP [^\n]+|KKP [^\n]+|Klub [^\n]+|Koło [^\n]+)$', re.M)
REC = re.compile(r'^\s*[–-]\s*(przyjąć|odrzucić)\s*$', re.M)
ITEM = re.compile(r'^\s*(\d{1,3})\)\s', re.M)


def amendments(text):
    result, previous = [], 0
    for match in REC.finditer(text):
        chunk, previous = text[previous:match.end()], match.end()
        author, number = AUTH.search(chunk), ITEM.search(chunk)
        if not author or not number or 'odrzucić projekt' in chunk[:number.end()].casefold():
            continue
        clubs = [re.sub(r'^(?:KK?P|Klub Parlamentarny|Klub|Koło)\s+', '', a).strip(' ;,.') for a in AUTH.findall(chunk)]
        body = ' '.join(chunk[number.end():author.start()].split())
        if body and clubs:
            result.append({'number': number[1], 'text': body, 'clubs': clubs})
    return result


def declarations(text):
    """Only affirmative, self-contained declarations with a named organisation.

    Mere mentions of the lobbying statute and negative/no-submission declarations do not match.
    Ambiguous lists stay in the source for a future parser, without a signal.
    """
    flat = ' '.join(text.split())
    pattern = re.compile(r'(?P<name>(?:Związek|Konfederacja|Stowarzyszenie|Izba|Fundacja|Polska Rada|'
        r'Polskie Stowarzyszenie)[^.!?;:]{3,180}?)\s+zgłosi(?:ł|ła|ło|ły)\s+'
        r'zainteresowanie pracami nad projektem[^.!?]{0,180}[.!?]', re.I)
    return [{'author': m['name'].strip(), 'text': m[0]} for m in pattern.finditer(flat)
            if not re.search(r'\bnie\b|brak|żaden', m[0], re.I)]
