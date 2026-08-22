/** L'écran « planning » : la carte calendrier de Home Assistant.
 *
 *  Le planning des repas est déjà une entité `calendar.*` (voir
 *  `custom_components/home_stock/calendar.py`), avec création, modification et
 *  suppression d'événements. On affiche donc la carte calendrier de Lovelace
 *  sur cette entité plutôt qu'une grille maison : mois / semaine / jour /
 *  liste, le thème et la langue de l'utilisateur, et un clic sur un jour ouvre
 *  la boîte de dialogue de Home Assistant, qui écrit un vrai repas.
 *
 *  LA GRILLE MAISON RESTE, en repli. Elle n'est pas là par nostalgie :
 *  `loadCardHelpers` vient d'un chunk que seul Lovelace charge (voir
 *  `shell/ui/carte-calendrier.ts`), donc une ouverture directe de
 *  `/home-stock` n'a pas la carte. Sans repli, cet écran serait vide.
 *
 *  Sept colonnes × quatre créneaux en 1280 × 800. En 412 × 915, UNE journée à
 *  la fois avec précédent / suivant — pas une grille de sept colonnes réduite,
 *  qui produirait des cibles sous 48 px et que `verifier-rendu.mjs` refuserait
 *  à juste titre.
 *
 *  Les jours sont des journées ALIMENTAIRES : elles courent de 4 h à 4 h.
 */
import { LitElement, html, css, nothing, type PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';
import { tokens } from '../shell/ui/tokens';
import '../shell/ui/hs-icon';
import { creerCarteCalendrier, entiteCalendrierRepas,
         type HassCalendrier } from '../shell/ui/carte-calendrier';

export type CleCreneau = 'breakfast' | 'lunch' | 'dinner' | 'snack';

/** Les créneaux dans l'ordre du planning, avec leur nom français. Repris de
 *  `meal_slot.position` : la même liste que celle que `m004` sème. */
export const CRENEAUX: ReadonlyArray<readonly [CleCreneau, string]> = [
  ['breakfast', 'Petit-déjeuner'],
  ['lunch', 'Déjeuner'],
  ['dinner', 'Dîner'],
  ['snack', 'En-cas'],
];

const JOURS = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi',
               'samedi'];

export type RepasPlanning = {
  id: number;
  uid: string;
  day: string;
  slot_key: CleCreneau;
  position: number;
  recipe_id: number | null;
  recipe_name: string | null;
  product_id: number | null;
  product_name: string | null;
  note: string | null;
  servings: number;
  state: 'planned' | 'done' | 'skipped';
};

export type ProduitManquant = { product_id: number; product_name: string };

