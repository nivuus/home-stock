# Journal des modifications

Toutes les modifications notables de home-stock sont notées ici. Le format suit
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et la numérotation suit
le [versionnage sémantique](https://semver.org/lang/fr/). Le numéro de version
est celui de la release que le workflow de publication calcule à partir des
sujets de commit ; les versions antérieures à 1.7.0 sont décrites dans les notes
des releases GitHub.

## [1.7.0] - 2026-10-10

### Ajouté

- Changer la quantité d'une ligne d'ingrédient d'une recette existante sans
  recréer la recette : commande websocket `home_stock/recipe/ingredient/update`
  et service `home_stock.set_recipe_ingredient_quantity` (`quantity` dans
  l'unité de base du produit).
- Retirer une ligne d'ingrédient d'une recette existante : commande websocket
  `home_stock/recipe/ingredient/delete` et service
  `home_stock.remove_recipe_ingredient`.
- Les deux gestes désignent la ligne par son identifiant (`ingredient_id`,
  avec `recipe_id` facultatif pour vérifier qu'elle est bien de cette
  recette), ou par la recette et le nom de son produit (`recipe_id` +
  `product`, sans tenir compte des majuscules ; une ligne sans produit répond
  à son texte importé, comme « eau »). Un nom que portent deux lignes est
  refusé : l'identifiant tranche alors.
- Remettre une ligne d'ingrédient dans une recette (le retour en arrière
  d'un retrait) : commande websocket `home_stock/recipe/ingredient/add` et
  service `home_stock.add_recipe_ingredient` (`recipe_id`, `product` par son
  nom ou seulement `raw_text`, `quantity` dans l'unité de base, `position`
  pour reprendre la place qu'avait la ligne). La réponse d'un retrait donne
  le texte, la quantité et la position à reprendre.
- Lister les lignes d'ingrédient d'une recette avec leur identifiant :
  service `home_stock.get_recipe_ingredients` (`recipe_id`), qui ne modifie
  rien et donne l'`ingredient_id` qu'attendent les deux gestes ci-dessus.
- Un champ refusé (quantité nulle, négative, non numérique ou supérieure à
  100 000, champ manquant ou inconnu, ligne introuvable) l'est en français sur
  la commande websocket comme sur le service, et rien n'est écrit.
- Après l'un ou l'autre geste, le capteur du prochain repas est recalculé
  aussitôt ; l'aperçu d'un repas relit la recette modifiée.

Exemple de script qui enchaîne les trois services et lit leurs réponses
(`response_variable`) — le petit-déj de la recette 193 :

```yaml
petit_dej_193:
  alias: Petit-déj — krisprolls à 50 g, sans ail ni eau
  sequence:
    - action: home_stock.get_recipe_ingredients
      data:
        recipe_id: 193
      response_variable: recette
    - action: home_stock.set_recipe_ingredient_quantity
      data:
        recipe_id: 193
        ingredient_id: >-
          {{ (recette.ingredients | selectattr('product', 'search', '^krisprolls$', true)
              | first).ingredient_id }}
        quantity: 50
      response_variable: modifiee
    - action: home_stock.remove_recipe_ingredient
      data:
        recipe_id: 193
        product: Ail
    - action: home_stock.remove_recipe_ingredient
      data:
        recipe_id: 193
        product: eau
      response_variable: retiree
    - action: persistent_notification.create
      data:
        title: Recette 193
        message: >-
          Krisprolls : {{ modifiee.ingredient.amount }} g ;
          retiré : {{ retiree.removed.raw_text }}.
```

### Modifié

- `manifest.json` porte désormais le numéro de la release (`1.7.0`) au lieu de
  `0.1.0`.

### Limites connues

- Une ligne remise par `home_stock.add_recipe_ingredient` n'est pas tout à
  fait celle qui a été retirée :
  - elle reçoit un nouvel identifiant (`ingredient_id`) ;
  - sa quantité est en unité de base du produit : un conditionnement ou une
    mesure (comme « 1 gousse » d'ail) ne revient pas, seule la quantité en
    grammes, millilitres ou pièces ;
  - elle n'a plus de groupe (`group_name`) et n'est plus marquée facultative
    (`optional`) ;
  - elle perd sa référence d'import (`external_ref`) et son score de
    rapprochement (`match_score`) ; son état de rapprochement devient
    « confirmé » avec un produit, « ignoré » sans.
- Changer une quantité remplace de même un conditionnement ou une mesure par
  l'unité de base : la ligne garde son texte importé, qui n'est que la trace
  de l'import.
