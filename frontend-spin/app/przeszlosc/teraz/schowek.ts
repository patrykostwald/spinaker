/** Kopiowanie tekstu do schowka (z zapasową drogą dla starszych przeglądarek); false, gdy się nie udało. */
export async function kopiujDoSchowka(tekst: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(tekst);
    return true;
  } catch {
    try {
      const pole = document.createElement('textarea');
      pole.value = tekst; pole.setAttribute('readonly', ''); pole.style.position = 'fixed'; pole.style.opacity = '0';
      document.body.appendChild(pole); pole.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(pole);
      return ok;
    } catch { return false; }
  }
}
