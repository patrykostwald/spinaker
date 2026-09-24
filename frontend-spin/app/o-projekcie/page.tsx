import { permanentRedirect } from 'next/navigation';

/** Dawny adres opisu projektu. Treść przeniesiona na /o-nas. */
export default function AboutProjectRedirect() {
  permanentRedirect('/o-nas');
}
