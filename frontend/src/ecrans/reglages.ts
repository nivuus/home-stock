/** L'écran Réglages : l'ordre des rayons, la liste des emplacements, et la
 *  resynchronisation Open Food Facts — un écran de bureau, comme le
 *  Catalogue, jamais consulté au milieu d'un rayon de magasin.
 *
 *  Le réordonnancement des rayons se fait par boutons « monter » / « descendre »,
 *  jamais par glisser-déposer : la contrainte « aucun geste » du panneau vaut
 *  ici comme partout ailleurs. Chaque appui envoie la liste ordonnée complète
 *  à `home_stock/aisles/reorder`, qui refuse tout identifiant de rayon
 *  inconnu — donc toujours la liste actuelle, jamais une liste reconstruite
 *  à la main. L'ordre affiché bouge tout de suite (optimiste), mais si le
 *  serveur refuse, l'écran recharge la vraie liste au lieu de continuer à
 *  montrer — et à renvoyer au prochain appui — un ordre que le serveur n'a
 *  jamais accepté.
 *
 *  Le réordonnancement passe par la file hors-ligne comme le Catalogue (une
 *  écriture est une écriture). La resynchronisation, elle, n'y passe pas :
 *  `home_stock.resync_off` est un SERVICE Home Assistant, pas une commande
 *  websocket du domaine — `FileAttente` ne sait rejouer que des commandes
 *  `home_stock/*`, et une resynchronisation qu'on ne voulait plus (retardée
 *  hors ligne, puis rejouée sans qu'on s'y attende des heures plus tard)
 *  serait pire qu'un simple échec immédiat à retenter à la main.
 */
import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { Connexion } from '../connexion';
import type { FileAttente } from '../file-attente';
import type { Emplacement } from './rangement';
import type { Rayon } from './catalogue';

/** Les seuls messages que `home_stock.resync_off` est connu pour renvoyer,
 *  déjà rédigés en français pour être lus tels quels (voir `resync_off`,
 *  `services.py`). Tout le reste — une exception Python imprévue, jamais
 *  traduite — obtient le message générique plutôt que d'être montré tel
 *  quel : même principe de liste blanche que `CODES_DE_REFUS_EN_FRANCAIS`
 *  dans `file-attente.ts`, adapté à un appel de service, qui ne porte pas de
 *  code d'erreur structuré comme une commande websocket du domaine — seulement
 *  un texte. */
const MESSAGES_RESYNC_CONNUS: ReadonlySet<string> = new Set([
  'Une resynchronisation Open Food Facts est déjà en cours.',
]);
const MESSAGE_RESYNC_GENERIQUE = "La resynchronisation n'a pas pu être lancée.";

function messageResyncAffichable(err: unknown): string {
  const texte = err && typeof err === 'object' && 'message' in err && typeof (err as any).message === 'string'
    ? (err as any).message as string : null;
  return texte !== null && MESSAGES_RESYNC_CONNUS.has(texte) ? texte : MESSAGE_RESYNC_GENERIQUE;
}

/** Fait remonter (ou descendre) l'élément d'index `index` d'un cran — une
 *  permutation simple, jamais un tri : l'ordre de tout le reste ne bouge
 *  pas. `null` si le mouvement demandé n'a pas de sens (déjà en haut / en
 *  bas), pour que l'appelant sache ne rien envoyer. */
export function deplacer<T>(liste: T[], index: number, sens: -1 | 1): T[] | null {
  const cible = index + sens;
  if (cible < 0 || cible >= liste.length) return null;
  const copie = [...liste];
  [copie[index], copie[cible]] = [copie[cible], copie[index]];
  return copie;
}

@customElement('home-stock-reglages')
export class EcranReglages extends LitElement {
  @property({ attribute: false }) connexion?: Connexion;
  /** La file hors-ligne : le réordonnancement des rayons est une écriture
   *  comme une autre (spec §14). */
  @property({ attribute: false }) file?: FileAttente;
  @property({ attribute: false }) enAttente = 0;

  @state() private rayons: Rayon[] = [];
  @state() private emplacements: Emplacement[] = [];
  @state() private erreurChargement: string | null = null;

  @state() private resyncEnCours = false;
  @state() private messageResync: string | null = null;
  @state() private erreurResync: string | null = null;

  connectedCallback(): void {
    super.connectedCallback();
    void this.charger();
  }

  private async charger(): Promise<void> {
    if (!this.connexion) return;
    this.erreurChargement = null;
    try {
      const [rayons, emplacements] = await Promise.all([
        this.connexion.appeler<{ aisles: Rayon[] }>('home_stock/aisles/list'),
        this.connexion.appeler<{ locations: Emplacement[] }>('home_stock/locations/list'),
      ]);
      this.rayons = rayons.aisles;
      this.emplacements = emplacements.locations;
    } catch {
      this.erreurChargement = 'Impossible de récupérer les rayons et les emplacements. Vérifiez la connexion.';
    }
  }

  private avertirFile(): void {
    this.dispatchEvent(new CustomEvent('file-changee', { bubbles: true, composed: true }));
  }

