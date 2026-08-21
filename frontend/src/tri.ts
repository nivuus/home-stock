/** Le bac où part un emballage, en français.
 *
 *  Pur, comme `dlc.ts` : le serveur rend des CLÉS (`yellow`, `glass`,
 *  `household`, `dropoff`) et des matériaux bruts, la mise en phrase est
 *  l'affaire du panneau.
 *
 *  Rien de connu → rien d'affiché. Une consigne inventée envoie du verre dans
 *  le bac jaune avec l'assurance de l'écran.
 */
export type Bac = 'yellow' | 'glass' | 'household' | 'dropoff';

const LIBELLE_BAC: Record<Bac, string> = {
  yellow: 'Bac jaune',
  glass: 'Bac à verre',
  household: 'Ordures ménagères',
  dropoff: 'Déchèterie',
};

export function consigneDeTri(bacs: Bac[]): string | null {
  const connus: string[] = [];
  for (const bac of bacs) {
    const libelle = LIBELLE_BAC[bac];
    if (libelle !== undefined && !connus.includes(libelle)) connus.push(libelle);
  }
  if (connus.length === 0) return null;
  // Deux composants peuvent viser deux bacs (le pot et son étui) : ce qu'on
  // doit faire, c'est ouvrir un ou deux couvercles, pas lire un inventaire.
  return connus.map((libelle, index) => (index === 0 ? libelle : libelle.toLowerCase()))
    .join(' et ');
}
