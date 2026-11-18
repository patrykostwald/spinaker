import type { Okres } from './typy';
import { OKRESY } from './warstwy';

/**
 * Wybór okresu (1 godz., 24 godz., 7 dni): natywne pola radiowe w grupie. Dzięki temu klawiatura działa jak w każdym wyborze
 * jednej z kilku opcji (Tab wchodzi do grupy, strzałki zmieniają opcję), a czytnik ekranu zapowiada „1 z 3”. Cały napis jest
 * celem dotyku (min. 44 px), a zaznaczenie to kolor, ramka i znaczenie dla technologii asystujących (nie sam kolor).
 */
export interface WyborOkresuProps {
  okres: Okres;
  onOkres: (o: Okres) => void;
  /** Unikalna nazwa grupy radiowej (dwa wybory na stronie nie mogą dzielić nazwy). */
  nazwa: string;
  /** Id elementu z napisem grupy („Czas”, „Okres”). */
  opisanePrzez: string;
  klasa: string;
}

export function WyborOkresu({ okres, onOkres, nazwa, opisanePrzez, klasa }: WyborOkresuProps) {
  return <div className={`tz-okresy ${klasa}`} role="radiogroup" aria-labelledby={opisanePrzez}>
    {OKRESY.map(o => <label key={o.id} className="tz-okresy__opcja" data-on={okres === o.id ? '' : undefined}>
      <input type="radio" name={nazwa} value={o.id} checked={okres === o.id} onChange={() => onOkres(o.id)} />
      <span>{o.etykieta}</span>
    </label>)}
  </div>;
}
