import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { Connexion, type Hass } from './connexion';
import { FileAttente } from './file-attente';
import './ecrans/scanner';
import './ecrans/fiche';
import './ecrans/panier';
import './ecrans/rangement';
import type { ResumeDerniereFiche } from './ecrans/scanner';
import type { ArticlePret, ResultatLookup, UniteBase } from './ecrans/fiche';
import type { DonneesSession } from './ecrans/panier';
import type { LigneRangement, LigneRangementAutonome, LigneRangementSession } from './ecrans/rangement';

export type Ecran = 'scanner' | 'fiche' | 'panier' | 'rangement' | 'catalogue' | 'reglages';

/** Ce que la bannière et la dernière-fiche affichent : un résumé, pas la
 *  réponse brute de `lookup`. */
function resumeDe(resultat: ResultatLookup | null, statut: string, ignores: string[] = []): ResumeDerniereFiche | null {
  if (!resultat) return null;
  const nom = resultat.off?.label ?? resultat.article?.label ?? resultat.product?.name ?? resultat.code;
  const marque = resultat.off?.brand ?? resultat.article?.brand ?? null;
  const image = resultat.off?.image ?? resultat.article?.image ?? null;
  return { nom, marque, image, statut, ignores };
}

/** Un article rapporté seul, hors session : la fiche vient de le créer (ou
 *  de le retrouver) mais aucune ligne serveur n'existe pour lui — c'est le
 *  panneau qui le fabrique, à partir du dernier résultat de `lookup` encore
 *  en main, pour que l'écran de rangement ait un emplacement et une DLC
 *  suggérés comme pour n'importe quelle autre ligne. */
function ligneAutonomeDepuis(resultat: ResultatLookup | null, articleId: number, quantite: number,
                              prixUnitaire: number | null): LigneRangementAutonome {
  return {
    source: 'autonome',
    id: `autonome-${crypto.randomUUID()}`,
    article_id: articleId,
    quantity: quantite,
    unit_price: prixUnitaire,
    product_name: resultat?.product?.name ?? resultat?.off?.label ?? resultat?.article?.label
      ?? resultat?.off?.generic_name ?? 'Article',
    base_unit: (resultat?.product?.base_unit as UniteBase | undefined) ?? 'piece',
    default_location_id: resultat?.product?.default_location_id ?? null,
    default_shelf_life_days: resultat?.product?.default_shelf_life_days ?? null,
    brand: resultat?.off?.brand ?? resultat?.article?.brand ?? null,
    image: resultat?.off?.image ?? resultat?.article?.image ?? null,
    net_quantity: resultat?.article?.net_quantity ?? resultat?.off?.net_quantity ?? null,
  };
}

@customElement('home-stock-panel')
export class PanneauGardeManger extends LitElement {
  @property({ attribute: false }) hass!: Hass;
  @property({ attribute: false }) narrow = false;
  @state() ecran: Ecran = 'scanner';
  @state() enAttente = 0;
  @state() private session: DonneesSession | null = null;
  @state() private resultatCourant: ResultatLookup | null = null;
  @state() private derniereFiche: ResumeDerniereFiche | null = null;
  /** Articles rapportés seuls, hors session, encore à ranger : rien côté
   *  serveur ne les représente tant qu'ils n'ont pas de lot, donc le panneau
   *  les garde le temps que l'écran de rangement les traite. */
  @state() private enAttenteRangement: LigneRangementAutonome[] = [];
  /** Le dernier refus du serveur sur une écriture en file, en français
   *  (c'est déjà le message du serveur) — jusqu'à ce qu'on l'accuse
   *  réception ou qu'un nouveau refus le remplace. */
  @state() private erreurFile: string | null = null;
  /** La cible de navigation en attente de confirmation, quand on quitte le
   *  rangement avec des articles autonomes encore en attente — `null` tant
   *  qu'aucun départ n'est armé (voir `demanderNavigation`). */
  @state() private navigationArmee: Ecran | null = null;