  /** Empile, rejoue tout de suite, et — c'est ce qui distingue ce geste du
   *  même motif dans le Catalogue — recharge la vraie liste depuis le
   *  serveur si CE réordonnancement précis a été refusé (un rayon disparu
   *  entre-temps, par exemple). Sans ça, l'écran continuerait d'afficher un
   *  ordre optimiste que le serveur n'a jamais accepté, et le renverrait
   *  identique au prochain appui. Une panne de transport (toujours en
   *  file, hors ligne) laisse l'ordre optimiste en place — la file le
   *  retentera d'elle-même. */
  private async deplacerRayon(index: number, sens: -1 | 1): Promise<void> {
    const nouvelOrdre = deplacer(this.rayons, index, sens);
    if (nouvelOrdre === null) return;
    this.rayons = nouvelOrdre;
    if (!this.file) return;
    const suivi = this.file.ajouter('home_stock/aisles/reorder', { aisle_ids: nouvelOrdre.map((r) => r.id) });
    this.avertirFile();
    await this.file.rejouer();
    this.avertirFile();
    if (await suivi.sort === 'refusee') {
      // Déjà signalé en français dans la bannière globale du panneau : rien
      // à ajouter ici, seulement corriger l'affichage.
      await this.charger();
    }
  }

  private async resynchroniser(): Promise<void> {
    if (!this.connexion || this.resyncEnCours) return;
    this.resyncEnCours = true;
    this.messageResync = null;
    this.erreurResync = null;
    try {
      await this.connexion.appelerService('home_stock', 'resync_off', { all: true });
      this.messageResync = 'Resynchronisation lancée en tâche de fond — environ 40 minutes pour tout le catalogue. '
        + 'Les champs corrigés à la main ne sont jamais écrasés.';
    } catch (err) {
      this.erreurResync = messageResyncAffichable(err);
    } finally {
      this.resyncEnCours = false;
    }
  }

  private rendreRayons() {
    if (this.rayons.length === 0) return html`<p class="vide">Aucun rayon.</p>`;
    return html`
      <ul class="liste-rayons">
        ${this.rayons.map((rayon, index) => html`
          <li class="rayon">
            <span class="rayon-nom">${rayon.name}</span>
            <span class="rayon-boutons">
              <button class="monter" aria-label="Monter ${rayon.name}" ?disabled=${index === 0}
                @click=${() => { void this.deplacerRayon(index, -1); }}>▲</button>
              <button class="descendre" aria-label="Descendre ${rayon.name}"
                ?disabled=${index === this.rayons.length - 1}
                @click=${() => { void this.deplacerRayon(index, 1); }}>▼</button>
            </span>
          </li>
        `)}
      </ul>
    `;
  }

  private rendreEmplacements() {
    if (this.emplacements.length === 0) return html`<p class="vide">Aucun emplacement.</p>`;
    return html`
      <ul class="liste-emplacements">
        ${this.emplacements.map((emp) => html`
          <li class="emplacement">
            <span class="emplacement-nom">${emp.name}</span>
            <span class="emplacement-type">${emp.kind}</span>
          </li>
        `)}
      </ul>
    `;
  }

  render() {
    return html`
      ${this.enAttente > 0 ? html`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente > 1 ? 's' : ''} en attente de réseau</p>
      ` : nothing}

      ${this.erreurChargement ? html`
        <p class="erreur">${this.erreurChargement}</p>
        <button class="reessayer" @click=${() => { void this.charger(); }}>Réessayer</button>
      ` : nothing}

      <section class="section">
        <h3 class="titre">Ordre des rayons</h3>
        <p class="explication">
          L'ordre du parcours en magasin — utilisé pour trier le panier. Pas de glisser-déposer :
          « monter » et « descendre » déplacent un rayon d'un cran.
        </p>
        ${this.rendreRayons()}
      </section>

      <section class="section">
        <h3 class="titre">Emplacements</h3>
        ${this.rendreEmplacements()}
      </section>

      <section class="section">
        <h3 class="titre">Open Food Facts</h3>
        <p class="explication">
          Relit tout le catalogue depuis Open Food Facts — environ 40 minutes au rythme qu'OFF tolère.
          Les champs corrigés à la main ne sont jamais écrasés.
        </p>
        <button class="resynchroniser" ?disabled=${this.resyncEnCours} @click=${this.resynchroniser}>
          ${this.resyncEnCours ? 'Lancement…' : 'Resynchroniser Open Food Facts'}
        </button>
        ${this.messageResync ? html`<p class="message-resync">${this.messageResync}</p>` : nothing}
        ${this.erreurResync ? html`<p class="erreur">${this.erreurResync}</p>` : nothing}
      </section>
    `;
  }

  static styles = css`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .en-attente { text-align: center; color: var(--secondary-text-color); font-size: 0.85rem; margin: 0 0 8px; }
    .erreur { color: var(--error-color, #b3261e); font-size: 0.9rem; }
    .reessayer {
      min-height: 48px; width: 100%; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .section {
      margin: 0 0 20px; padding: 12px; border-radius: 8px; background: var(--secondary-background-color);
    }
    .titre { margin: 0 0 4px; font-size: 1rem; }
    .explication { margin: 0 0 8px; color: var(--secondary-text-color); font-size: 0.85rem; }
    .vide { color: var(--secondary-text-color); }
    .liste-rayons, .liste-emplacements { list-style: none; margin: 0; padding: 0; }
    .rayon, .emplacement {
      display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px;
      padding: 8px 0; border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .rayon:last-child, .emplacement:last-child { border-bottom: none; }
    .rayon-nom, .emplacement-nom { flex: 1; min-width: 0; }
    .emplacement-type { color: var(--secondary-text-color); font-size: 0.85rem; }
    .rayon-boutons { display: flex; gap: 8px; flex-shrink: 0; }
    .monter, .descendre {
      min-width: 48px; min-height: 48px; border-radius: 8px; border: none; font-size: 1.1rem;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .monter:disabled, .descendre:disabled { opacity: 0.4; }
    .resynchroniser {
      display: block; width: 100%; min-height: 48px; border-radius: 8px; border: none; font-size: 0.95rem;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .resynchroniser:disabled { opacity: 0.6; }
    .message-resync { color: var(--secondary-text-color); font-size: 0.85rem; margin: 8px 0 0; }
  `;
}
