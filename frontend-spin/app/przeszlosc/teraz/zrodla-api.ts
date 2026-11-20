import { useQuery } from '@tanstack/react-query';
import { co, pobierz, wspolne } from './api';
import { probneZrodla } from './dane-probne/zrodla';
import { daneZrodel, walidujZrodla, type DaneZrodel, type WynikZrodel } from './zrodla';

/**
 * Klient GET /api/teraz/zrodla/ (backend/teraz/api.py: ZrodlaView): rodzaj łącza, ostatni sukces, kod błędu, luka.
 * Odświeżanie co 60 s (stan źródeł zmienia się wolniej niż wpisy). Awaria (sieć, kod HTTP, zły format) to błąd zapytania,
 * który interfejs pokazuje jako „stan źródeł niedostępny” (zrodla.ts: DaneZrodel), nigdy jako pustą listę.
 * W trybie próbnym zwraca dane przykładowe (dane-probne/zrodla.ts), bez zapytania do sieci.
 */
export const ODSWIEZANIE_ZRODEL_MS = 60_000;

export function useZrodla(probne: boolean): DaneZrodel {
  const q = useQuery<WynikZrodel>({
    queryKey: ['teraz', 'zrodla', probne],
    queryFn: ({ signal }) => probne ? Promise.resolve({ zrodla: probneZrodla(), pominiete: 0 }) : pobierz<WynikZrodel>('zrodla', {}, signal, walidujZrodla),
    ...wspolne, ...co(ODSWIEZANIE_ZRODEL_MS),
  });
  return daneZrodel(q);
}
