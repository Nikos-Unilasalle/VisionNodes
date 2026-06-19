# Exercices — Chapitre 11 · Tester une forme : la morphologie mathématique

---

## Exercice 1 · Filtrer des grains de pollen par leur forme

![Image microscopique de pollen : grains circulaires lisses (tournesol), grains épineux (rose), grains allongés (maïs), de tailles variées sur le même fond](../figures/ex_ch11_pollen.jpg)

**Ce que vous voyez.** Trois formes de pollen mélangées. La mission : n'en garder qu'une à la fois en choisissant la bonne sonde, comme un tamis qui ne laisse passer qu'une forme.

**Pipeline VNStudio**
`Image Source` → `Threshold (Advanced)` → `Morphology (Advanced)` → `Connected Components` → `Region Properties` → `Output Display`

Le nœud de morphologie applique une sonde de forme et de taille réglables ; l'inspecteur compte les grains survivants.

---

**Questions**

1. Appliquez une ouverture avec une sonde ronde de rayon moyen. Quels grains survivent : les plus gros, les plus ronds ? Lesquels disparaissent ? Comptez les survivants.

2. Remplacez la sonde par une fine barre horizontale et érodez. Quels grains tiennent : les allongés horizontaux, les ronds, les épineux ? Que révèle ce choix de sonde sur la forme que vous sélectionnez ?

3. Sur des grains percés de petits trous (artefacts de seuillage), appliquez une fermeture. Les trous se comblent-ils ? Quelle taille de sonde suffit à tous les boucher sans souder les grains entre eux ?

4. **Défi.** Réglez une chaîne complète pour ne compter que les grains ronds de tournesol, en éliminant les épineux et les allongés. Quelle combinaison de sonde et de filtre d'aire y arrive ? Combien de grains de tournesol comptez-vous ?

---

## Exercice 2 · Faire ressortir un texte sur un fond inégal

![Ancienne carte géographique manuscrite : fond jauni à éclairage inégal, noms de villes en encre noire (petits), tracés de rivières fins](../figures/ex_ch11_carte_ancienne.jpg)

**Ce que vous voyez.** Un fond qui s'assombrit lentement d'un coin à l'autre, sur lequel se détachent de petits détails sombres. La mission : effacer ce fond inégal pour ne garder que le texte, étape clé avant toute lecture automatique.

**Pipeline VNStudio**
`Image Source` → `Morphology (Advanced)` (Top Hat) → `Colormap` → `Output Display`

Le top-hat estime le fond avec une grande sonde puis le soustrait, ne laissant que les détails plus petits que la sonde.

---

**Questions**

1. Appliquez le top-hat avec une grande sonde. Qu'est-ce qui ressort : le texte ou le fond jauni ? Le fond inégal a-t-il disparu, devenu uniforme ?

2. Agrandissez progressivement la sonde. À partir de quelle taille les noms de villes commencent-ils eux aussi à disparaître ? Pourquoi la sonde ne doit-elle pas être plus grande que les détails à garder ?

3. Sur une carte au texte clair sur fond sombre, quel mode (top-hat clair ou sombre) fait ressortir le texte ? Vérifiez que le bon mode dépend du contraste texte/fond.

4. **Défi.** Enchaînez top-hat, seuillage et comptage pour extraire tous les caractères de la carte. Combien de morceaux sont détectés ? Ajoutez un filtre d'aire pour jeter les résidus de bruit. Combien de vrais caractères reste-t-il ?

---

## Exercice 3 · Extraire le contour et l'ossature d'une feuille

![Silhouette binaire d'une feuille de chêne : forme blanche sur fond noir, lobes caractéristiques et pétiole fin](../figures/ex_ch11_feuille_chene.jpg)

**Ce que vous voyez.** Une silhouette à lobes et à axe central fin. La mission : en tirer un contour propre puis une « ossature » réduite à l'essentiel, utile pour identifier l'espèce.

**Pipeline VNStudio**
`Image Source` → `Threshold (Advanced)` → `Split Half` :
— gauche : `Morphology (Advanced)` (gradient morphologique)
— droite : `Sobel Edge Detector`
→ `Output Display`

Le gradient morphologique trace le contour par différence entre dilatation et érosion ; comparez-le au contour classique.

---

**Questions**

1. Comparez les deux contours sur un bord lisse, puis sur un coin de lobe. Lequel donne un trait plus régulier ? Lequel est plus fin ?

2. Ajoutez du bruit poivre et sel à l'image et relancez. Lequel des deux contours résiste le mieux aux pixels parasites ? Pourquoi un contour fondé sur min/max locaux encaisse-t-il mieux quelques pixels fous ?

3. Érodez la feuille étape par étape et observez. Quand le pétiole fin disparaît-il ? Et les lobes ? Quelle partie de la feuille résiste le plus longtemps ?

4. **Défi.** Réduisez la feuille à son ossature centrale (squelette) avec le mode dédié du nœud de morphologie. Combien de branches obtenez-vous ? Y a-t-il autant de branches que de lobes ? Cette ossature suffirait-elle à reconnaître un chêne parmi d'autres feuilles ?

---

*Corrigés disponibles en annexe.*
