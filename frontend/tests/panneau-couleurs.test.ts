import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Hass } from '../src/connexion';

/** `appliquerCouleursDeTexte` monte une sonde dans l'hôte et lit son `color`
 *  calculé : deux recalculs de style SYNCHRONES par appel. Home Assistant,
 *  lui, repasse un objet `hass` neuf à chaque changement d'état de la maison
 *  — sur la tablette de la cuisine, plusieurs fois par seconde. Ce fichier
 *  compte les appels ; il faut donc espionner le module AVANT que
 *  `panneau.ts` ne l'importe, d'où le `vi.mock` (hissé) et l'import dynamique
 *  du panneau plus bas. */
const appliquer = vi.fn();
vi.mock('../src/shell/ui/on-color', async (original) => ({
  ...(await original<typeof import('../src/shell/ui/on-color')>()),
  appliquerCouleursDeTexte: (hote: HTMLElement) => appliquer(hote),
}));

await import('../src/panneau');

type Panneau = HTMLElement & { hass: Hass; updateComplete: Promise<unknown> };

function hassFactice(themes: object, selectedTheme: unknown = null): Hass {
  return {
    connection: {
      sendMessagePromise: vi.fn().mockResolvedValue(null),
      subscribeMessage: vi.fn().mockResolvedValue(() => {}),
    },
    language: 'fr',
    themes,
    selectedTheme,
  } as unknown as Hass;
}

/** Le même `hass` qu'avant, mais un OBJET neuf : exactement ce que HA repasse
 *  quand une lampe change d'état, thème inchangé. */
function memeTheme(precedent: Hass): Hass {
  return hassFactice(precedent.themes as object, precedent.selectedTheme);
}

async function monter(hass: Hass): Promise<Panneau> {
  const el = document.createElement('home-stock-panel') as Panneau;
  el.hass = hass;
  document.body.appendChild(el);
  await el.updateComplete;
  return el;
}

describe('panneau : recalcul des couleurs de texte', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    appliquer.mockClear();
  });

  it('calcule une fois au montage, et une seule', async () => {
    await monter(hassFactice({ darkMode: false }));
    expect(appliquer).toHaveBeenCalledTimes(1);
  });

  it('ne recalcule PAS quand seul l’état de la maison a changé', async () => {
    // Le défaut corrigé : `changees.has('hass')` est vrai à chaque état de
    // lampe, de capteur, de minuteur. Un panneau ouvert sur la tablette de la
    // cuisine forçait alors deux recalculs de style par seconde, pour
    // reposer exactement la même couleur.
    const el = await monter(hassFactice({ darkMode: false }));
    appliquer.mockClear();

    for (let i = 0; i < 5; i += 1) {
      el.hass = memeTheme(el.hass);
      await el.updateComplete;
    }

    expect(appliquer).not.toHaveBeenCalled();
  });

  it('recalcule quand le thème change vraiment', async () => {
    const el = await monter(hassFactice({ darkMode: false }));
    appliquer.mockClear();

    // Un autre objet `themes` : c'est ce que HA repose quand le thème change.
    el.hass = hassFactice({ darkMode: false });
    await el.updateComplete;
    expect(appliquer).toHaveBeenCalledTimes(1);

    // Une bascule clair/sombre, elle, peut ne changer QUE le booléen.
    const themes = el.hass.themes as { darkMode?: boolean };
    el.hass = { ...el.hass, themes: { ...themes, darkMode: true } } as Hass;
    await el.updateComplete;
    expect(appliquer).toHaveBeenCalledTimes(2);

    // Et le thème choisi dans le profil, qui vit ailleurs.
    el.hass = { ...el.hass, selectedTheme: { theme: 'graphite' } } as Hass;
    await el.updateComplete;
    expect(appliquer).toHaveBeenCalledTimes(3);
  });
});
