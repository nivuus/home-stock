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
import type { Magasin } from './panier';

/** Un rayon dans le parcours d'UN magasin, tel que `home_stock/store/aisles`
 *  le rend. `mean_rank` reste visible même sur une ligne épinglée : on doit
 *  VOIR que l'apprentissage la contredit. */
export type RayonMagasin = {
  store_id: number;
  aisle_id: number;
  position: number;
  source: 'learned' | 'manual';
  mean_rank: number | null;
  observed_sessions: number;
  updated_at: string | null;
  aisle_name: string;
  default_position: number;
};

export type ParcoursMagasin = {
  store_id: number;
  aisles: RayonMagasin[];
  observed_sessions: number;
  required_sessions: number;
  reliable: boolean;
};

export type Recurrente = {
  id: number;
  product_id: number | null;
  free_text: string | null;
  quantity: number | null;
  every_days: number;
  last_added_on: string | null;
  active: number;
  product_name: string | null;
  base_unit: string | null;
};
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
  /** Au-delà de 1000 px, la place existe pour une mise en page dense. Posé par
   *  le panneau, qui la MESURE (`window.innerWidth`) et laisse un hôte étroit
   *  la refuser. Faux par défaut : l'écran étroit reste la mise en page de
   *  référence, et c'est la large qui doit se justifier. */
  @property({ type: Boolean }) large = false;
  /** La file hors-ligne : le réordonnancement des rayons est une écriture
   *  comme une autre (spec §14). */
  @property({ attribute: false }) file?: FileAttente;
  @property({ attribute: false }) enAttente = 0;

  @state() private rayons: Rayon[] = [];
  @state() private emplacements: Emplacement[] = [];
  @state() private erreurChargement: string | null = null;

  // --- lot 4 : magasins, parcours par magasin, récurrences ---------------
  /** Les magasins connus, l'onglet ouvert et son parcours. L'ordre appris
   *  vit PAR MAGASIN : celui du lot 1 reste le repli, pour un rayon jamais
   *  vu ici. */
  @state() private magasins: Magasin[] = [];
  @state() private magasinOuvert: number | null = null;
  @state() private parcours: ParcoursMagasin | null = null;
  /** La fusion armée par le premier appui : le second confirme. Deux
   *  appuis, parce que fusionner réaffecte des sessions et des prix. */
  @state() private fusionArmee: number | null = null;
  @state() private erreurFusion: string | null = null;
  @state() private recurrentes: Recurrente[] = [];
  @state() private saisieRecurrente = '';
  @state() private saisieJours = '';
  /** Renseignés par le panneau quand il les connaît : l'entité de lecture
   *  des tickets, et le poids du dossier des photos. La photo n'est jamais
   *  supprimée toute seule — elle justifie ce que le modèle en a tiré — donc
   *  les réglages disent au moins ce qu'elle pèse. */
  @property({ attribute: false }) agentTicket: string | null = null;
  @property({ attribute: false }) tailleTickets: string | null = null;

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
      const [rayons, emplacements, magasins, recurrentes] = await Promise.all([
        this.connexion.appeler<{ aisles: Rayon[] }>('home_stock/aisles/list'),
        this.connexion.appeler<{ locations: Emplacement[] }>('home_stock/locations/list'),
        this.connexion.appeler<{ stores: Magasin[] }>('home_stock/stores/list'),
        this.connexion.appeler<{ recurring: Recurrente[] }>('home_stock/recurring/list'),
      ]);
      // `?? []` sur chacune : une réponse qui n'a pas la clé attendue ne
      // doit pas vider un écran entier de réglages. C'est une lecture
      // accessoire, pas une condition d'affichage.
      this.rayons = rayons?.aisles ?? [];
      this.emplacements = emplacements?.locations ?? [];
      this.magasins = magasins?.stores ?? [];
      this.recurrentes = recurrentes?.recurring ?? [];
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

  // --- lot 4 --------------------------------------------------------------

  private async ouvrirMagasin(store: Magasin): Promise<void> {
    this.fusionArmee = null;
    this.erreurFusion = null;
    if (this.magasinOuvert === store.id) {
      this.magasinOuvert = null;
      this.parcours = null;
      return;
    }
    this.magasinOuvert = store.id;
    this.parcours = null;
    if (!this.connexion) return;
    this.parcours = await this.connexion.appeler<ParcoursMagasin>(
      'home_stock/store/aisles', { store_id: store.id });
  }

  /** Déplacer un rayon l'ÉPINGLE : l'apprentissage ne le déplacera plus.
   *  Règle `article.manual_fields` du lot 0, transposée — et c'est bien ce
   *  qu'on veut dire en le déplaçant à la main. */
  private async deplacerRayonMagasin(index: number, sens: -1 | 1): Promise<void> {
    const parcours = this.parcours;
    if (!parcours || !this.connexion) return;
    const nouvel = deplacer(parcours.aisles, index, sens);
    if (nouvel === null) return;
    this.parcours = await this.connexion.appeler<ParcoursMagasin>(
      'home_stock/store/reorder_aisles',
      { store_id: parcours.store_id, aisle_ids: nouvel.map((r) => r.aisle_id) });
  }

  /** « Reprendre l'apprentissage » : la ligne redevient automatique. Une
   *  commande à part, et pas un réordonnancement sans elle — réépingler tous
   *  les autres ne dés-épingle pas celle-ci. */
  private async reprendreApprentissage(aisleId: number): Promise<void> {
    const parcours = this.parcours;
    if (!parcours || !this.connexion) return;
    this.parcours = await this.connexion.appeler<ParcoursMagasin>(
      'home_stock/store/unpin_aisle',
      { store_id: parcours.store_id, aisle_id: aisleId });
  }

  private async fusionner(mergeId: number): Promise<void> {
    const garde = this.magasins.find((m) => m.id !== mergeId);
    if (!garde || !this.connexion) return;
    this.erreurFusion = null;
    try {
      const rendu = await this.connexion.appeler<{ stores: Magasin[] }>(
        'home_stock/store/merge', { keep_id: garde.id, merge_id: mergeId });
      this.magasins = rendu.stores;
    } catch (err) {
      // Le refus est déjà en français côté serveur — « on ne déplace pas le
      // sol sous une session ». Affiché tel quel, à côté du bouton.
      this.erreurFusion = (err as Error)?.message ?? 'Fusion impossible.';
    }
    this.fusionArmee = null;
  }

  private async enregistrerRecurrente(): Promise<void> {
    const texte = this.saisieRecurrente.trim();
    const jours = Number.parseInt(this.saisieJours, 10);
    if (!texte || !Number.isFinite(jours) || !this.connexion) return;
    const rendu = await this.connexion.appeler<{ recurring: Recurrente[] }>(
      'home_stock/recurring/save', { free_text: texte, every_days: jours });
    this.recurrentes = rendu.recurring;
    this.saisieRecurrente = '';
    this.saisieJours = '';
  }

  private async supprimerRecurrente(id: number): Promise<void> {
    if (!this.connexion) return;
    const rendu = await this.connexion.appeler<{ recurring: Recurrente[] }>(
      'home_stock/recurring/delete', { recurring_id: id });
    this.recurrentes = rendu.recurring;
  }

  private rendreMagasins() {
    if (this.magasins.length === 0) return html`<p class="vide">Aucun magasin connu.</p>`;
    return html`
      <ul class="liste-magasins">
        ${this.magasins.map((magasin) => html`
          <li class="magasin">
            <button class="magasin-onglet"
              aria-pressed=${this.magasinOuvert === magasin.id ? 'true' : 'false'}
              @click=${() => { void this.ouvrirMagasin(magasin); }}>
              ${magasin.name}
            </button>
            ${this.magasins.length > 1 ? html`
              ${this.fusionArmee === magasin.id ? html`
                <button class="confirmer-fusion"
                  @click=${() => { void this.fusionner(magasin.id); }}>Confirmer</button>
                <button class="annuler-fusion"
                  @click=${() => { this.fusionArmee = null; }}>Annuler</button>
              ` : html`
                <button class="fusionner"
                  @click=${() => { this.fusionArmee = magasin.id; }}>Fusionner</button>
              `}
            ` : nothing}
            ${this.magasinOuvert === magasin.id ? this.rendreParcours() : nothing}
          </li>
        `)}
      </ul>
      ${this.erreurFusion ? html`<p class="erreur-fusion">${this.erreurFusion}</p>` : nothing}
    `;
  }

  private rendreParcours() {
    const parcours = this.parcours;
    if (!parcours) return html`<p class="vide">Chargement du parcours…</p>`;
    return html`
      <p class="fiabilite">${
        parcours.reliable
          ? `Ordre appris de ce magasin (${parcours.observed_sessions} sessions).`
          : `${parcours.observed_sessions} session${parcours.observed_sessions > 1 ? 's' : ''}`
            + ` sur ${parcours.required_sessions} : l’ordre par défaut est encore utilisé.`
      }</p>
      <ul class="liste-rayons-magasin">
        ${parcours.aisles.map((rayon, index) => html`
          <li class="rayon-magasin ${rayon.source === 'manual' ? 'epingle' : ''}">
            <span class="rayon-magasin-nom">${rayon.aisle_name}</span>
            ${rayon.source === 'manual' ? html`
              <span class="marque-epingle">épinglé</span>
              <button class="reprendre-apprentissage"
                @click=${() => { void this.reprendreApprentissage(rayon.aisle_id); }}>
                Reprendre l’apprentissage
              </button>
            ` : nothing}
            <button class="monter-rayon-magasin" aria-label="Monter ${rayon.aisle_name}"
              ?disabled=${index === 0}
              @click=${() => { void this.deplacerRayonMagasin(index, -1); }}>▲</button>
            <button class="descendre-rayon-magasin" aria-label="Descendre ${rayon.aisle_name}"
              ?disabled=${index === parcours.aisles.length - 1}
              @click=${() => { void this.deplacerRayonMagasin(index, 1); }}>▼</button>
          </li>
        `)}
      </ul>
    `;
  }

  private rendreRecurrentes() {
    return html`
      <ul class="liste-recurrentes">
        ${this.recurrentes.map((ligne) => html`
          <li class="recurrente">
            <span class="recurrente-nom">${ligne.product_name ?? ligne.free_text}</span>
            <span class="recurrente-jours">${`tous les ${ligne.every_days} j`}</span>
            <button class="supprimer-recurrente"
              aria-label=${`Supprimer ${ligne.product_name ?? ligne.free_text}`}
              @click=${() => { void this.supprimerRecurrente(ligne.id); }}>×</button>
          </li>
        `)}
      </ul>
      <div class="ajout-recurrente">
        <input class="champ-recurrente" placeholder="Ce qu’on rachète" .value=${this.saisieRecurrente}
          aria-label="Libellé de la ligne récurrente"
          @input=${(e: InputEvent) => { this.saisieRecurrente = (e.target as HTMLInputElement).value; }} />
        <input class="champ-jours" inputmode="numeric" placeholder="jours" .value=${this.saisieJours}
          aria-label="Tous les combien de jours"
          @input=${(e: InputEvent) => { this.saisieJours = (e.target as HTMLInputElement).value; }} />
        <button class="ajouter-recurrente"
          @click=${() => { void this.enregistrerRecurrente(); }}>Ajouter</button>
      </div>
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
        <h3 class="titre">Magasins et parcours</h3>
        <p class="explication">
          L'ordre appris de chaque magasin. Déplacer un rayon l'épingle : l'apprentissage
          ne le déplacera plus. Fusionner deux enseignes réunit leurs sessions, leurs prix
          et leurs parcours — et ne réécrit jamais ce qui a été observé.
        </p>
        ${this.rendreMagasins()}
      </section>

      <section class="section">
        <h3 class="titre">Achats récurrents</h3>
        <p class="explication">
          Ce qu'on rachète sans que rien ne le réclame : le café, les sacs poubelle.
        </p>
        ${this.rendreRecurrentes()}
      </section>

      <section class="section">
        <h3 class="titre">Tickets de caisse</h3>
        <p class="agent-ticket">${
          this.agentTicket
            ? `Lus par ${this.agentTicket}.`
            : 'Aucune entité de lecture configurée : choisissez-en une dans les options '
              + 'de l’intégration pour photographier vos tickets.'
        }</p>
        <p class="taille-tickets">${
          this.tailleTickets
            ? `Le dossier des photos pèse ${this.tailleTickets}. Les photos ne sont jamais `
              + 'supprimées automatiquement : elles justifient ce qui en a été tiré.'
            : 'Les photos ne sont jamais supprimées automatiquement : elles justifient ce '
              + 'qui en a été tiré.'
        }</p>
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
    .liste-magasins, .liste-rayons-magasin, .liste-recurrentes {
      list-style: none; margin: 0; padding: 0;
    }
    .magasin, .rayon-magasin, .recurrente {
      display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .magasin-onglet, .fusionner, .confirmer-fusion, .annuler-fusion,
    .monter-rayon-magasin, .descendre-rayon-magasin, .reprendre-apprentissage,
    .supprimer-recurrente, .ajouter-recurrente {
      min-height: 48px; min-width: 88px; border-radius: 8px; border: none; font-size: 0.9rem;
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .magasin-onglet[aria-pressed='true'] {
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .magasin-onglet, .rayon-magasin-nom, .recurrente-nom { flex: 1 1 auto; }
    .marque-epingle { font-size: 0.8rem; color: var(--secondary-text-color); }
    .fiabilite { flex-basis: 100%; margin: 4px 0; font-size: 0.85rem; color: var(--secondary-text-color); }
    .erreur-fusion { color: var(--error-color, #b3261e); font-size: 0.9rem; margin: 8px 0 0; }
    .ajout-recurrente { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
    .champ-recurrente { flex: 1 1 140px; min-height: 48px; box-sizing: border-box; padding: 4px 8px; }
    .champ-jours { flex: 0 0 88px; min-height: 48px; box-sizing: border-box; padding: 4px 8px; }
    .agent-ticket, .taille-tickets { margin: 4px 0; color: var(--secondary-text-color); font-size: 0.9rem; }
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
