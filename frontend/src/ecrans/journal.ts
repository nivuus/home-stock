/** L'écran « journal » : ce qui est sorti du stock, jour par jour.
 *
 *  Deux vues : le détail d'UNE journée (`home_stock/journal/day`) et un
 *  histogramme de plusieurs seaux (`home_stock/journal/series`) — jour,
 *  semaine ou mois — qui sert à choisir la journée à ouvrir. Toucher une
 *  barre recharge le détail sur le jour qu'elle représente ; pour une
 *  semaine ou un mois, son `label` est déjà le premier jour du seau, que
 *  `journal/day` accepte tel quel — aucune conversion ici.
 *
 *  Depuis le lot 4, il écrit une seule chose : une CORRECTION. Le journal ne
 *  cache jamais une erreur — la ligne fautive reste visible, barrée, avec sa
 *  contrepassation juste en dessous. C'est ce qui permet de comprendre, six
 *  mois plus tard, pourquoi une journée porte une valeur négative.
 *
 *  Corriger demande DEUX appuis, et le détail dit AVANT, en clair, ce que la
 *  correction va faire : « Annule 200 g de Pâtes — 310 kcal, 0,42 € — et
 *  remet 200 g dans le lot du 2026-08-14 ». Une opération irréversible qui ne
 *  s'annonce pas est une opération qu'on déclenche par erreur.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';
import { formaterNombre } from '../nombres';

export type Granularite = 'day' | 'week' | 'month';

/** Une ligne du journal, telle que `home_stock/journal/day` la rend — une
 *  sortie de stock (mangée, jetée ou périmée), jamais une entrée. */
export type EntreeJournal = {
  id: number;
  occurred_at: string;
  product_name: string;
  quantity: number;
  base_unit: string;
  reason: string;
  // Le serveur gèle NULL quand aucun taux de kcal n'était connu au moment
  // du mouvement (spec : ce gel est l'invariant, pas un cas rare) — un type
  // non nullable ici laisserait `Math.round(null)` afficher silencieusement
  // « 0 kcal » là où la vraie réponse est « inconnu ».
  kcal: number | null;
  parts_total: number | null;
  parts_mine: number | null;
  batch_id?: number | null;
  /** Le mouvement que CETTE ligne annule, s'il y en a un. */
  corrects_id?: number | null;
  /** La contrepassation qui annule cette ligne, s'il y en a une. */
  corrected_by?: number | null;
};

/** Ce que `home_stock/movement/correction_preview` répond : ce que la
 *  correction fera, avant qu'on appuie. */
export type ApercuCorrection = {
  movement_id: number;
  product_name: string | null;
  base_unit: string | null;
  quantity: number;
  kcal: number | null;
  cost: number | null;
  reason: string;
  occurred_at: string;
  batch_id: number | null;
  batch_entered_at: string | null;
  meal_id?: number | null;
  correctable: boolean;
  refusal: string | null;
};

export type TotauxJournal = {
  kcal: number;
  cost: number;
  waste_cost: number;
  unvalued: number;
  proteins?: number;
  salt?: number;
};

export type JourJournal = {
  food_day: string;
  start: string;
  end: string;
  entries: EntreeJournal[];
  totals: TotauxJournal;
  /** Les plafonds réglés dans les options de l'entrée. Absents tant que
   *  personne n'en a posé : l'écran est alors celui du lot 2, à l'identique. */
  goals?: Record<string, number>;
  /** La moyenne des sept journées CLOSES, telle que le résumé la publie. */
  week_mean?: Partial<TotauxJournal>;
};

/** Les neuf nutriments qu'un objectif peut viser, en français et avec leur
 *  unité. Le serveur rend les clés, le panneau les phrases — même partage
 *  que `tri.ts` pour les bacs. */
