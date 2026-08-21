import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { Connexion, type Hass } from './connexion';
import { FileAttente } from './file-attente';
import './ecrans/scanner';
import './ecrans/fiche';
import './ecrans/panier';
import './ecrans/session';
import './ecrans/rangement';
import './ecrans/catalogue';
import './ecrans/reglages';
import './ecrans/consommation';
import './ecrans/journal';
import './ecrans/recettes';
import './ecrans/recette';
import './ecrans/validation';
import './ecrans/planning';
import './ecrans/piles';
import './ecrans/equipements';
import './ecrans/liste';
import './ecrans/ticket';
import type { ResumeDerniereFiche } from './ecrans/scanner';
import type { ArticlePret, ResultatLookup, UniteBase } from './ecrans/fiche';
import type { DonneesSession } from './ecrans/panier';
import type { DonneesTicket } from './ecrans/ticket';
import type { LigneRangement, LigneRangementAutonome, LigneRangementSession } from './ecrans/rangement';

export type Ecran = 'scanner' | 'fiche' | 'panier' | 'rangement' | 'session'
  | 'catalogue' | 'reglages' | 'consommation' | 'journal'
  | 'recettes' | 'recette' | 'planning' | 'validation'
  | 'piles' | 'equipements' | 'liste' | 'ticket';

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
  /** Le produit visé par l'écran « manger », posé par la fiche ou le
   *  catalogue via `manger-produit` — `null` tant qu'aucun n'a été désigné,
   *  ce qui est aussi pourquoi ce n'est jamais un bouton de navigation nu :
   *  il n'aurait aucun produit à passer. */
  @state() private produitAManger: number | null = null;

  private connexion?: Connexion;
  private file?: FileAttente;
  private desabonner?: () => void;

  connectedCallback(): void {
    super.connectedCallback();
    window.addEventListener('resize', this.surRedimensionnement);
    // Écoutés sur l'hôte, pas sur chaque enfant : `recette-ouverte` est émis
    // par la liste ET par le planning, et les deux événements remontent
    // (bubbles + composed). Un écouteur ici couvre les deux émetteurs, et
    // rend surtout ces écrans atteignables autrement qu'en câblant chaque
    // parent — c'est ce que fait déjà `manger-produit` au lot 2.
    this.addEventListener('recette-ouverte', this.surRecetteOuverte as EventListener);
    this.addEventListener('valider-repas', this.surValiderRepas as EventListener);
    this.addEventListener('repas-valide', this.surRepasValide as EventListener);
    this.connexion = new Connexion(this.hass);
    this.file = new FileAttente(
      window.localStorage,
      (type, charge) => this.connexion!.appeler(type, charge),
      (_action, message) => { this.erreurFile = message; },
    );
    this.enAttente = this.file.taille();
    // Rejeu générique de ce qui traînait déjà dans le stockage local (une
    // page précédente, une reconnexion) : aucun appelant précis n'attend le
    // sort d'une action en particulier ici — chaque entrée porte désormais
    // sa propre promesse (voir `FileAttente.ajouter`), donc rien à purger.
    void this.file.rejouer().then(() => {
      this.enAttente = this.file!.taille();
    });
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
    // `manger-produit` peut venir de la fiche comme du catalogue — deux
    // écrans différents, jamais montés ensemble — donc écouté ici, sur
    // l'hôte, plutôt que câblé à chaque enfant qui pourrait l'émettre.
    // Écouté sur le panneau lui-même, comme `manger-produit` et
    // `recette-ouverte` : « Ticket » n'est pas une destination de la barre,
    // on y entre depuis la session ou depuis un bandeau, et l'émetteur n'est
    // donc pas toujours un enfant rendu à ce moment-là.
    this.addEventListener('ticket-ouvert', this.surTicketOuvert as EventListener);
    this.addEventListener('aller-liste', this.surAllerListe);
    this.addEventListener('manger-produit', this.surMangerProduit as EventListener);
    this.addEventListener('consommation-enregistree', this.surConsommationEnregistree);
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.desabonner?.();
    this.desabonner = undefined;
    window.removeEventListener('online', this.auRetourDuReseau);
    window.removeEventListener('resize', this.surRedimensionnement);
    this.removeEventListener('recette-ouverte', this.surRecetteOuverte as EventListener);
    this.removeEventListener('valider-repas', this.surValiderRepas as EventListener);
    this.removeEventListener('repas-valide', this.surRepasValide as EventListener);
    this.removeEventListener('manger-produit', this.surMangerProduit as EventListener);
    this.removeEventListener('consommation-enregistree', this.surConsommationEnregistree);
  }

  private auRetourDuReseau = (): void => {
    // Même rejeu générique qu'au démarrage (voir connectedCallback) : ce
    // retour réseau peut faire partir des actions posées par un écran
    // depuis longtemps démonté, personne ne réclamera leur sort — chacune
    // le résout d'elle-même.
    void this.file?.rejouer().then(() => {
      this.enAttente = this.file!.taille();
    });
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
      // Le refus (s'il y en a un) est déjà annoncé par la bannière French
      // via `surRefus` : cet écran-ci n'a besoin de rien de plus, il ne lit
      // pas le `sort` de `ajouter` — inutile de s'y accrocher pour rien.
      this.file!.ajouter('home_stock/session/add_line', {
        article_id: articleId, quantity: quantite, unit_price: prixUnitaire,
      });
      this.enAttente = this.file!.taille();
      void this.file!.rejouer().then(() => {
        this.enAttente = this.file!.taille();
      });
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

  /** L'écran « Courses » vient d'ouvrir ou de clore une session côté
   *  serveur. On relit `session/current` — c'est lui la vérité, pas ce que
   *  le panneau croyait — puis on renvoie au scanner : ouvrir une session
   *  n'a qu'un but, scanner en rayon ; la clore n'en laisse plus aucun. */
  private surSessionChangee = async (): Promise<void> => {
    await this.actualiserSession();
    this.ecran = 'scanner';
  };

  /** La fiche ou le catalogue désignent un produit à manger : on le retient
   *  et on bascule dessus — via `demanderNavigation`, pour que quitter un
   *  rangement en attente prévienne d'abord, comme pour toute autre cible. */
  private surMangerProduit = (evenement: CustomEvent<{ product_id: number }>): void => {
    this.produitAManger = evenement.detail.product_id;
    this.demanderNavigation('consommation');
  };

  /** La déclaration est enregistrée (ou en file, hors ligne) : l'écran
   *  « manger » l'a déjà dit lui-même, il ne reste qu'à revenir au scanner —
   *  comme l'ajout au panier depuis la fiche. */
  private surConsommationEnregistree = (): void => {
    this.produitAManger = null;
    this.ecran = 'scanner';
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
  /** La recette ouverte en vue cuisine, et le repas en cours de validation.
   *  Retenus ici parce que `recette` et `validation` n'ont pas de bouton de
   *  navigation : on y entre depuis une liste ou depuis le planning, comme
   *  `fiche` et `consommation` au lot 2. */
  /** La largeur RÉELLEMENT mesurée : `window.innerWidth >= 1000`, relevée à
   *  chaque `resize`. Mesurée, jamais déduite d'un agent utilisateur — c'est
   *  aussi ce qui la rend vraie hors du panneau Home Assistant, dans le
   *  harnais du vérificateur de rendu, qui ne fournit aucun `narrow`. */
  @state() private largeMesuree = typeof window !== 'undefined' && window.innerWidth >= 1000;

  /** Vrai au-delà de 1000 px de large — sauf si l'hôte affirme être étroit.
   *
   *  Home Assistant fournit `narrow` au panneau depuis toujours et ne s'en
   *  était jamais servi : la barre latérale dépliée sur une tablette large
   *  laisse au panneau bien moins que `innerWidth`, et une mise en page dense
   *  écrasée dans 400 px est pire que la mise en page étroite qu'elle
   *  remplace. L'hôte gagne donc contre la mesure, jamais l'inverse. */
  get large(): boolean {
    return this.largeMesuree && !this.narrow;
  }

  private surRedimensionnement = () => {
    this.largeMesuree = window.innerWidth >= 1000;
  };

  /** Le ticket ouvert, et si une entité de lecture est réglée. « Ticket » ne
   *  s'atteint pas par un bouton nu : on y entre depuis la session ou depuis
   *  le bandeau d'un ticket en attente, comme `recette` et `validation` au
   *  lot 3. */
  @state() ticketOuvert: DonneesTicket | null = null;
  @state() agentTicketConfigure = true;

  private surAllerListe = (): void => {
    this.demanderNavigation('liste');
  };

  private surTicketOuvert = (e: CustomEvent<{ ticket: DonneesTicket | null;
                                              agent_configure?: boolean }>): void => {
    this.ticketOuvert = e.detail.ticket;
    this.agentTicketConfigure = e.detail.agent_configure ?? true;
    this.demanderNavigation('ticket');
  };

  @state() recetteOuverte: number | null = null;
  @state() repasDeLaRecette: number | null = null;
  @state() repasAValider: number | null = null;

  private surRecetteOuverte = (e: CustomEvent) => {
    this.recetteOuverte = e.detail.recipe_id;
    this.repasDeLaRecette = e.detail.meal_id ?? null;
    this.demanderNavigation('recette');
  };

  private surValiderRepas = (e: CustomEvent) => {
    this.repasAValider = e.detail.meal_id;
    this.demanderNavigation('validation');
  };

  private surRepasValide = () => {
    this.repasAValider = null;
    this.demanderNavigation('planning');
  };

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
        ${this.ecran !== 'session' ? html`
          <button class="nav-bouton" @click=${() => this.demanderNavigation('session')}>
            Courses
          </button>
        ` : nothing}
        ${this.ecran !== 'catalogue' ? html`
          <button class="nav-bouton" @click=${() => this.demanderNavigation('catalogue')}>Catalogue</button>
        ` : nothing}
        ${this.ecran !== 'journal' ? html`
          <button class="nav-bouton" @click=${() => this.demanderNavigation('journal')}>Journal</button>
        ` : nothing}
        ${this.ecran !== 'piles' ? html`
          <button class="nav-bouton" @click=${() => this.demanderNavigation('piles')}>Piles</button>
        ` : nothing}
        ${this.ecran !== 'equipements' ? html`
          <button class="nav-bouton" @click=${() => this.demanderNavigation('equipements')}>
            Équipements
          </button>
        ` : nothing}
        ${this.ecran !== 'liste' ? html`
          <button class="nav-bouton" @click=${() => this.demanderNavigation('liste')}>Liste</button>
        ` : nothing}
        ${this.ecran !== 'reglages' ? html`
          <button class="nav-bouton" @click=${() => this.demanderNavigation('recettes')}>Recettes</button>
          <button class="nav-bouton" @click=${() => this.demanderNavigation('planning')}>Planning</button>
          <button class="nav-bouton" @click=${() => this.demanderNavigation('reglages')}>Réglages</button>
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
    /* flex-wrap : jusqu'à six boutons cohabitent ici (Scanner, Panier,
       Ranger, Courses, Catalogue, Réglages). Sur 412 px de large ils ne
       tiennent pas tous sur une ligne, et un dépassement horizontal fait
       échouer le vérificateur de rendu — à juste titre. Ils passent donc à
       la ligne plutôt que de rétrécir sous la cible de 48 px ou de tronquer
       leur libellé. */
    .navigation { display: flex; flex-wrap: wrap; gap: 8px; padding: 8px 12px 0; }
    .nav-bouton {
      flex: 1 1 auto; min-height: 48px; min-width: 88px; border-radius: 8px; border: none; font-size: 0.95rem;
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
    if (this.ecran === 'session') {
      return html`
        <home-stock-session .donnees=${this.session} .connexion=${this.connexion}
          .file=${this.file} .enAttente=${this.enAttente}
          @session-changee=${this.surSessionChangee} @file-changee=${this.surFileChangee}
          >
        </home-stock-session>`;
    }
    if (this.ecran === 'catalogue') {
      return html`
        <home-stock-catalogue .connexion=${this.connexion} .file=${this.file} .enAttente=${this.enAttente}
          .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-catalogue>`;
    }
    if (this.ecran === 'reglages') {
      return html`
        <home-stock-reglages .connexion=${this.connexion} .file=${this.file} .enAttente=${this.enAttente}
          .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-reglages>`;
    }
    if (this.ecran === 'consommation') {
      return html`
        <home-stock-consommation .connexion=${this.connexion} .file=${this.file}
          .productId=${this.produitAManger}>
        </home-stock-consommation>`;
    }
    if (this.ecran === 'journal') {
      return html`
        <home-stock-journal .connexion=${this.connexion} .file=${this.file}
          .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-journal>`;
    }
    if (this.ecran === 'recettes') {
      return html`
        <home-stock-recettes .connexion=${this.connexion} .file=${this.file}
          .enAttente=${this.enAttente} @file-changee=${this.surFileChangee}>
        </home-stock-recettes>`;
    }
    if (this.ecran === 'recette' && this.recetteOuverte !== null) {
      return html`
        <home-stock-recette .connexion=${this.connexion} .file=${this.file}
          .recipeId=${this.recetteOuverte} .mealId=${this.repasDeLaRecette}
          @recette-fermee=${() => this.demanderNavigation('recettes')}>
        </home-stock-recette>`;
    }
    if (this.ecran === 'validation' && this.repasAValider !== null) {
      return html`
        <home-stock-validation .connexion=${this.connexion} .file=${this.file}
          .mealId=${this.repasAValider} @file-changee=${this.surFileChangee}>
        </home-stock-validation>`;
    }
    if (this.ecran === 'planning') {
      return html`
        <home-stock-planning .connexion=${this.connexion} .file=${this.file}
          .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-planning>`;
    }
    if (this.ecran === 'piles') {
      return html`
        <home-stock-piles .connexion=${this.connexion} .file=${this.file}
          .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-piles>`;
    }
    if (this.ecran === 'equipements') {
      return html`
        <home-stock-equipements .connexion=${this.connexion} .file=${this.file}
          .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-equipements>`;
    }
    if (this.ecran === 'liste') {
      return html`
        <home-stock-liste .connexion=${this.connexion} .file=${this.file}
          .enAttente=${this.enAttente} .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-liste>`;
    }
    if (this.ecran === 'ticket') {
      return html`
        <home-stock-ticket .connexion=${this.connexion} .file=${this.file}
          .enAttente=${this.enAttente} .ticket=${this.ticketOuvert}
          .agentConfigure=${this.agentTicketConfigure} .large=${this.large}
          @file-changee=${this.surFileChangee}>
        </home-stock-ticket>`;
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
