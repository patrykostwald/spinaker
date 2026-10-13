import { permanentRedirect } from 'next/navigation';

/** Dawny adres (prototyp przeszlosc-v3: zrodla.html): źródła i metodologia mieszczą się dziś na stronie "Jak to działa". */
export default function DawnyAdres() {
  permanentRedirect('/przeszlosc/jak-to-dziala');
}
