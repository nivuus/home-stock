/** L'écran « Liste » : ce qu'il faut acheter, dans l'ordre du magasin où l'on
 *  est.
 *
 *  Les lignes viennent de `home_stock/list/items`, déjà triées côté serveur
 *  par l'ordre appris de ce magasin (`store_aisle.position`, à défaut
 *  `aisle.position`). Cet écran ne fait qu'un passage linéaire pour les
 *  grouper visuellement : il ne retrie JAMAIS — c'est ce tri-là qui est testé
 *  côté serveur, et le refaire ici laisserait les deux dériver.
 *
 *  Cocher est UN appui, pas deux. Le double appui protège les gestes
 *  destructifs (cocher une tâche de maintenance, supprimer une ligne de
 *  panier) ; cocher une ligne de courses porte un bit, et se défait sur place
 *  d'un appui.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';

/** Une revendication : pourquoi cette ligne est là. */
export type Revendication = {
  origin: 'shortage' | 'meal_plan' | 'manual' | 'recurring';
  quantity: number | null;
  detail: string | null;
};

/** Une ligne de liste, exactement comme `home_stock/list/items` la rend. */
export type LigneListe = {
  id: number;
  product_id: number | null;
  free_text: string | null;
  quantity: number | null;
  note: string | null;
  added_at: string;
  checked_at: string | null;
  removed_at: string | null;
  session_id: number | null;
  line_id: number | null;
  product_name: string | null;
  base_unit: string | null;
  aisle_id: number | null;
  aisle_name: string | null;
  aisle_position: number;
  claims: Revendication[];
};

export type Estimation = {
  amount: number;
  confidence: number;
  priced: number;
  total: number;
};

export type DonneesListe = {
  items: LigneListe[];
  store_id: number | null;
  store_name: string | null;
  estimate: Estimation;
};

function formaterEuros(valeur: number): string {
  return `${valeur.toFixed(2).replace('.', ',')} €`;
}

/** Groupe des lignes DÉJÀ triées, par un simple passage linéaire — ne jamais
 *  trier ici, seulement grouper ce qui est déjà contigu. */
export function grouperListeParRayon(
  lignes: LigneListe[],
): { rayon: string; lignes: LigneListe[] }[] {
  const groupes: { rayon: string; lignes: LigneListe[] }[] = [];
  for (const ligne of lignes) {
    const rayon = ligne.aisle_name ?? 'Sans rayon';
    const dernier = groupes[groupes.length - 1];
    if (dernier && dernier.rayon === rayon) dernier.lignes.push(ligne);
    else groupes.push({ rayon, lignes: [ligne] });
  }
  return groupes;
}

/** Ce qu'on affiche à droite du nom. Sans quantité, « ce qu'il faut » : la
 *  liste dit qu'elle ne sait pas, plutôt que d'écrire « 0 ». */
export function quantiteAffichee(ligne: LigneListe): string {
  if (ligne.quantity === null) return 'ce qu’il faut';
  const unite = ligne.base_unit && ligne.base_unit !== 'piece' ? ` ${ligne.base_unit}` : '';
  return `${ligne.quantity}${unite}`;
}

@customElement('home-stock-liste')
export class EcranListe extends LitElement {
  @property({ attribute: false }) donnees: DonneesListe | null = null;
  @property({ attribute: false }) connexion?: Connexion;
  /** Au-delà de 1000 px, la place existe pour une mise en page dense. Posé par
   *  le panneau, qui la MESURE (`window.innerWidth`) et laisse un hôte étroit
   *  la refuser. Faux par défaut : l'écran étroit reste la mise en page de
   *  référence, et c'est la large qui doit se justifier. */
  @property({ type: Boolean }) large = false;
  /** Toute écriture passe par la file : cet écran se lit debout dans un
   *  rayon, l'endroit où le réseau lâche le plus souvent. */
  @property({ attribute: false }) file?: FileAttente;
  @property({ attribute: false }) enAttente = 0;

  /** Ce qu'on vient de cocher ou de retirer sans que le serveur ait encore
   *  répondu. Sans cet état, un appui hors ligne n'aurait AUCUN effet visible
   *  et la ligne semblerait ne pas avoir été prise en compte — le défaut
   *  exact que la file existe pour éviter. */
  @state() private cocheesLocalement = new Set<number>();
  @state() private decocheesLocalement = new Set<number>();
  @state() private retireesLocalement = new Set<number>();
  @state() private saisie = '';