  private connexion?: Connexion;
  private file?: FileAttente;
  private desabonner?: () => void;

  connectedCallback(): void {
    super.connectedCallback();
    this.connexion = new Connexion(this.hass);
    this.file = new FileAttente(
      window.localStorage,
      (type, charge) => this.connexion!.appeler(type, charge),
      (_action, message) => { this.erreurFile = message; },
    );
    this.enAttente = this.file.taille();
    void this.file.rejouer().then(() => { this.enAttente = this.file!.taille(); });
    void this.actualiserSession();
    void this.connexion.abonner(() => {
      // Le panier peut se vider (checkout) ou s'ouvrir depuis un autre
      // appareil pendant qu'on range : la bannière doit suivre.
      void this.actualiserSession();
      this.requestUpdate();
    }).then((desabonner) => {
      // L'élément a pu quitter le DOM pendant que l'abonnement était en vol :
      // disconnectedCallback s'est déjà exécuté et ne sera pas rappelé, donc
      // stocker la fonction ici la laisserait fuiter pour toujours. On s'en
      // sert tout de suite à la place de la garder.
      if (this.isConnected) {
        this.desabonner = desabonner;
      } else {
        desabonner();
      }
    });
    window.addEventListener('online', this.auRetourDuReseau);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.desabonner?.();
    this.desabonner = undefined;
    window.removeEventListener('online', this.auRetourDuReseau);
  }

  private auRetourDuReseau = (): void => {
    void this.file?.rejouer().then(() => { this.enAttente = this.file!.taille(); });
  };

  /** `session/current` répond `null`, ou l'enveloppe complète
   *  `{session, lines, totals, stores}` — jamais juste `{store}` : c'est
   *  cette enveloppe entière que le panier et le rangement lisent. */
  private async actualiserSession(): Promise<void> {
    try {
      this.session = await this.connexion!.appeler<DonneesSession | null>('home_stock/session/current');
    } catch {
      // Hors ligne : on garde la dernière bannière connue plutôt que d'en
      // afficher une fausse.
    }
  }

  /** Un code lu (scanner ou clavier) devient une fiche : c'est la commande
   *  home_stock/lookup, jamais une écriture. */
  private surCodeLu = async (evenement: CustomEvent<{ code: string }>): Promise<void> => {
    try {
      const resultat = await this.connexion!.appeler<ResultatLookup>(
        'home_stock/lookup', { code: evenement.detail.code });
      this.resultatCourant = resultat;
      this.ecran = 'fiche';
    } catch {
      this.derniereFiche = {
        nom: evenement.detail.code, marque: null, image: null,
        statut: 'Connexion indisponible — réessayez.',
      };
    }
  };

  /** La fiche a résolu l'article (créé au besoin) et dit ce qu'elle veut en
   *  faire. En session (courses en cours), ajouter au panier ne demande rien
   *  de plus : c'est la file hors-ligne qui l'envoie — c'est tout le sens de
   *  son existence, le rayon d'un magasin est précisément l'endroit où le
   *  réseau lâche. Hors session, l'article vient d'être rapporté seul :
   *  choisir l'emplacement et la DLC revient à l'écran « rangement », vers
   *  lequel on route directement plutôt que de laisser la valeur sur la
   *  bannière du scanner. */
  private surArticlePret = (evenement: CustomEvent<ArticlePret>): void => {
    const { articleId, quantite, prixUnitaire, mode, offDroppedFields } = evenement.detail;
    if (mode === 'panier') {
      this.file!.ajouter('home_stock/session/add_line', {
        article_id: articleId, quantity: quantite, unit_price: prixUnitaire,
      });
      this.enAttente = this.file!.taille();
      void this.file!.rejouer().then(() => { this.enAttente = this.file!.taille(); });
      this.derniereFiche = resumeDe(this.resultatCourant, 'Ajouté au panier.', offDroppedFields);
      this.resultatCourant = null;
      this.ecran = 'scanner';
      return;
    }
    const ligne = ligneAutonomeDepuis(this.resultatCourant, articleId, quantite, prixUnitaire);
    this.enAttenteRangement = [...this.enAttenteRangement, ligne];
    this.resultatCourant = null;
    this.ecran = 'rangement';
  };

