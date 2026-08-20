import { describe, expect, it, vi } from 'vitest';
import { Connexion, type Hass } from '../src/connexion';

function hassFactice(): Hass & {
  connection: { sendMessagePromise: ReturnType<typeof vi.fn>; subscribeMessage: ReturnType<typeof vi.fn> };
  callService: ReturnType<typeof vi.fn>;
} {
  return {
    connection: {
      sendMessagePromise: vi.fn().mockResolvedValue({ ok: true }),
      subscribeMessage: vi.fn().mockResolvedValue(() => {}),
    },
    language: 'fr',
    callService: vi.fn().mockResolvedValue(undefined),
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