  connectedCallback(): void {
    super.connectedCallback();
    void this.charger();
  }

  /** Se charge elle-même quand une connexion est là, comme `piles` et
   *  `journal` : le panneau n'a pas à connaître la forme de la liste pour la
   *  lui passer. Les tests montent l'écran sans connexion et lui donnent
   *  `donnees` directement. */
  private async charger(): Promise<void> {
    if (!this.connexion) return;
    this.donnees = await this.connexion.appeler<DonneesListe>('home_stock/list/items');
    this.cocheesLocalement = new Set();
    this.decocheesLocalement = new Set();
    this.retireesLocalement = new Set();
  }

  private ecrire(type: string, charge: Record<string, unknown>): void {
    if (!this.file) return;
    this.file.ajouter(type, charge);
    this.avertirFile();
    void this.file.rejouer().then(() => {
      this.avertirFile();
      void this.charger();
    });
  }

  private avertirFile(): void {
    this.dispatchEvent(new CustomEvent('file-changee', { bubbles: true, composed: true }));
  }

  private estCochee(ligne: LigneListe): boolean {
    if (this.decocheesLocalement.has(ligne.id)) return false;
    return this.cocheesLocalement.has(ligne.id) || ligne.checked_at !== null;
  }

  private cocher(ligne: LigneListe): void {
    this.cocheesLocalement = new Set(this.cocheesLocalement).add(ligne.id);
    const restantes = new Set(this.decocheesLocalement);
    restantes.delete(ligne.id);
    this.decocheesLocalement = restantes;
    this.ecrire('home_stock/list/check', { item_id: ligne.id });
  }

  private decocher(ligne: LigneListe): void {
    this.decocheesLocalement = new Set(this.decocheesLocalement).add(ligne.id);
    const restantes = new Set(this.cocheesLocalement);
    restantes.delete(ligne.id);
    this.cocheesLocalement = restantes;
    this.ecrire('home_stock/list/uncheck', { item_id: ligne.id });
  }

  private retirer(ligne: LigneListe): void {
    this.retireesLocalement = new Set(this.retireesLocalement).add(ligne.id);
    this.ecrire('home_stock/list/remove', { item_id: ligne.id });
  }

  private ajouter(): void {
    const texte = this.saisie.trim();
    if (!texte) return;
    this.ecrire('home_stock/list/add', { free_text: texte });
    this.saisie = '';
  }

  private origines(ligne: LigneListe): string {
    return ligne.claims.map((c) => c.detail).filter(Boolean).join(' · ');
  }

  private rendreLigne(ligne: LigneListe, cochee: boolean) {
    const nom = ligne.product_name ?? ligne.free_text ?? '';
    const origines = this.origines(ligne);
    return html`
      <article class="ligne ${cochee ? 'ligne-cochee' : ''}">
        <button class=${cochee ? 'decocher' : 'cocher'}
          aria-label=${cochee ? `Décocher ${nom}` : `Cocher ${nom}`}
          @click=${() => (cochee ? this.decocher(ligne) : this.cocher(ligne))}>
          ${cochee ? '☑' : '☐'}
        </button>
        <div class="infos">
          <p class="nom">${nom}</p>
          <p class="quantite">${quantiteAffichee(ligne)}</p>
          ${origines ? html`<p class="origines">${origines}</p>` : nothing}
        </div>
        <button class="retirer" aria-label=${`Retirer ${nom} de la liste`}
          @click=${() => this.retirer(ligne)}>×</button>
      </article>
    `;
  }