  private surLigneAutonomeRangee = (evenement: CustomEvent<{ id: string }>): void => {
    this.enAttenteRangement = this.enAttenteRangement.filter((l) => l.id !== evenement.detail.id);
  };

  private surRangementTermine = (): void => {
    // La liste s'est vidée d'elle-même (tout a été rangé) : rien à confirmer,
    // mais un départ resté armé d'un geste précédent ne doit pas survivre à
    // un écran qui n'existe plus.
    this.navigationArmee = null;
    this.ecran = 'scanner';
  };

  /** Le panier et le rangement écrivent directement dans la file (chacun
   *  leurs propres actions : quantité, prix, suppression, checkout,
   *  store_line…) : c'est ce signal qui tient le compteur affiché à jour,
   *  plutôt qu'un panneau qui devrait connaître le détail de leurs écritures. */
  private surFileChangee = (): void => {
    this.enAttente = this.file!.taille();
  };

  /** Les lignes de la session encore à ranger — vide tant qu'aucune session
   *  n'est en `to_store` (rien à ranger tant qu'on n'est pas passé en
   *  caisse). */
  private get lignesSessionARanger(): LigneRangementSession[] {
    if (!this.session?.session || this.session.session.state !== 'to_store') return [];
    return this.session.lines
      .filter((l) => l.stored_at === null)
      .map((l) => ({ ...l, source: 'session' as const }));
  }

  private get lignesARanger(): LigneRangement[] {
    return [...this.lignesSessionARanger, ...this.enAttenteRangement];
  }

  /** Change d'écran, sauf s'il faut d'abord prévenir : quitter le rangement
   *  alors que des articles autonomes attendent encore les perd pour de bon
   *  — rien côté serveur ne les représente tant qu'ils n'ont pas de lot,
   *  contrairement aux lignes de session qui, elles, survivent dans
   *  `to_store`. Pas de `window.confirm` : ni ses cibles tactiles ni son
   *  contraste ne sont sous notre main, il bloque le fil, ses libellés
   *  suivent la langue du navigateur plutôt que le français de l'appli, et
   *  là où les popups système sont coupées — Fully Kiosk le permet, jsdom
   *  répond « Not implemented » — il rend `undefined`, donc refuse
   *  silencieusement de naviguer plutôt que d'avertir. Même geste à deux
   *  appuis que la suppression d'une ligne : armer, puis confirmer ou
   *  annuler, en boutons, dans l'écran. */
  private demanderNavigation(cible: Ecran): void {
    if (this.ecran === 'rangement' && cible !== 'rangement' && this.enAttenteRangement.length > 0) {
      this.navigationArmee = cible;
      return;
    }
    this.ecran = cible;
  }

  private confirmerNavigation(): void {
    const cible = this.navigationArmee;
    this.navigationArmee = null;
    if (cible) this.ecran = cible;
  }

  private annulerNavigation(): void {
    this.navigationArmee = null;
  }