function ajouterJours(jour: string, delta: number): string {
  const date = new Date(`${jour}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + delta);
  return date.toISOString().slice(0, 10);
}

function libelleJour(jour: string): string {
  const date = new Date(`${jour}T12:00:00Z`);
  return `${JOURS[date.getUTCDay()]} ${date.getUTCDate()}`;
}

@customElement('home-stock-planning')
export class EcranPlanning extends LitElement {
  @property({ attribute: false }) connexion?: Connexion;
  @property({ attribute: false }) file?: FileAttente;
  @property({ type: Boolean }) large = false;
  /** L'objet `hass` du panneau : la carte calendrier en a besoin, et elle
   *  seule. Absent en test unitaire et à l'ouverture directe — l'écran
   *  retombe alors sur sa grille. */
  @property({ attribute: false }) hass?: HassCalendrier;
  /** Le premier jour affiché. En étroit, le seul. */
  @property({ type: String }) debut = new Date().toISOString().slice(0, 10);

  @state() repas: RepasPlanning[] = [];
  @state() manquants: ProduitManquant[] = [];
  @state() armeAnnulation: number | null = null;
  @state() message: string | null = null;
  /** La carte Lovelace, une fois construite — `null` tant qu'on n'a pas
   *  essayé, ou quand Home Assistant n'a pas de quoi la faire. */
  @state() private carte: HTMLElement | null = null;
  /** Une seule tentative : `hass` est remplacé par Home Assistant à chaque
   *  état de la maison, et rebâtir la carte à chaque fois la ferait clignoter
   *  et perdrait la vue choisie par l'utilisateur. */
  private carteDemandee = false;

  connectedCallback(): void {
    super.connectedCallback();
    void this.charger();
  }

  protected willUpdate(changees: PropertyValues): void {
    if (!changees.has('hass')) return;
    // La carte est un élément Lovelace ordinaire : c'est à son parent de lui
    // repasser `hass`, à chaque fois, comme le ferait un tableau de bord.
    if (this.carte) (this.carte as { hass?: unknown }).hass = this.hass;
    void this.demanderCarte();
  }

  private async demanderCarte(): Promise<void> {
    if (this.carteDemandee || !this.hass) return;
    const entite = entiteCalendrierRepas(this.hass);
    if (!entite) return;
    this.carteDemandee = true;
    const carte = await creerCarteCalendrier(entite);
    if (!carte) return;
    (carte as { hass?: unknown }).hass = this.hass;
    this.carte = carte;
  }

  get jours(): string[] {
    const nombre = this.large ? 7 : 1;
    return Array.from({ length: nombre }, (_, i) => ajouterJours(this.debut, i));
  }

  async charger(): Promise<void> {
    if (!this.connexion) return;
    const jours = this.jours;
    const reponse = await this.connexion.appeler<{ meals: RepasPlanning[] }>(
      'home_stock/meals/list',
      { start: jours[0], end: jours[jours.length - 1] });
    this.repas = reponse.meals ?? [];
  }

  async allerA(delta: number): Promise<void> {
    this.debut = ajouterJours(this.debut, this.large ? delta * 7 : delta);
    this.armeAnnulation = null;
    await this.charger();
  }

  repasDe(jour: string, creneau: CleCreneau): RepasPlanning[] {
    return this.repas
      .filter((r) => r.day === jour && r.slot_key === creneau)
      .sort((a, b) => a.position - b.position);
  }

  // --- écritures, toutes par la file ---------------------------------------

  async poser(jour: string, creneau: CleCreneau): Promise<void> {
    if (!this.file) return;
    this.file.ajouter('home_stock/meal/plan', {
      day: jour, slot_key: creneau, note: 'Repas', servings: 1,
    });
    void this.file.rejouer?.();
    await this.charger();
  }

  async deplacer(repas: RepasPlanning, jour: string,
                 creneau: CleCreneau): Promise<void> {
    if (!this.file) return;
    if (repas.state === 'done') {
      // Ses mouvements portent une date figée : déplacer la ligne les
      // décorrélerait en silence.
      this.message = 'Un repas validé ne se déplace pas : ses mouvements '
        + 'portent une date figée.';
      return;
    }
    this.message = null;
    this.file.ajouter('home_stock/meal/move', {
      meal_id: repas.id, day: jour, slot_key: creneau,
    });
    void this.file.rejouer?.();
    await this.charger();
  }

  /** Deux appuis, comme toute action destructive du panneau. */
  async annuler(repas: RepasPlanning): Promise<void> {
    if (this.armeAnnulation !== repas.id) {
      this.armeAnnulation = repas.id;
      return;
    }
    if (!this.file) return;
    this.armeAnnulation = null;
    this.file.ajouter('home_stock/meal/cancel', { meal_id: repas.id });
    void this.file.rejouer?.();
    await this.charger();
  }

  ouvrirRecette(repas: RepasPlanning): void {
    if (repas.recipe_id === null) return;
    this.dispatchEvent(new CustomEvent('recette-ouverte', {
      detail: { recipe_id: repas.recipe_id, meal_id: repas.id },
      bubbles: true, composed: true,
    }));
  }

  ouvrirValidation(repas: RepasPlanning): void {
    if (repas.state === 'done') return;
    this.dispatchEvent(new CustomEvent('valider-repas', {
      detail: { meal_id: repas.id }, bubbles: true, composed: true,
    }));
  }

  // --- rendu ---------------------------------------------------------------

  private nomDe(repas: RepasPlanning): string {
    return repas.recipe_name ?? repas.product_name ?? repas.note ?? 'Repas';
  }

  private rendreRepas(repas: RepasPlanning) {
    const nom = this.nomDe(repas);
    // Deux boutons texte par repas, répétés sur 28 (ou 56) cases, noyaient la
    // grille sous cinquante-six libellés « Valider »/« Annuler » identiques.
    // En icônes ils redeviennent lisibles, mais chacun doit encore dire QUEL
    // repas il touche pour un lecteur d'écran — d'où l'aria-label nommant.
    const confirmation = this.armeAnnulation === repas.id;
    return html`
      <div class="repas etat-${repas.state}">
        <button class="repas-nom" @click=${() => this.ouvrirRecette(repas)}>
          ${nom}
        </button>
        ${repas.state === 'done'
          ? html`<span class="valide">validé</span>`
          : html`
            <button class="valider-repas" aria-label="Valider ${nom}"
                    @click=${() => this.ouvrirValidation(repas)}>
              <hs-icon name="check"></hs-icon>
            </button>
            <button class="annuler-repas ${confirmation ? 'arme' : ''}"
                    aria-label="${confirmation ? `Confirmer le retrait de ${nom}` : `Retirer ${nom} du planning`}"
                    @click=${() => this.annuler(repas)}>
              <hs-icon name=${confirmation ? 'alert' : 'close'}></hs-icon>
            </button>`}
      </div>
    `;
  }

  private rendreCase(jour: string, creneau: CleCreneau) {
    const repas = this.repasDe(jour, creneau);
    return html`
      <div class="case">
        ${repas.map((r) => this.rendreRepas(r))}
        <button class="poser" @click=${() => this.poser(jour, creneau)}>+</button>
      </div>
    `;
  }

  render() {
    // La carte quand Home Assistant sait la faire, la grille sinon. Jamais les
    // deux : ce seraient deux plannings sur le même écran, chacun avec sa
    // notion de « la semaine affichée ».
    return this.carte ? this.rendreCarte() : this.rendreGrille();
  }

  private rendreCarte() {
    return html`<div class="calendrier">${this.carte}</div>`;
  }

  private rendreGrille() {
    const jours = this.jours;
    return html`
      <div class="entete">
        <button class="precedent-jour" @click=${() => this.allerA(-1)}>Précédent</button>
        <span class="periode">${this.large
          ? `${libelleJour(jours[0])} — ${libelleJour(jours[jours.length - 1])}`
          : libelleJour(jours[0])}</span>
        <button class="suivant-jour" @click=${() => this.allerA(1)}>Suivant</button>
      </div>

      ${this.message ? html`<p class="message">${this.message}</p>` : nothing}
      ${this.manquants.length
        ? html`<p class="manquants">${this.manquants.length} produit${
            this.manquants.length > 1 ? 's' : ''} à acheter</p>`
        : nothing}

      <div class="grille ${this.large ? 'large' : 'etroit'}">
        ${this.large
          ? html`<div class="ligne-jours">
              <span class="coin"></span>
              ${jours.map((j) => html`<span class="jour">${libelleJour(j)}</span>`)}
            </div>`
          : nothing}
        ${CRENEAUX.map(([cle, nom]) => html`
          <div class="ligne-creneau">
            <span class="creneau">${nom}</span>
            ${jours.map((j) => this.rendreCase(j, cle))}
          </div>`)}
      </div>
    `;
  }

  static styles = [tokens, css`
    :host { display: block; padding: 12px; color: var(--hs-text); }
    /* ha-full-calendar se dimensionne sur son parent (height: "parent") :
       sans hauteur ici, il se replierait à zéro. 78 vh laisse la barre de
       navigation et l'en-tête visibles sur les trois tailles ; pas de dvh,
       Chrome 100 (la tablette de la cuisine) ne le connaît pas. Pas de
       backtick dans ce commentaire : il est DANS un littéral de gabarit. */
    .calendrier { height: 78vh; min-height: 380px; }
    /* La carte de Lovelace pose height:100% sur SON ha-card interne — un
       pourcentage qui ne résout à rien tant que l'élément carte lui-même n'a
       pas de hauteur. Sans cette ligne, la chaîne casse au premier maillon et
       le calendrier se replie sur sa hauteur de contenu. */
    .calendrier > * { display: block; height: 100%; }
    .entete { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
    .periode { flex: 1; text-align: center; font-weight: 600; }
    .entete button, .poser, .repas-nom {
      min-height: var(--hs-touch); padding: 0 12px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--hs-divider); font-size: 1rem;
      background: var(--hs-surface); color: var(--hs-text);
    }
    .valider-repas, .annuler-repas {
      display: inline-flex; align-items: center; justify-content: center;
      min-height: var(--hs-touch); min-width: var(--hs-touch);
      padding: 0; border-radius: var(--hs-radius-s);
      border: 1px solid var(--hs-divider);
      background: var(--hs-surface); color: var(--hs-text);
      cursor: pointer;
    }
    /* Deuxième appui d'une action destructive : le danger se dit par la
       bordure (jamais un aplat sous du texte/icône) — le tracé change aussi
       (close → alert) pour un repère qui ne dépend pas de la couleur seule. */
    .annuler-repas.arme { border-color: var(--hs-danger); }
    .grille { display: flex; flex-direction: column; gap: 8px; }
    .ligne-jours, .ligne-creneau { display: flex; gap: 8px; align-items: stretch; }
    .creneau, .coin { flex: 0 0 7em; display: flex; align-items: center;
                      font-weight: 600; }
    .jour { flex: 1; text-align: center; font-weight: 600; }
    .case {
      /* Zone de dépôt, pas une cible tactile : 48px reste volontairement en dur. */
      flex: 1; display: flex; flex-direction: column; gap: 6px; padding: 6px;
      border: 1px dashed var(--hs-divider); border-radius: 8px;
      min-height: 48px;
    }
    .repas { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
    .repas-nom { flex: 1; text-align: left; }
    .etat-done .repas-nom { text-decoration: line-through; opacity: 0.7; }
    .valide { opacity: 0.75; font-size: 0.85rem; }
    .poser { align-self: stretch; }
    .message, .manquants { margin: 4px 0; }
    .etroit .creneau { flex: 0 0 6em; }
    @media (max-width: 700px) {
      .creneau, .coin { flex: 0 0 5.5em; }
      /* Les deux icônes de 62 px tiennent à côté du nom sur un seul jour
         affiché (comportement existant) : plus besoin de les empiler en
         pleine largeur, une mise en page pensée pour les anciens libellés
         texte « Valider »/« Annuler ». */
    }
  `];
}