  render() {
    const donnees = this.donnees;
    if (!donnees) return html`<p class="vide">Liste indisponible.</p>`;
    const visibles = donnees.items.filter((l) => !this.retireesLocalement.has(l.id));
    const ouvertes = visibles.filter((l) => !this.estCochee(l));
    const cochees = visibles.filter((l) => this.estCochee(l));
    const estimation = donnees.estimate;
    return html`
      <section class="bandeau">
        <p class="magasin">${donnees.store_name ?? 'Ordre par défaut'}</p>
        <p class="compte">${
          `${ouvertes.length} ligne${ouvertes.length > 1 ? 's' : ''} — ≈ ${formaterEuros(estimation.amount)}`
        }</p>
        <p class="confiance">${
          `estimation sur ${estimation.priced} ligne${estimation.priced > 1 ? 's' : ''} sur ${estimation.total}`
        }</p>
      </section>

      ${this.enAttente > 0 ? html`
        <p class="en-attente">
          ${this.enAttente} envoi${this.enAttente > 1 ? 's' : ''} en attente de réseau
        </p>
      ` : nothing}

      <section class="ajout">
        <input class="champ-ajout" .value=${this.saisie} placeholder="Ajouter une ligne"
          aria-label="Ajouter une ligne"
          @input=${(e: InputEvent) => { this.saisie = (e.target as HTMLInputElement).value; }} />
        <button class="ajouter" @click=${this.ajouter}>Ajouter</button>
      </section>

      ${ouvertes.length === 0 ? html`
        <p class="vide">Rien à acheter pour l’instant.</p>
      ` : nothing}

      ${(() => {
        const rayons = grouperListeParRayon(ouvertes).map((groupe) => html`
          <section class="rayon">
            <h3 class="rayon-nom">${groupe.rayon}</h3>
            ${groupe.lignes.map((ligne) => this.rendreLigne(ligne, false))}
          </section>
        `);
        // Au-delà de 1000 px les rayons cessent d'être empilés : une ligne de
        // courses est COURTE mais large, et quatre rayons les uns sous les
        // autres imposent de défiler pour une information qui tient sur un
        // écran. Rien d'autre ne change : mêmes lignes, mêmes commandes, même
        // texte — élargir n'ajoute pas une donnée.
        return this.large ? html`<div class="rayons-colonnes">${rayons}</div>` : rayons;
      })()}

      ${cochees.length > 0 ? html`
        <section class="cochees">
          <h3 class="rayon-nom">Dans le chariot (${cochees.length})</h3>
          ${cochees.map((ligne) => this.rendreLigne(ligne, true))}
        </section>
      ` : nothing}
    `;
  }

  static styles = css`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .bandeau {
      display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px;
      justify-content: space-between; margin-bottom: 8px;
    }
    .magasin { font-weight: 600; margin: 0; }
    .compte { font-size: 1.2rem; font-weight: 700; margin: 0; }
    .confiance { font-size: 0.8rem; color: var(--secondary-text-color); margin: 0; flex-basis: 100%; }
    .en-attente { text-align: center; color: var(--secondary-text-color); font-size: 0.85rem; margin: 4px 0 8px; }
    .ajout { display: flex; gap: 8px; margin-bottom: 8px; }
    .champ-ajout { flex: 1; min-height: 48px; box-sizing: border-box; font-size: 1rem; padding: 4px 8px; }
    .ajouter {
      min-height: 48px; min-width: 88px; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .vide { color: var(--secondary-text-color); text-align: center; }
    .rayon-nom {
      margin: 16px 0 4px; font-size: 0.9rem; text-transform: uppercase;
      color: var(--secondary-text-color); letter-spacing: 0.04em;
    }

    /* --- la vue dense (lot 6) ---------------------------------------------
       Des colonnes d'au moins 320 px : en dessous, le nom, la quantité et
       l'origine d'une ligne se cassent en trois et on perd tout le gain.
       Le remplissage automatique laisse le nombre de colonnes suivre la largeur
       réelle, plutôt que de le figer à trois. */
    .rayons-colonnes {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 0 24px; align-items: start;
    }
    .rayons-colonnes .rayon { break-inside: avoid; }
    .ligne {
      display: flex; align-items: center; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .ligne-cochee .nom { text-decoration: line-through; color: var(--secondary-text-color); }
    .cocher, .decocher {
      min-width: 48px; min-height: 48px; border-radius: 8px; border: none; font-size: 1.3rem;
      background: var(--secondary-background-color); color: var(--primary-text-color); flex-shrink: 0;
    }
    .infos { flex: 1; min-width: 0; }
    .nom { margin: 0; }
    .quantite { margin: 2px 0 0; font-size: 0.9rem; color: var(--secondary-text-color); }
    .origines { margin: 2px 0 0; font-size: 0.8rem; color: var(--secondary-text-color); }
    .retirer {
      min-width: 48px; min-height: 48px; border-radius: 8px; border: none; font-size: 1.2rem;
      background: var(--secondary-background-color); color: var(--primary-text-color); flex-shrink: 0;
    }
  `;
}
