"""Plan przycięcia kopii w Backblaze B2: zostaw N najnowszych kopii w każdym katalogu, resztę (wszystkie wersje i znaczniki usunięcia) oznacz do skasowania.

Wejście: JSON z `aws s3api list-object-versions` (plik z argumentu 1), N (argument 2), plik wyjściowy dla `delete-objects` (argument 3).
Zasady: katalog = pierwszy człon klucza (pg/, media/, glosy/); „kopia” = klucz; kolejność wg daty najnowszej wersji; nigdy nie ruszamy
kluczy spoza znanych katalogów. Nic nie wypisuje nazw plików poza datą i rozmiarem (bez sekretów).
"""
import json
import sys
from collections import defaultdict

KNOWN = ('pg/', 'media/', 'glosy/')


def plan(data, keep):
    versions = defaultdict(list)
    for kind in ('Versions', 'DeleteMarkers'):
        for v in data.get(kind) or []:
            versions[v['Key']].append((kind, v))
    by_dir = defaultdict(list)
    for key, items in versions.items():
        prefix = next((p for p in KNOWN if key.startswith(p)), None)
        if prefix is None:
            continue
        newest = max(v['LastModified'] for _, v in items)
        live = max(items, key=lambda it: it[1]['LastModified'])[0] == 'Versions'   # ukryta (skasowana) kopia nie liczy się do „zostających”
        by_dir[prefix].append((newest, key, live))
    delete, report = [], {}
    for prefix, rows in by_dir.items():
        rows.sort(reverse=True)
        ordered = [key for _, key, live in rows if live][:keep]
        stay = set(ordered)
        removed_keys = [key for _, key, _ in rows if key not in stay]
        size = 0
        for key in removed_keys:
            for kind, v in versions[key]:
                delete.append({'Key': key, 'VersionId': v['VersionId']})
                size += int(v.get('Size') or 0)
        report[prefix] = {'zostaje': len(stay), 'do_skasowania_plikow': len(removed_keys), 'wersji_do_skasowania': sum(len(versions[k]) for k in removed_keys), 'bajtow': size}
    return delete, report


if __name__ == '__main__':
    data = json.load(open(sys.argv[1]))
    delete, report = plan(data, int(sys.argv[2]))
    json.dump({'Objects': delete, 'Quiet': True}, open(sys.argv[3], 'w'))
    for prefix, r in sorted(report.items()):
        print(f"{prefix}: zostaje {r['zostaje']}, do skasowania {r['do_skasowania_plikow']} plików ({r['wersji_do_skasowania']} wersji, {r['bajtow'] / 1e9:.2f} GB)")
    print(f'RAZEM wersji do skasowania: {len(delete)}')
