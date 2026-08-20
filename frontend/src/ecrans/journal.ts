/** L'écran « journal » : ce qui est sorti du stock, jour par jour.
 *
 *  Deux vues : le détail d'UNE journée (`home_stock/journal/day`) et un
 *  histogramme de plusieurs seaux (`home_stock/journal/series`) — jour,
 *  semaine ou mois — qui sert à choisir la journée à ouvrir. Toucher une
 *  barre recharge le détail sur le jour qu'elle représente ; pour une
 *  semaine ou un mois, son `label` est déjà le premier jour du seau, que
 *  `journal/day` accepte tel quel — aucune conversion ici.
 *
 *  Écran de lecture seule : aucune file hors-ligne, aucune écriture. Comme
 *  le catalogue, il tolère un aller-retour réseau — ce n'est jamais un
 *  rayon de magasin qui le consulte.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
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
  kcal: number;
  parts_total: number | null;
  parts_mine: number | null;
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
    await this.chargerSerie(granularite);
  }

  /** Recharge le détail sur le jour d'un seau touché — pour `week` et
   *  `month`, `label` est déjà le premier jour du seau (voir l'en-tête). */
  async ouvrirSeau(label: string): Promise<void> {
    await this.chargerJour(label);
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
                    @click=${() => this.ouvrirSeau(seau.label)}>
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
    return html`
      <li class="entree ${entree.reason !== 'consumption' ? 'jete' : ''}">
        <span class="entree-nom">${entree.product_name}</span>
        <span class="entree-quantite">
          ${formaterNombre(Math.abs(entree.quantity))} ${entree.base_unit}
        </span>
        ${partagee ? html`<span class="entree-parts">${entree.parts_mine ?? 0}/${entree.parts_total}</span>` : nothing}
        <span class="entree-kcal">${Math.round(entree.kcal)} kcal</span>
      </li>
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
          <p class="non-chiffre">${jour.totals.unvalued} sortie(s) sans prix connu.</p>
        ` : nothing}
      </section>
    `;
  }

  render() {
    return html`
      <h1 class="titre">Journal</h1>
      ${this.rendreGranularites()}
      ${this.rendreBarres()}
      ${this.rendreJour()}
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