const LIBELLE_NUTRIMENT: Record<string, { nom: string; unite: string }> = {
  kcal: { nom: 'Énergie', unite: 'kcal' },
  proteins: { nom: 'Protéines', unite: 'g' },
  carbohydrates: { nom: 'Glucides', unite: 'g' },
  sugars: { nom: 'Sucres', unite: 'g' },
  added_sugars: { nom: 'Sucres ajoutés', unite: 'g' },
  fat: { nom: 'Matières grasses', unite: 'g' },
  saturated_fat: { nom: 'Graisses saturées', unite: 'g' },
  fiber: { nom: 'Fibres', unite: 'g' },
  salt: { nom: 'Sel', unite: 'g' },
};

export type SeauJournal = { label: string; kcal: number; cost: number; waste_cost: number };
export type SerieJournal = { granularity: Granularite; buckets: SeauJournal[] };

/** Le nombre de seaux demandés à `journal/series`, par granularité — deux
 *  semaines de jours, un an de semaines ou de mois. */
const NOMBRE_DE_SEAUX: Record<Granularite, number> = { day: 14, week: 12, month: 12 };

const LIBELLE_GRANULARITE: Record<Granularite, string> = { day: 'Jours', week: 'Semaines', month: 'Mois' };

function formaterEuros(valeur: number): string {
  return `${valeur.toFixed(2).replace('.', ',')} €`;
}

@customElement('home-stock-journal')
export class EcranJournal extends LitElement {
  @property({ attribute: false }) connexion?: Connexion;

  @state() jour: JourJournal | null = null;
  @state() serie: SerieJournal | null = null;
  @state() granularite: Granularite = 'day';
  @state() enCours = false;
  /** Le seau touché en vue « semaine » ou « mois ». Il n'existe aucune
   *  commande serveur qui rende le détail d'un seau — seul `journal/day`
   *  rend un détail, et seulement pour UN jour. Toucher une barre « mois »
   *  ne doit donc jamais recharger `jour` sur son premier jour (qui ne
   *  représenterait qu'une fraction du seau) : les totaux affichés sont
   *  ceux du seau lui-même, déjà dans la réponse de `journal/series`. */
  @state() seauSelectionne: SeauJournal | null = null;

