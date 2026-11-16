# Garde-manger (`home_stock`)

Gestion des stocks de la maison dans Home Assistant : placards, frigo,
congélateur, alimentaire comme ménager. Chaque lot porte sa date limite et son
prix payé ; le journal des mouvements alimente la comptabilité kcal et euros par
jour.

## Installation

HACS → Intégrations → dépôt personnalisé → cette URL, catégorie « Integration ».
Puis Paramètres → Appareils et services → Ajouter une intégration → Garde-manger.

## État

Lot 0 : fondations (schéma, catalogue, lots, journal, services). Le scan de
codes-barres et l'interface arrivent au lot 1.

Langues : les phrases vocales n'existent qu'en français (`custom_sentences/fr`) ;
il manque leurs équivalents dans les autres langues, ainsi que les libellés
d'unités et le format des nombres (`domain/units.py`) et le choix des noms Open
Food Facts dans la langue configurée, encore figés en français.
