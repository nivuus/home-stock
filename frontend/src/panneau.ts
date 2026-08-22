import { LitElement, html, css, nothing, type PropertyValues } from 'lit';
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
import './shell/nav-bar';
import './shell/header';
import { primeHaComponents } from './shell/ui/ha-available';
import { appliquerCouleursDeTexte } from './shell/ui/on-color';
import { tokens } from './shell/ui/tokens';
import { FAMILIES, destinationOf, familyOf, type FamilyId } from './shell/destinations';
import { DEFAULT_SCREEN, parsePath, pathOf } from './shell/router';
import type { IconName } from './shell/ui/icons';

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
  /** Posée par `ha-panel-custom` : `{prefix: '/home-stock', path: '/list'}`.
   *  C'est aussi par elle que revient le bouton Retour du navigateur — HA
   *  écoute `popstate` et nous repasse la route, donc rien à écouter ici. */
  @property({ attribute: false }) route?: { prefix: string; path: string };
  @state() ecran: Ecran = 'scanner';
  @state() enAttente = 0;
  @state() private session: DonneesSession | null = null;
  @state() private resultatCourant: ResultatLookup | null = null;
  @state() private derniereFiche: ResumeDerniereFiche | null = null;
  /** Articles rapportés seuls, hors session, encore à ranger : rien côté
   *  serveur ne les représente tant qu'ils n'ont pas de lot, donc le panneau
   *  les garde le temps que l'écran de rangement les traite. */
  @state() private enAttenteRangement: LigneRangementAutonome[] = [];
  /** Le dernier refus du serveur, en français — jusqu'à ce qu'on l'accuse
   *  réception ou qu'un nouveau le remplace. Deux sources depuis le lot 7 :
   *  une ÉCRITURE en file refusée (c'est alors déjà le message du serveur),
   *  et une LECTURE que la route a demandée et qui n'a rien rendu (un
   *  `/receipt/<id>` introuvable — voir `chargerTicket`). Le nom garde son
   *  histoire ; la bannière, elle, n'est plus réservée à la file. */
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

  /** Le dernier `path` déjà appliqué : sans lui, chaque rendu rejouerait la
   *  route et écraserait une navigation faite entre-temps par un événement
   *  métier (`recette-ouverte`, par exemple). Home Assistant repasse un
   *  OBJET `route` neuf à chaque fois qu'il redessine le panneau, même quand
   *  l'URL n'a pas bougé : sans cette comparaison sur la valeur, un simple
   *  changement de thème ramènerait l'utilisateur à l'écran de son URL. */
  private dernierChemin: string | null = null;

  willUpdate(changees: PropertyValues): void {
    if (!changees.has('route')) return;
    const chemin = this.route?.path ?? '';
    if (chemin === this.dernierChemin) return;
    this.dernierChemin = chemin;
    this.appliquerChemin(chemin);
  }

  /** Traduit un chemin en état — LE seul endroit qui le sache, et le seul qui
   *  applique le paramètre d'un écran paramétré.
   *
   *  `avecGardeFou` n'est faux qu'au rejeu d'un départ confirmé : le garde-fou
   *  vient précisément d'être levé par le second appui, le rejouer réarmerait
   *  la même confirmation en boucle. */
  private appliquerChemin(chemin: string, avecGardeFou = true): void {
    const route = parsePath(chemin);
    // Une route inconnue vaut la racine — mais elle la vaut EN PASSANT PAR LE
    // MÊME GARDE-FOU : c'était le second contournement, aussi silencieux que
    // le premier.
    const cible: Ecran = route ? route.screen : DEFAULT_SCREEN;
    if (avecGardeFou && this.departARisque(cible)) {
      // On retient le CHEMIN, pas la cible : lui seul porte le paramètre, et
      // le rejouer tel quel évite d'avoir un second endroit qui sait traduire
      // un chemin en état. Sans ça, confirmer un départ vers `/item/<code>`
      // posait l'écran sans jamais faire le `lookup`.
      this.armer(cible, null, chemin);
      // L'URL vient de bouger sous nos pieds (bouton Retour du navigateur,
      // geste système d'Android, URL tapée) et l'écran, lui, ne bouge pas :
      // on repose donc celle du rangement, pour qu'écran et URL ne divergent
      // jamais. `replace`, pas `push` — un départ refusé ne mérite aucune
      // entrée d'historique.
      //
      // PAS DE BOUCLE, et le mérite n'en revient PAS à `dernierChemin` : le
      // chemin qu'on repose est celui du rangement, donc l'écho que Home
      // Assistant nous renverra reparse vers `rangement` — la cible EST
      // l'écran courant, `departARisque` y est faux, il n'y a rien à
      // réarmer. Ce verrou-là tient même si HA nous rend le chemin sous une
      // autre forme (`/put-away/`, un segment de trop) ; `dernierChemin`,
      // lui, ne ferait qu'épargner un rendu. Le test
      // « un écho de route qui désigne le rangement autrement » vise
      // précisément ce verrou-ci, en défaisant l'égalité de chemins.
      this.naviguerVers('rangement', null, true);
      return;
    }
    if (!route) {
      // `replace` : une route inconnue ne mérite pas une entrée d'historique
      // dans laquelle le bouton Retour viendrait retomber.
      this.naviguerVers(DEFAULT_SCREEN, null, true);
      return;
    }
    this.ecran = route.screen;
    this.appliquerParametre(route.screen, route.param);
  }

  /** Chaque écran paramétré range son paramètre là où son composant le lit.
   *  Appelé PAR LA ROUTE seulement : les événements métier
   *  (`recette-ouverte`, `ticket-ouvert`…) posent déjà la donnée eux-mêmes,
   *  et bien mieux que ce qu'un segment d'URL peut en dire — un ticket
   *  arrive en objet complet, un identifiant demande un aller-retour. */
  private appliquerParametre(ecran: Ecran, param: string | null): void {
    if (param === null) return;
    if (ecran === 'recette') this.recetteOuverte = Number(param);
    else if (ecran === 'validation') this.repasAValider = Number(param);
    else if (ecran === 'consommation') this.produitAManger = Number(param);
    else if (ecran === 'ticket') void this.chargerTicket(Number(param));
    else if (ecran === 'fiche') void this.chargerFiche(param, false);
  }

  /** `/receipt/12` ne désigne qu'un identifiant : la session, elle, nous
   *  passe le ticket entier. Il faut donc aller le chercher — `ticketOuvert`
   *  est un objet, pas un numéro. */
  private async chargerTicket(id: number): Promise<void> {
    // `agentConfigure` dit si une entité `ai_task` est réglée, ce qui concerne
    // la PHOTO d'un ticket, pas la lecture d'un ticket déjà pris — et aucune
    // route ne le sait, `receipt/get` ne le rend pas. On le repose donc à son
    // défaut : hériter du `false` d'un `ticket-ouvert` précédent cacherait,
    // derrière « aucune entité de lecture n'est configurée », un ticket qui se
    // charge parfaitement.
    this.agentTicketConfigure = true;
    this.ticketOuvert = null;
    try {
      this.ticketOuvert = await this.connexion!.appeler<DonneesTicket>(
        'home_stock/receipt/get', { receipt_id: id });
    } catch {
      // Surtout pas un `catch` muet : l'écran resterait vide sans dire
      // pourquoi, et ce lot passe son temps à débusquer des pannes muettes.
      // On le dit par la bannière de l'en-tête, le canal qui existe déjà pour
      // ça — plutôt qu'en reposant l'écran précédent, qui déplacerait
      // l'utilisateur sans expliquer ce qui a échoué juste après qu'il a
      // délibérément demandé CE ticket.
      this.erreurFile = `Ticket n° ${id} introuvable ou injoignable.`;
    }
  }

  connectedCallback(): void {
    super.connectedCallback();
    // Une seule tentative, au montage du panneau : si Home Assistant sait
    // charger son chunk Lovelace, les enveloppes rendront `<ha-card>` plutôt
    // que leur repli. Sinon (tablette cuisine, ouverture directe), le repli
    // est correct et rien n'échoue.
    primeHaComponents();
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
    await this.chargerFiche(evenement.detail.code);
  };

  /** Le `lookup` et l'écran qui va avec. Séparé de l'écouteur parce que la
   *  route `/item/<code>` l'appelle aussi — mais elle, sans repousser une
   *  entrée d'historique pour l'écran où l'on vient déjà d'arriver. */
  private async chargerFiche(code: string, naviguer = true): Promise<void> {
    try {
      const resultat = await this.connexion!.appeler<ResultatLookup>(
        'home_stock/lookup', { code });
      this.resultatCourant = resultat;
      if (naviguer) this.naviguerVers('fiche', code);
      else this.ecran = 'fiche';
    } catch {
      this.derniereFiche = {
        nom: code, marque: null, image: null,
        statut: 'Connexion indisponible — réessayez.',
      };
      // Un `/item/<code>` que le serveur ne sait pas résoudre n'a rien à
      // montrer : on retombe sur le scanner, où le message ci-dessus
      // s'affiche — en `replace`, pour ne pas piéger le bouton Retour.
      if (!naviguer) this.naviguerVers('scanner', null, true);
    }
  }

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
      this.naviguerVers('scanner');
      return;
    }
    const ligne = ligneAutonomeDepuis(this.resultatCourant, articleId, quantite, prixUnitaire);
    this.enAttenteRangement = [...this.enAttenteRangement, ligne];
    this.resultatCourant = null;
    this.naviguerVers('rangement');
  };

  /** L'écran « Courses » vient d'ouvrir ou de clore une session côté
   *  serveur. On relit `session/current` — c'est lui la vérité, pas ce que
   *  le panneau croyait — puis on renvoie au scanner : ouvrir une session
   *  n'a qu'un but, scanner en rayon ; la clore n'en laisse plus aucun. */
  private surSessionChangee = async (): Promise<void> => {
    await this.actualiserSession();
    this.naviguerVers('scanner');
  };

  /** La fiche ou le catalogue désignent un produit à manger : on le retient
   *  et on bascule dessus — via `demanderNavigation`, pour que quitter un
   *  rangement en attente prévienne d'abord, comme pour toute autre cible. */
  private surMangerProduit = (evenement: CustomEvent<{ product_id: number }>): void => {
    this.produitAManger = evenement.detail.product_id;
    this.demanderNavigation('consommation', evenement.detail.product_id);
  };

  /** La déclaration est enregistrée (ou en file, hors ligne) : l'écran
   *  « manger » l'a déjà dit lui-même, il ne reste qu'à revenir au scanner —
   *  comme l'ajout au panier depuis la fiche. */
  private surConsommationEnregistree = (): void => {
    this.produitAManger = null;
    this.naviguerVers('scanner');
  };

  private surLigneAutonomeRangee = (evenement: CustomEvent<{ id: string }>): void => {
    this.enAttenteRangement = this.enAttenteRangement.filter((l) => l.id !== evenement.detail.id);
  };

  private surRangementTermine = (): void => {
    // La liste s'est vidée d'elle-même (tout a été rangé) : rien à confirmer,
    // mais un départ resté armé d'un geste précédent ne doit pas survivre à
    // un écran qui n'existe plus.
    this.navigationArmee = null;
    this.naviguerVers('scanner');
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
    // `null` quand on vient photographier un ticket qui n'existe pas encore :
    // aucun `/receipt/<id>` ne le désigne alors, et `cheminDe` le sait.
    this.demanderNavigation('ticket', e.detail.ticket?.id ?? null);
  };

  @state() recetteOuverte: number | null = null;
  @state() repasDeLaRecette: number | null = null;
  @state() repasAValider: number | null = null;

  private surRecetteOuverte = (e: CustomEvent) => {
    this.recetteOuverte = e.detail.recipe_id;
    this.repasDeLaRecette = e.detail.meal_id ?? null;
    this.demanderNavigation('recette', e.detail.recipe_id);
  };

  private surValiderRepas = (e: CustomEvent) => {
    this.repasAValider = e.detail.meal_id;
    this.demanderNavigation('validation', e.detail.meal_id);
  };

  private surRepasValide = () => {
    this.repasAValider = null;
    this.demanderNavigation('planning');
  };

  /** Le paramètre de la cible armée, retenu avec elle : sans lui,
   *  confirmer « Quitter quand même » vers `/recipe/12` produirait un chemin
   *  sans identifiant, que `pathOf` refuse. */
  private parametreArme: string | number | null = null;

  /** Le chemin d'URL qui a armé le départ, quand c'est une route qui l'a fait
   *  — `null` pour un geste de l'application. Voir `armer`. */
  private cheminArme: string | null = null;

  /** Change d'écran, sauf s'il faut d'abord prévenir (voir plus haut). Le
   *  garde-fou s'arme AVANT toute navigation : ni l'URL, ni l'historique, ni
   *  `ecran` ne bougent tant que le second appui n'est pas venu. */
  /** Vrai quand quitter l'écran courant pour cette cible-là perdrait des
   *  articles rapportés seuls. Partagé par les DEUX portes d'entrée de la
   *  navigation — les gestes de l'application et les routes d'URL — parce
   *  qu'un garde-fou posé sur une seule des deux n'en est pas un. */
  private departARisque(cible: Ecran): boolean {
    return this.ecran === 'rangement' && cible !== 'rangement'
      && this.enAttenteRangement.length > 0;
  }

  /** `chemin` n'est renseigné que pour un départ armé par une ROUTE : c'est
   *  lui qu'on rejouera, parce qu'une route n'a que son chemin pour dire ce
   *  qu'elle veut. Un geste de l'application, lui, a déjà posé sa donnée
   *  (`recetteOuverte`, `ticketOuvert`…) avant d'armer. */
  private armer(cible: Ecran, param: string | number | null,
                chemin: string | null = null): void {
    this.navigationArmee = cible;
    this.parametreArme = param;
    this.cheminArme = chemin;
  }

  private demanderNavigation(cible: Ecran, param: string | number | null = null): void {
    // Ici, rien n'a encore bougé : ni l'URL ni l'historique n'ont à être
    // reposés, contrairement à `appliquerChemin`.
    if (this.departARisque(cible)) {
      this.armer(cible, param);
      return;
    }
    this.naviguerVers(cible, param);
  }

  /** Le chemin d'un écran, ou `null` quand il n'en a pas : un ticket qu'on
   *  vient d'ouvrir pour le photographier n'existe pas encore côté serveur,
   *  donc aucun `/receipt/<id>` ne le désigne. On y va alors sans toucher à
   *  l'URL, plutôt que de laisser `pathOf` lever sur un cas légitime. */
  private cheminDe(ecran: Ecran, param: string | number | null): string | null {
    if (destinationOf(ecran).param && (param === null || param === undefined)) return null;
    return pathOf(ecran, param);
  }

  /** La navigation passe TOUJOURS par l'URL : `history.pushState` puis
   *  `location-changed`, la convention du frontend HA. Home Assistant nous
   *  repasse alors `route`, et `willUpdate` applique l'écran. Un seul chemin
   *  de navigation, donc le bouton Retour du navigateur et le geste système
   *  d'Android marchent sans une ligne de plus.
   *
   *  Le paramètre ne sert qu'à fabriquer l'URL : l'appelant a déjà posé la
   *  donnée (`recetteOuverte`, `ticketOuvert`…) avant d'appeler — la relire
   *  depuis une chaîne d'URL rejouerait un aller-retour serveur pour rien. */
  /** Écrit l'URL et prévient Home Assistant, sans rien décider de l'écran.
   *  `dernierChemin` est posé ici : HA nous repassera `route`, et cet écho
   *  n'a pas à refaire un rendu pour ce qu'on vient d'appliquer. */
  private pousserUrl(chemin: string, remplacer = false): void {
    const url = `${this.route?.prefix ?? '/home-stock'}${chemin}`;
    if (remplacer) window.history.replaceState(null, '', url);
    else window.history.pushState(null, '', url);
    window.dispatchEvent(new CustomEvent('location-changed', {
      detail: { replace: remplacer }, bubbles: true, composed: true,
    }));
    this.dernierChemin = chemin;
  }

  private naviguerVers(ecran: Ecran, param: string | number | null = null,
                       remplacer = false): void {
    const chemin = this.cheminDe(ecran, param);
    // HA ne nous repassera `route` que s'il écoute vraiment ; en test, et si
    // une version future changeait de convention, on applique nous-mêmes.
    if (chemin !== null) this.pousserUrl(chemin, remplacer);
    this.ecran = ecran;
  }

  private confirmerNavigation = (): void => {
    const cible = this.navigationArmee;
    const param = this.parametreArme;
    const chemin = this.cheminArme;
    this.navigationArmee = null;
    this.parametreArme = null;
    this.cheminArme = null;
    if (!cible) return;
    if (chemin !== null) {
      // Départ armé par une ROUTE : on la rejoue à la lettre, par le seul
      // endroit qui sait traduire un chemin en état. C'est lui, et lui seul,
      // qui applique le paramètre — `naviguerVers` ne le fait pas, exprès (un
      // geste de l'application a déjà posé sa donnée, et la relire d'une URL
      // rejouerait un aller-retour serveur pour rien). Garde-fou débranché :
      // le second appui vient de le lever.
      this.pousserUrl(chemin);
      this.appliquerChemin(chemin, false);
      return;
    }
    // Armé par un geste de l'application : l'appelant a déjà posé sa donnée,
    // il ne reste que l'URL et l'écran.
    this.naviguerVers(cible, param);
  };

  private annulerNavigation = (): void => {
    this.navigationArmee = null;
    this.parametreArme = null;
    this.cheminArme = null;
  };

  /** Les pastilles de la barre : un seul compte, sur « Courses ». Ce qui
   *  attend un geste, c'est ce qu'on a rapporté et pas encore rangé — sinon,
   *  à défaut, le panier en cours. Jamais les deux additionnés : ce sont deux
   *  choses différentes, et un chiffre qui mêle les deux ne veut rien dire. */
  private get pastilles(): Partial<Record<FamilyId, number>> {
    const aRanger = this.lignesARanger.length;
    const enPanier = this.session?.session?.state === 'shopping'
      ? this.session.totals.lines : 0;
    return { shopping: aRanger || enPanier };
  }

  private get actionPrimaire(): { icon: IconName; label: string } | null {
    // Le scan appartient aux Courses : c'est là qu'on rapporte un article,
    // qu'on le mette au panier ou qu'on le range. Ailleurs il n'aurait rien à
    // faire de ce qu'il lirait.
    return familyOf(this.ecran) === 'shopping' && this.ecran !== 'scanner'
      ? { icon: 'scan', label: 'Scanner un article' } : null;
  }

  private rendreConfirmationQuitter() {
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

  /** La famille choisie mène à SA racine, jamais à l’écran d’où l’on
   *  vient : c’est ce qui rend la barre prévisible. */
  private surFamilleChoisie = (evenement: CustomEvent<{ family: FamilyId }>): void => {
    const famille = FAMILIES.find((f) => f.id === evenement.detail.family);
    if (famille) this.demanderNavigation(famille.root);
  };

  /** Le retour remonte à la racine de la famille courante — jamais à
   *  `history.back()`, qui ramènerait à l’écran précédent quelle que soit sa
   *  famille et ferait sauter l’utilisateur d’un bout à l’autre du panneau. */
  private surRetour = (): void => {
    const famille = FAMILIES.find((f) => f.id === familyOf(this.ecran));
    if (famille) this.demanderNavigation(famille.root);
  };

  private surErreurAcquittee = (): void => {
    this.erreurFile = null;
  };

  static styles = [tokens, css`
    :host { display: block; height: 100%; background: var(--hs-surface-2); }
    /* Ordre du DOM : la barre AVANT la colonne, pour que le rail se pose
       naturellement à gauche en row. En column-reverse, la barre repasse en
       bas de l’écran sans quitter sa place dans le DOM — donc sans casser
       l’ordre de tabulation, et sans dvh ni :has(), absents de Chrome 100
       (la tablette de la cuisine). */
    /* position: relative — la confirmation de départ se pose EN SURCOUCHE
       par-dessus, sans démonter l'écran en dessous (voir render). */
    .coquille { position: relative; display: flex; flex-direction: column-reverse; height: 100%; }
    .coquille.large { flex-direction: row; }
    .colonne { flex: 1; display: flex; flex-direction: column; min-height: 0; }
    .contenu { flex: 1; overflow-y: auto; }
    .navigation { flex: 0 0 auto; }
    /* Une surcouche opaque, qui couvre AUSSI la barre : tant qu'un départ est
       armé, aucune autre destination n'est à un doigt de distance. Pas de
       dialog natif : Chrome 100 (la tablette de la cuisine) ne l'a pas. Pas
       d'inset non plus, les quatre côtés se disent très bien. */
    .confirmation-quitter-rangement {
      position: absolute; top: 0; right: 0; bottom: 0; left: 0; z-index: 2;
      display: flex; flex-direction: column; justify-content: center;
      gap: var(--hs-space-2);
      padding: var(--hs-space-3);
      background: var(--hs-surface); color: var(--hs-text);
    }
    .confirmation-quitter-rangement p { margin: 0; }
    .confirmer-quitter, .annuler-quitter {
      min-height: var(--hs-touch); width: 100%;
      border-radius: var(--hs-radius-s); border: none; font-size: 0.95rem;
      font-family: var(--hs-font); cursor: pointer;
    }
    /* Bordure, pas aplat : aucun texte ne tient 4,5:1 sur --hs-danger sous le
       thème HA par défaut (spec § 6.1 ter). Ce qui protège ce geste, c’est
       qu’il demande deux appuis — pas sa couleur. */
    .confirmer-quitter {
      background: var(--hs-surface); color: var(--hs-text);
      border: 2px solid var(--hs-danger);
    }
    .annuler-quitter { background: var(--hs-accent); color: var(--hs-on-accent); }
  `];

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
    // La fiche laisse l’écran à la caméra : sa barre de navigation reste
    // masquée, et l’en-tête y passe en `compact` (titre, retour, bannière —
    // pas de ligne secondaire).
    //
    // Mais l’en-tête, LUI, revient. La fiche n’est plus un cul-de-sac de
    // passage : `/item/<code>` est une URL partageable, et c’est la cible
    // délibérée de « Quitter quand même ». Sans en-tête, et sous la contrainte
    // « aucun geste de navigation » (pas de balayage, pas de bouton système),
    // on y entrait sans plus pouvoir en sortir — l’écran n’émet que
    // `article-pret` et `manger-produit`, jamais un retour. Le retour de
    // l’en-tête ramène à la racine de la famille, comme partout ailleurs.
    const pleinEcran = this.ecran === 'fiche';
    return html`
      <div class="coquille ${this.large ? 'large' : ''}">
        ${pleinEcran ? nothing : html`
        <hs-nav-bar class="navigation" .current=${this.ecran} .rail=${this.large}
          .badges=${this.pastilles} .action=${this.actionPrimaire}
          @famille-choisie=${this.surFamilleChoisie}
          @action-primaire=${() => this.demanderNavigation('scanner')}></hs-nav-bar>`}
        <div class="colonne">
          <hs-header .current=${this.ecran} .pending=${this.enAttente} .error=${this.erreurFile}
            .compact=${pleinEcran}
            @retour-demande=${this.surRetour}
            @erreur-acquittee=${this.surErreurAcquittee}
            @ecran-choisi=${(e: CustomEvent<{ screen: Ecran }>) => this.demanderNavigation(e.detail.screen)}></hs-header>
          <main class="contenu">${this.rendreEcran()}</main>
        </div>
        <!-- EN SURCOUCHE, jamais à la place : rendreEcran() s'exécute quand
             même, donc l'écran de rangement reste MONTÉ. Le démonter jetterait
             les emplacements que l'utilisateur vient de saisir à la main
             (emplacementChoisi, un état local de home-stock-rangement) —
             perdus par le bouton qui dit « je veux continuer », le pire des
             deux pour perdre quelque chose. -->
        ${this.navigationArmee ? this.rendreConfirmationQuitter() : nothing}
      </div>`;
  }

  /** Les références de `hass` qui témoignent d’un changement de THÈME, à la
   *  dernière mesure. Voir `themeAChange`. */
  private empreinteTheme: readonly unknown[] = [];

  /** Home Assistant remplace l’objet `hass` à CHAQUE changement d’état de la
   *  maison — sur la tablette de la cuisine, plusieurs fois par seconde. Or
   *  `appliquerCouleursDeTexte` n’est pas gratuit : il monte une sonde dans
   *  l’hôte et lit son `color` calculé, ce qui force un recalcul de style
   *  synchrone, deux fois (une par paire). Rejouer ça sur chaque état de
   *  lampe était du travail pur perte.
   *
   *  HA, lui, ne remplace `hass.themes` et `hass.selectedTheme` que quand le
   *  thème bouge vraiment : une comparaison de RÉFÉRENCES suffit, et elle ne
   *  coûte rien. `darkMode` est comparé à part parce qu’une bascule
   *  clair/sombre change la valeur sans changer l’objet qui la porte. */
  private themeAChange(): boolean {
    const empreinte = [this.hass?.themes, this.hass?.themes?.darkMode, this.hass?.selectedTheme];
    const change = empreinte.length !== this.empreinteTheme.length
      || empreinte.some((valeur, i) => valeur !== this.empreinteTheme[i]);
    this.empreinteTheme = empreinte;
    return change;
  }

  firstUpdated(): void {
    // Pas dans `connectedCallback` : la sonde de `on-color` a besoin de la
    // feuille adoptée pour résoudre `var(--hs-accent)`, et elle n’existe
    // qu’après le premier rendu.
    appliquerCouleursDeTexte(this);
    // Prend l’empreinte du thème AU MONTAGE : sans ça, le `updated()` du même
    // cycle de vie la verrait vide, la croirait changée, et referait le calcul
    // une seconde fois pour rien.
    this.themeAChange();
  }

  updated(changees: PropertyValues): void {
    // Le thème peut changer sous nos pieds (bascule clair/sombre, changement
    // de thème dans le profil) : HA repasse alors un nouvel objet `hass`. Mais
    // il en repasse un à chaque état de la maison — d’où le filtre.
    // `on-color.ts` ne pose rien s’il ne sait pas lire.
    if (changees.has('hass') && this.themeAChange()) appliquerCouleursDeTexte(this);
  }
}
