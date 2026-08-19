import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { Connexion, type Hass } from './connexion';
import { FileAttente } from './file-attente';
import './ecrans/scanner';
import './ecrans/fiche';
import type { ResumeDerniereFiche } from './ecrans/scanner';
import type { ResultatLookup } from './ecrans/fiche';

export type Ecran = 'scanner' | 'fiche' | 'panier' | 'rangement' | 'catalogue' | 'reglages';

type SessionCourante = { store: string | null } | null;

type ArticlePret = { articleId: number; quantite: number; prixUnitaire: number | null; mode: 'panier' | 'rangement' };

/** Ce que la bannière et la dernière-fiche affichent : un résumé, pas la
 *  réponse brute de `lookup`. */
function resumeDe(resultat: ResultatLookup | null, statut: string): ResumeDerniereFiche | null {
  if (!resultat) return null;
  const nom = resultat.off?.label ?? resultat.article?.label ?? resultat.product?.name ?? resultat.code;
  const marque = resultat.off?.brand ?? resultat.article?.brand ?? null;
  const image = resultat.off?.image ?? resultat.article?.image ?? null;
  return { nom, marque, image, statut };
}

@customElement('home-stock-panel')
export class PanneauGardeManger extends LitElement {
  @property({ attribute: false }) hass!: Hass;
  @property({ attribute: false }) narrow = false;
  @state() ecran: Ecran = 'scanner';
  @state() enAttente = 0;
  @state() private session: SessionCourante = null;
  @state() private resultatCourant: ResultatLookup | null = null;
  @state() private derniereFiche: ResumeDerniereFiche | null = null;

  private connexion?: Connexion;
  private file?: FileAttente;
  private desabonner?: () => void;

  connectedCallback(): void {
    super.connectedCallback();
    this.connexion = new Connexion(this.hass);
    this.file = new FileAttente(window.localStorage, (type, charge) =>
      this.connexion!.appeler(type, charge));
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

  /** `session/current` plutôt qu'un champ du résumé : le résumé n'a pas de
   *  booléen « session ouverte » (un panier tout juste ouvert et un panier
   *  vide se ressemblent), alors que cette commande répond `null` sans
   *  ambiguïté quand il n'y a pas de session. */
  private async actualiserSession(): Promise<void> {
    try {
      const courante = await this.connexion!.appeler<{ store: string | null } | null>(
        'home_stock/session/current');
      this.session = courante ? { store: courante.store } : null;
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
   *  faire. En session, ajouter au panier ne demande rien de plus (pas
   *  d'emplacement à choisir) : c'est fait ici. Hors session, choisir
   *  l'emplacement et la DLC revient à l'écran « rangement » — pas encore
   *  construit (lot suivant, avec `raccourcisDlc`) : en attendant, l'article
   *  existe déjà dans le catalogue (c'est le principal), et on revient au
   *  scanner pour ne pas bloquer la suite des scans. */
  private surArticlePret = async (evenement: CustomEvent<ArticlePret>): Promise<void> => {
    const { articleId, quantite, prixUnitaire, mode } = evenement.detail;
    if (mode === 'panier') {
      try {
        await this.connexion!.appeler('home_stock/session/add_line', {
          article_id: articleId, quantity: quantite,
          unit_price: prixUnitaire ?? undefined, idempotency_key: crypto.randomUUID(),
        });
        this.derniereFiche = resumeDe(this.resultatCourant, 'Ajouté au panier.');
      } catch {
        this.derniereFiche = resumeDe(this.resultatCourant, 'Non envoyé — hors ligne.');
      }
    } else {
      this.derniereFiche = resumeDe(this.resultatCourant, 'Article créé — reste à ranger.');
    }
    this.resultatCourant = null;
    this.ecran = 'scanner';
  };

  static styles = css`
    :host { display: block; height: 100%; background: var(--primary-background-color); }
  `;

  render() {
    if (this.ecran === 'scanner') {
      return html`
        <home-stock-scanner .session=${this.session} .derniereFiche=${this.derniereFiche}
          @code-lu=${this.surCodeLu}>
        </home-stock-scanner>`;
    }
    if (this.ecran === 'fiche' && this.resultatCourant) {
      return html`
        <home-stock-fiche .resultat=${this.resultatCourant}
          .mode=${this.session ? 'panier' : 'rangement'} .connexion=${this.connexion}
          @article-pret=${this.surArticlePret}>
        </home-stock-fiche>`;
    }
    return html`<div class="ecran">${this.ecran}</div>`;
  }
}