  /** La file hors-ligne. Corriger est une écriture comme une autre : elle se
   *  fait souvent depuis la cuisine, et le réseau n'y est pas meilleur qu'en
   *  rayon. */
  @property({ attribute: false }) file?: FileAttente;
  /** L'identifiant de la ligne dont le détail est ouvert, et ce que le
   *  serveur dit qu'une correction lui ferait. */
  @state() private detailOuvert: number | null = null;
  @state() private apercu: ApercuCorrection | null = null;
  /** La correction armée par le premier appui : le second confirme. */
  /** Ce que le premier appui a armé : une ligne, ou un repas entier. Le
   *  TYPE de commande n'est pas stocké ici — il est écrit en toutes lettres
   *  au moment de l'envoi. Le contrat de la file hors ligne se vérifie en
   *  scannant ce fichier : une commande passée par une variable y serait
   *  invisible, et son schéma pourrait refuser la clé d'idempotence sans
   *  que rien ne le signale. */
  @state() private correctionArmee: { cible: 'mouvement' | 'repas'; id: number } | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    void this.chargerJour();
    void this.chargerSerie(this.granularite);
  }

  private async chargerJour(date?: string): Promise<void> {
    if (!this.connexion) return;
    this.jour = await this.connexion.appeler<JourJournal>('home_stock/journal/day',
                                                          date ? { date } : {});
  }

  private async chargerSerie(granularite: Granularite): Promise<void> {
    if (!this.connexion) return;
    this.enCours = true;
    try {
      this.serie = await this.connexion.appeler<SerieJournal>('home_stock/journal/series',
        { granularity: granularite, count: NOMBRE_DE_SEAUX[granularite] });
    } finally {
      this.enCours = false;
    }
  }

  /** Change de vue (jour, semaine, mois) : recharge la série avec le compte
   *  qui va avec, jamais celui de la vue précédente. */
  async choisirGranularite(granularite: Granularite): Promise<void> {
    this.granularite = granularite;
    this.seauSelectionne = null;
    await this.chargerSerie(granularite);
  }

  /** Touché un seau. En vue « jour », le seau EST le jour : son `label` est
   *  la date, `journal/day` la rend telle quelle. En vue « semaine » ou
   *  « mois », le seau couvre plusieurs jours — `journal/day` ne rendrait
   *  que le premier d'entre eux, un jour qui ne pèse qu'une fraction du
   *  seau affiché. Faute d'une commande serveur qui rende le détail d'un
   *  seau, on affiche donc les totaux du seau lui-même plutôt que de
   *  mentir avec le détail d'un seul jour. */
  async ouvrirSeau(seau: SeauJournal): Promise<void> {
    if (this.granularite === 'day') {
      this.seauSelectionne = null;
      await this.chargerJour(seau.label);
    } else {
      this.jour = null;
      this.seauSelectionne = seau;
    }
  }

  /** La hauteur relative d'une barre.
   *
   *  La garde sur `maximum > 0` n'est pas décorative : une semaine sans rien
   *  de déclaré donnerait `0 / 0`, donc `NaN`, donc une hauteur CSS invalide
   *  — et des barres invisibles sans la moindre erreur nulle part.
   */
  private partDeLaBarre(kcal: number, maximum: number): number {
    return maximum > 0 ? kcal / maximum : 0;
  }

  /** Le seau lui-même n'est jamais la cible tactile : à quatorze seaux sur
   *  un téléphone de 412 px, un bouton qui vaudrait la barre entière ferait
   *  moins de 24 px de large — sous les 48 px de cible tactile, quelle que
   *  soit sa hauteur. Le bouton reste donc toujours la colonne (ou la ligne,
   *  cf. le style plus bas) EN ENTIER, à taille fixe ; seul le remplissage
   *  intérieur — décoratif, jamais cliqué pour lui-même — varie avec `part`,
   *  via la variable CSS `--part` que le style choisit d'appliquer en
   *  hauteur (histogramme large) ou en largeur (liste étroite). */
  private rendreBarres() {
    const seaux = this.serie?.buckets ?? [];
    const maximum = Math.max(0, ...seaux.map((b) => b.kcal));
    return html`
      <div class="barres">
        ${seaux.map((seau) => {
          const part = this.partDeLaBarre(seau.kcal, maximum);
          return html`
            <button class="barre" data-part=${part}
                    style=${`--part: ${Math.round(part * 100)}%`}
                    title=${`${seau.label} — ${Math.round(seau.kcal)} kcal`}
                    @click=${() => this.ouvrirSeau(seau)}>
              <span class="barre-remplissage"></span>
            </button>`;
        })}
      </div>`;
  }

  private rendreGranularites() {
    return html`
      <nav class="granularites">
        ${(Object.keys(LIBELLE_GRANULARITE) as Granularite[]).map((g) => html`
          <button type="button" class="granularite ${this.granularite === g ? 'granularite-active' : ''}"
            @click=${() => this.choisirGranularite(g)}>
            ${LIBELLE_GRANULARITE[g]}
          </button>
        `)}
      </nav>
    `;
  }

  private rendreEntree(entree: EntreeJournal) {
    const partagee = entree.parts_total !== null && entree.parts_total !== entree.parts_mine;
    const corrigee = (entree.corrected_by ?? null) !== null;
    const contrepassation = (entree.corrects_id ?? null) !== null;
    const classes = [
      'entree',
      entree.reason !== 'consumption' ? 'jete' : '',
      corrigee ? 'corrigee' : '',
      contrepassation ? 'contrepassation' : '',
    ].filter(Boolean).join(' ');
    return html`
      <li class=${classes}>
        <button class="entree-ouvrir" @click=${() => this.ouvrirDetail(entree)}>
          <span class="entree-nom">${entree.product_name}</span>
          <span class="entree-quantite">
            ${formaterNombre(Math.abs(entree.quantity))} ${entree.base_unit}
          </span>
          ${partagee ? html`
            <span class="entree-parts">${entree.parts_mine ?? 0}/${entree.parts_total}</span>
          ` : nothing}
          <span class="entree-kcal">${entree.kcal === null ? '—' : `${Math.round(entree.kcal)} kcal`}</span>
        </button>
        ${this.detailOuvert === entree.id ? this.rendreDetail() : nothing}
      </li>
    `;
  }

  /** Ouvre le détail et demande au serveur ce que la correction ferait. Le
   *  panneau ne le CALCULE jamais lui-même : la quantité rendue, le lot visé
   *  et le refus éventuel sont des faits que seul le serveur connaît. */
  private async ouvrirDetail(entree: EntreeJournal): Promise<void> {
    if (this.detailOuvert === entree.id) {
      this.detailOuvert = null;
      return;
    }
    this.detailOuvert = entree.id;
    this.apercu = null;
    this.correctionArmee = null;
    if (!this.connexion) return;
    try {
      this.apercu = await this.connexion.appeler<ApercuCorrection>(
        'home_stock/movement/correction_preview', { movement_id: entree.id });
    } catch {
      // Le détail reste ouvert et vide : mieux qu'un écran qui se referme
      // tout seul sans dire pourquoi.
      this.apercu = null;
    }
  }

  private ecrire(type: string, charge: Record<string, unknown>): void {
    if (!this.file) return;
    this.file.ajouter(type, charge);
    this.dispatchEvent(new CustomEvent('file-changee', { bubbles: true, composed: true }));
    void this.file.rejouer();
  }

  private confirmerCorrection(): void {
    const armee = this.correctionArmee;
    if (!armee) return;
    if (armee.cible === 'mouvement') {
      this.ecrire('home_stock/movement/correct', { movement_id: armee.id });
    } else {
      this.ecrire('home_stock/meal/correct', { meal_id: armee.id });
    }
    this.correctionArmee = null;
    this.detailOuvert = null;
  }

  private rendreDetail() {
    const apercu = this.apercu;
    if (!apercu) return html`<div class="detail"><p>Chargement…</p></div>`;
    const lot = apercu.batch_entered_at
      ? ` et remet ${formaterNombre(apercu.quantity)} ${apercu.base_unit ?? ''} `
        + `dans le lot du ${apercu.batch_entered_at.slice(0, 10)}`
      : '';
    const chiffres = [
      apercu.kcal === null ? null : `${Math.round(apercu.kcal)} kcal`,
      apercu.cost === null ? null : formaterEuros(apercu.cost),
    ].filter(Boolean).join(', ');
    return html`
      <div class="detail">
        <p class="annonce">${
          `Annule ${formaterNombre(apercu.quantity)} ${apercu.base_unit ?? ''} `
          + `de ${apercu.product_name ?? ''}`
          + (chiffres ? ` — ${chiffres}` : '') + lot + '.'
        }</p>
        ${apercu.refusal ? html`<p class="refus">${apercu.refusal}</p>` : nothing}
        ${this.correctionArmee ? html`
          <button class="confirmer-correction" @click=${this.confirmerCorrection}>
            Confirmer
          </button>
          <button class="annuler-correction"
            @click=${() => { this.correctionArmee = null; }}>Annuler</button>
        ` : html`
          ${apercu.correctable ? html`
            <button class="corriger" @click=${() => {
              this.correctionArmee = { cible: 'mouvement', id: apercu.movement_id };
            }}>Corriger</button>
          ` : nothing}
          ${!apercu.correctable && apercu.meal_id ? html`
            <button class="corriger-repas" @click=${() => {
              this.correctionArmee = { cible: 'repas', id: apercu.meal_id! };
            }}>Corriger le repas</button>
          ` : nothing}
        `}
      </div>
    `;
  }

  private rendreJour() {
    const jour = this.jour;
    if (!jour) return nothing;
    return html`
      <section class="jour">
        <h2 class="titre-jour">${jour.food_day}</h2>
        ${jour.entries.length === 0 ? html`
          <p class="vide">Rien de déclaré ce jour-là.</p>
        ` : html`
          <ul class="entrees">
            ${jour.entries.map((e) => this.rendreEntree(e))}
          </ul>
        `}
        <p class="total-kcal">${Math.round(jour.totals.kcal)} kcal</p>
        <p class="total-cout">
          ${formaterEuros(jour.totals.cost)}
          ${jour.totals.waste_cost > 0 ? html` — dont ${formaterEuros(jour.totals.waste_cost)} jeté` : nothing}
        </p>
        ${jour.totals.unvalued > 0 ? html`
          <p class="non-chiffre">${jour.totals.unvalued} sortie(s) sans calories connues.</p>
        ` : nothing}
        ${this.rendreObjectifs(jour)}
      </section>
    `;
  }

  /** Une ligne par objectif réglé — « Sel 1,2 / 6 g » — et, quand la moyenne
   *  des sept journées closes dépasse elle aussi, une seconde ligne grise.
   *  Aucun objectif réglé : aucune ligne, et l'écran reste celui du lot 2.
   *
   *  Ce sont des PLAFONDS : une journée vide ne dépasse rien, donc rien ne
   *  s'y marque — il n'y a aucune garde « la journée est vide » à écrire. */
  private rendreObjectifs(jour: JourJournal) {
    const objectifs = jour.goals ?? {};
    const semaine = jour.week_mean ?? {};
    const lignes = Object.keys(LIBELLE_NUTRIMENT)
      .filter((nutriment) => typeof objectifs[nutriment] === 'number');
    if (lignes.length === 0) return nothing;
    return html`
      <ul class="objectifs">
        ${lignes.map((nutriment) => {
          const { nom, unite } = LIBELLE_NUTRIMENT[nutriment];
          const plafond = objectifs[nutriment];
          const valeurJour = (jour.totals as Record<string, number | undefined>)[nutriment] ?? 0;
          const valeurSemaine = (semaine as Record<string, number | undefined>)[nutriment];
          return html`
            <li class="objectif ${valeurJour > plafond ? 'objectif-depasse' : ''}">
              ${nom} ${formaterNombre(valeurJour)} / ${formaterNombre(plafond)} ${unite}
            </li>
            ${typeof valeurSemaine === 'number' && valeurSemaine > plafond ? html`
              <li class="objectif-semaine">
                ${nom}, moyenne sur 7 jours ${formaterNombre(valeurSemaine)} /
                ${formaterNombre(plafond)} ${unite}
              </li>
            ` : nothing}
          `;
        })}
      </ul>
    `;
  }

  /** Le seau touché en vue « semaine » ou « mois » : ses propres totaux,
   *  pas le détail d'un jour qui ne le représenterait qu'en partie. Un
   *  seau n'a ni liste d'entrées ni compteur `unvalued` (voir SeauJournal) —
   *  seuls kcal et coût s'affichent, à l'identique du bloc totaux du jour. */
  private rendreSeauTotaux() {
    const seau = this.seauSelectionne;
    if (!seau) return nothing;
    return html`
      <section class="jour">
        <h2 class="titre-jour">${seau.label}</h2>
        <p class="total-kcal">${Math.round(seau.kcal)} kcal</p>
        <p class="total-cout">
          ${formaterEuros(seau.cost)}
          ${seau.waste_cost > 0 ? html` — dont ${formaterEuros(seau.waste_cost)} jeté` : nothing}
        </p>
      </section>
    `;
  }

  render() {
    return html`
      <h1 class="titre">Journal</h1>
      ${this.rendreGranularites()}
      ${this.rendreBarres()}
      ${this.granularite === 'day' ? this.rendreJour() : this.rendreSeauTotaux()}
    `;
  }

  static styles = css`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .titre { margin: 0 0 8px; font-size: 1.2rem; }
    .granularites { display: flex; gap: 8px; margin-bottom: 8px; }
    .granularite {
      flex: 1 1 auto; min-height: 48px; border-radius: 8px; border: none; font-size: 0.9rem;
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .granularite-active { background: var(--primary-color); color: var(--text-primary-color, #fff); }
    .entree-ouvrir {
      display: flex; width: 100%; gap: 8px; align-items: baseline; min-height: 48px;
      border: none; background: transparent; color: inherit; font: inherit;
      text-align: left; padding: 0;
    }
    .corrigee .entree-nom, .corrigee .entree-quantite { text-decoration: line-through; }
    .contrepassation { color: var(--secondary-text-color); }
    .detail {
      margin: 4px 0 8px; padding: 8px; border-radius: 8px;
      background: var(--secondary-background-color);
    }
    .annonce { margin: 0 0 8px; }
    .refus { margin: 0 0 8px; color: var(--secondary-text-color); font-size: 0.9rem; }
    .corriger, .corriger-repas, .confirmer-correction, .annuler-correction {
      display: block; width: 100%; min-height: 48px; border-radius: 8px; border: none;
      margin-top: 8px; font-size: 1rem;
    }
    .corriger, .corriger-repas, .confirmer-correction {
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .annuler-correction {
      background: var(--card-background-color, #fff); color: var(--primary-text-color);
    }
    .objectifs { list-style: none; margin: 4px 0 0; padding: 0; }
    .objectif { font-size: 0.95rem; }
    .objectif-depasse { color: var(--error-color, #b3261e); }
    .objectif-semaine { font-size: 0.9rem; color: var(--secondary-text-color); }
    /* La cible tactile de .barre est fixe (colonne pleine hauteur ici,
       ligne pleine largeur sous 700 px) — jamais la grandeur du seau, qui ne
       viendrait qu'agrandir les gros jours et rétrécir les petits sous les
       48 px. Quatorze seaux sur 412 px ne tiennent pas en colonnes larges de
       48 px (14 x 48 > 372 px de contenu disponible) : sous 700 px, le
       graphe passe donc en liste de lignes empilées, chacune pleine largeur,
       où c'est la largeur du remplissage qui porte la valeur. */
    .barres {
      display: flex; gap: 4px; margin: 8px 0 16px;
      padding: 8px; border-radius: 8px; background: var(--secondary-background-color); box-sizing: border-box;
    }
    .barre {
      flex: 1 1 auto; min-width: 12px; height: 120px; min-height: 48px; box-sizing: border-box;
      display: flex; align-items: flex-end; border: none; border-radius: 4px; background: transparent; padding: 0;
    }
    .barre-remplissage {
      display: block; width: 100%; height: var(--part); min-height: 4px;
      border-radius: 4px 4px 0 0; background: var(--primary-color); pointer-events: none;
    }
    @media (max-width: 700px) {
      .barres { flex-direction: column; }
      .barre { flex: none; width: 100%; height: auto; min-height: 48px; align-items: stretch; }
      .barre-remplissage { width: var(--part); height: 100%; min-width: 4px; min-height: 0; border-radius: 0 4px 4px 0; }
    }
    .jour { margin-top: 8px; }
    .titre-jour { margin: 0 0 8px; font-size: 1rem; color: var(--secondary-text-color); }
    .entrees { list-style: none; margin: 0 0 8px; padding: 0; }
    .entree {
      display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-height: 48px;
      padding: 8px 0; border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .entree-nom { flex: 1 1 auto; }
    .entree-quantite, .entree-kcal { color: var(--secondary-text-color); font-size: 0.85rem; }
    .entree-parts {
      font-size: 0.8rem; padding: 2px 6px; border-radius: 999px;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .entree.jete { color: var(--error-color, #b3261e); }
    .vide { color: var(--secondary-text-color); }
    .total-kcal { margin: 4px 0 0; font-size: 1.1rem; font-weight: 600; }
    .total-cout { margin: 2px 0; color: var(--secondary-text-color); }
    .non-chiffre { color: var(--error-color, #b3261e); font-size: 0.85rem; }
  `;
}
