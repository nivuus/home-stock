/** Le décompte d'un minuteur de recette. Pur, comme `dlc.ts` et `portion.ts`.
 *
 *  Aucune entité `timer` de Home Assistant n'est créée : une recette de quatre
 *  étapes en produirait quatre, et elles lui survivraient — il faudrait alors
 *  les ranger, ce que personne ne fera.
 *
 *  Le module ne touche ni `setInterval` ni `Date.now()`. Il REÇOIT le temps,
 *  ce qui rend le décompte testable sans horloge factice globale et sans
 *  attendre une seconde réelle par assertion. Le panneau, lui, appelle
 *  `avancer` depuis son propre intervalle.
 */

export type EtatMinuteur = {
  /** Secondes restantes. Jamais négatif. */
  restant: number;
  enMarche: boolean;
  termine: boolean;
  /** La durée d'origine, pour pouvoir repartir de zéro. */
  duree: number;
};

export function demarrer(secondes: number, _maintenant = 0): EtatMinuteur {
  const duree = Math.max(0, secondes);
  return { restant: duree, enMarche: duree > 0, termine: duree === 0, duree };
}

/** Avance le décompte de `ecoule` secondes.
 *
 *  Le restant est borné à zéro : un minuteur oublié pendant dix minutes
 *  affiche « 0:00 », pas « -10:00 ». Et une fois terminé il reste terminé —
 *  repartir demande un `remettreAZero` explicite. */
export function avancer(etat: EtatMinuteur, ecoule: number): EtatMinuteur {
  if (!etat.enMarche) return etat;
  const restant = Math.max(0, etat.restant - Math.max(0, ecoule));
  return { ...etat, restant, enMarche: restant > 0, termine: restant === 0 };
}

export function mettreEnPause(etat: EtatMinuteur): EtatMinuteur {
  return { ...etat, enMarche: false };
}

export function reprendre(etat: EtatMinuteur): EtatMinuteur {
  return etat.termine ? etat : { ...etat, enMarche: etat.restant > 0 };
}

export function remettreAZero(secondes: number): EtatMinuteur {
  const duree = Math.max(0, secondes);
  return { restant: duree, enMarche: false, termine: false, duree };
}

/** « 12:30 », « 1:05:00 », « 0:00 ». L'heure n'apparaît que si elle existe :
 *  « 0:12:30 » pour douze minutes ferait lire une heure là où il n'y en a
 *  pas. */
export function formaterDuree(secondes: number): string {
  const total = Math.max(0, Math.round(secondes));
  const heures = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const restes = total % 60;
  const deuxChiffres = (n: number) => String(n).padStart(2, '0');
  if (heures > 0) return `${heures}:${deuxChiffres(minutes)}:${deuxChiffres(restes)}`;
  return `${minutes}:${deuxChiffres(restes)}`;
}