  private rendreNavigation() {
    if (this.ecran === 'fiche') return nothing;
    if (this.navigationArmee) {
      return html`
        <div class="confirmation-quitter-rangement">
          <p>
            Des articles rapportés seuls n’ont pas encore été rangés : ils seront perdus si vous quittez
            maintenant.
          </p>
          <button class="confirmer-quitter" @click=${this.confirmerNavigation}>Quitter quand même</button>
          <button class="annuler-quitter" @click=${this.annulerNavigation}>Rester ici</button>
        </div>
      `;
    }
    const enCourses = this.session?.session?.state === 'shopping';
    const lignesRangement = this.lignesARanger;
    return html`
      <nav class="navigation">
        ${this.ecran !== 'scanner' ? html`
          <button class="nav-bouton" @click=${() => this.demanderNavigation('scanner')}>Scanner</button>
        ` : nothing}
        ${enCourses && this.ecran !== 'panier' ? html`
          <button class="nav-bouton" @click=${() => this.demanderNavigation('panier')}>
            Panier${this.session!.totals.lines ? ` (${this.session!.totals.lines})` : ''}
          </button>
        ` : nothing}
        ${lignesRangement.length > 0 && this.ecran !== 'rangement' ? html`
          <button class="nav-bouton" @click=${() => this.demanderNavigation('rangement')}>
            Ranger (${lignesRangement.length})
          </button>
        ` : nothing}
      </nav>
    `;
  }

  private rendreErreurFile() {
    if (!this.erreurFile) return nothing;
    return html`
      <p class="erreur-file">
        ${this.erreurFile}
        <button class="fermer-erreur-file" @click=${() => { this.erreurFile = null; }}>OK</button>
      </p>
    `;
  }

  static styles = css`
    :host { display: block; height: 100%; background: var(--primary-background-color); }
    .navigation { display: flex; gap: 8px; padding: 8px 12px 0; }
    .nav-bouton {
      flex: 1; min-height: 48px; border-radius: 8px; border: none; font-size: 0.95rem;
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .erreur-file {
      display: flex; align-items: center; justify-content: space-between; gap: 8px;
      margin: 8px 12px 0; padding: 8px 12px; border-radius: 8px;
      background: var(--error-color, #b3261e); color: #fff; font-size: 0.9rem;
    }
    .fermer-erreur-file {
      min-height: 48px; min-width: 48px; border-radius: 8px; border: none;
      background: rgba(255, 255, 255, 0.2); color: #fff; font-weight: 600;
    }
    .confirmation-quitter-rangement {
      display: flex; flex-direction: column; gap: 8px; padding: 12px;
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .confirmation-quitter-rangement p { margin: 0; }
    .confirmer-quitter, .annuler-quitter {
      min-height: 48px; width: 100%; border-radius: 8px; border: none; font-size: 0.95rem;
    }
    .confirmer-quitter { background: var(--error-color, #b3261e); color: #fff; }
    .annuler-quitter { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  `;

  private rendreEcran() {
    if (this.ecran === 'fiche' && this.resultatCourant) {
      return html`
        <home-stock-fiche .resultat=${this.resultatCourant}
          .mode=${this.session?.session?.state === 'shopping' ? 'panier' : 'rangement'}
          .connexion=${this.connexion} .file=${this.file} @article-pret=${this.surArticlePret}>
        </home-stock-fiche>`;
    }
    if (this.ecran === 'panier' && this.session) {
      return html`
        <home-stock-panier .donnees=${this.session} .connexion=${this.connexion}
          .file=${this.file} .enAttente=${this.enAttente} @file-changee=${this.surFileChangee}>
        </home-stock-panier>`;
    }
    if (this.ecran === 'rangement') {
      return html`
        <home-stock-rangement .lignes=${this.lignesARanger} .connexion=${this.connexion} .file=${this.file}
          .enAttente=${this.enAttente}
          @ligne-autonome-rangee=${this.surLigneAutonomeRangee} @termine=${this.surRangementTermine}
          @file-changee=${this.surFileChangee}>
        </home-stock-rangement>`;
    }
    return html`
      <home-stock-scanner .session=${this.session?.session ? { store: this.session.session.store } : null}
        .derniereFiche=${this.derniereFiche} .enAttente=${this.enAttente} @code-lu=${this.surCodeLu}>
      </home-stock-scanner>`;
  }

  render() {
    return html`${this.rendreNavigation()}${this.rendreErreurFile()}${this.rendreEcran()}`;
  }
}
