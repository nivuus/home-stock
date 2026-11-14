import { describe, expect, it, vi, type Mock } from 'vitest';
import { Connexion, type Hass } from '../src/connexion';

function hassFactice(): Hass & {
  connection: { sendMessagePromise: ReturnType<typeof vi.fn>; subscribeMessage: ReturnType<typeof vi.fn> };
  callService: ReturnType<typeof vi.fn>;
  fetchWithAuth: Mock<Hass['fetchWithAuth']>;
} {
  return {
    connection: {
      sendMessagePromise: vi.fn().mockResolvedValue({ ok: true }),
      subscribeMessage: vi.fn().mockResolvedValue(() => {}),
    },
    language: 'fr',
    callService: vi.fn().mockResolvedValue(undefined),
    fetchWithAuth: vi.fn<Hass['fetchWithAuth']>(),
  };
}

describe('connexion', () => {
  it('transmet le type et la charge au websocket de hass', async () => {
    const hass = hassFactice();
    const connexion = new Connexion(hass);

    const resultat = await connexion.appeler('home_stock/products/list', { limite: 10 });

    expect(hass.connection.sendMessagePromise).toHaveBeenCalledWith({
      type: 'home_stock/products/list',
      limite: 10,
    });
    expect(resultat).toEqual({ ok: true });
  });

  it('appelle sans charge quand aucune n’est fournie', async () => {
    const hass = hassFactice();
    const connexion = new Connexion(hass);

    await connexion.appeler('home_stock/aisles/list');

    expect(hass.connection.sendMessagePromise).toHaveBeenCalledWith({
      type: 'home_stock/aisles/list',
    });
  });

  it('s’abonne au résumé avec le type home_stock/subscribe', async () => {
    const hass = hassFactice();
    const connexion = new Connexion(hass);
    const rappel = vi.fn();

    await connexion.abonner(rappel);

    expect(hass.connection.subscribeMessage).toHaveBeenCalledWith(rappel, {
      type: 'home_stock/subscribe',
    });
  });

  it('appelle un service Home Assistant tel quel, sans passer par le websocket du domaine', async () => {
    const hass = hassFactice();
    const connexion = new Connexion(hass);

    await connexion.appelerService('home_stock', 'resync_off', { all: true });

    expect(hass.callService).toHaveBeenCalledWith('home_stock', 'resync_off', { all: true });
    expect(hass.connection.sendMessagePromise).not.toHaveBeenCalled();
  });

  it('appelle un service sans donnée quand aucune n’est fournie', async () => {
    const hass = hassFactice();
    const connexion = new Connexion(hass);

    await connexion.appelerService('home_stock', 'resync_off');

    expect(hass.callService).toHaveBeenCalledWith('home_stock', 'resync_off', {});
  });

  it('ne lit jamais localStorage : tout passe par la connexion de hass', async () => {
    const hass = hassFactice();
    const acces = vi.spyOn(window.localStorage.__proto__, 'getItem');
    const connexion = new Connexion(hass);

    await connexion.appeler('home_stock/products/list');
    await connexion.abonner(() => {});

    expect(acces).not.toHaveBeenCalled();
    acces.mockRestore();
  });
});

describe('receipt photo upload', () => {
  // Home Assistant's frontend exposes `hass.fetchWithAuth`, which refreshes an
  // expired access token before the request. A raw `access_token` read from
  // `hass.auth.data` is never refreshed: on a panel left open for more than
  // the token's lifetime the upload got a 401.
  function hassAvecFetch(reponse: Response) {
    const fetchWithAuth = vi.fn().mockResolvedValue(reponse);
    const fetchBrut = vi.fn();
    vi.stubGlobal('fetch', fetchBrut);
    const hass: Hass & { auth: unknown } = {
      ...hassFactice(),
      auth: { data: { access_token: 'expired-token' } },
      fetchWithAuth,
    };
    return { hass, fetchWithAuth, fetchBrut };
  }

  it('goes through the authenticated fetch helper of hass, never a raw token', async () => {
    const { hass, fetchWithAuth, fetchBrut } = hassAvecFetch(new Response(
      JSON.stringify({ media_content_id: 'media-source://media_source/local/x.jpg' }),
      { status: 200 }));
    const fichier = new File(['x'], 'ticket.jpg', { type: 'image/jpeg' });

    const id = await new Connexion(hass).televerserMedia(fichier, 'media-source://media_source/local/r');

    expect(id).toBe('media-source://media_source/local/x.jpg');
    expect(fetchBrut).not.toHaveBeenCalled();
    expect(fetchWithAuth).toHaveBeenCalledTimes(1);
    const [chemin, init] = fetchWithAuth.mock.calls[0];
    expect(chemin).toBe('/api/media_source/local_source/upload');
    expect(init.method).toBe('POST');
    expect((init.body as FormData).get('media_content_id')).toBe('media-source://media_source/local/r');
    expect(JSON.stringify(init.headers ?? {})).not.toContain('expired-token');
    vi.unstubAllGlobals();
  });

  it('rejects with the HTTP status when the upload is refused', async () => {
    const { hass } = hassAvecFetch(new Response('', { status: 403 }));
    await expect(new Connexion(hass).televerserMedia(new File(['x'], 'a.jpg'), 'd'))
      .rejects.toThrow('403');
    vi.unstubAllGlobals();
  });
});
