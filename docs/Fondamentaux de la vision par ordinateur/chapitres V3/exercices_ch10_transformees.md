# Exercices — Chapitre 10 · Changer de regard : les transformées

---

## Exercice 1 · Effacer un motif de tissu sans toucher au reste

![Tissu à carreaux réguliers photographié à plat : motif périodique de lignes bleues et blanches, horizontales et verticales, parfaitement répété](../figures/ex_ch10_tissu_carreaux.jpg)

**Ce que vous voyez.** Un motif parfaitement périodique. La mission : passer dans l'espace des fréquences pour repérer la signature du quadrillage, puis le faire disparaître à volonté.

**Pipeline VNStudio**
`Image Source` → `FFT Analysis` → `Output Display` (spectre) + `Colormap`

Le nœud affiche le spectre de fréquences et permet d'appliquer un filtre passe-bas ou passe-haut avant de reconstruire l'image.

---

**Questions**

1. Observez le spectre : voyez-vous des points brillants bien nets, ou une tache diffuse ? Que disent ces points sur la régularité du tissu ? Repérez ceux qui correspondent aux lignes horizontales et ceux des verticales.

2. Appliquez un filtre passe-bas. Le quadrillage survit-il dans l'image reconstruite, ou s'efface-t-il ? Qu'a-t-on retiré au juste ?

3. Appliquez un filtre passe-haut. L'image reconstruite ne garde-t-elle que les contours du motif ? Pourquoi le fond uni a-t-il disparu ?

4. **Défi.** Passez la FFT sur un visage au lieu du tissu. Le spectre montre-t-il des points nets comme le tissu, ou une tache continue qui s'éteint depuis le centre ? Qu'est-ce que cela révèle sur la différence entre un motif fabriqué et une image naturelle ?

---

## Exercice 2 · Retrouver les routes d'un carrefour par le vote

![Vue aérienne d'un carrefour en étoile : cinq routes rectilignes convergent vers un rond-point central, leurs bords nets se détachant sur le macadam sombre](../figures/ex_ch10_carrefour.jpg)

**Ce que vous voyez.** Plusieurs droites bien marquées dans la scène. La mission : les faire retrouver automatiquement, sans dire au système où elles sont.

**Pipeline VNStudio**
`Image Source` → `Canny Edge Detector` *(à créer)* → `Hough Transform` *(à créer)* → `Draw Overlay` → `Output Display`

Le nœud trace les droites détectées sur l'image et expose un seuil de vote qui décide combien de lignes ressortent.

---

**Questions**

1. Lancez le pipeline. Les cinq routes sont-elles toutes tracées ? Leur direction colle-t-elle à ce que vous voyez ?

2. Le rond-point central est un cercle. Le détecteur de droites trace-t-il une ligne dessus ? Pourquoi un bord qui tourne en rond ne réunit-il pas assez de votes pour une seule direction ?

3. Baissez le seuil de vote. Combien de fausses lignes apparaissent en plus ? D'où viennent-elles dans la scène (marquages, trottoirs, ombres) ?

4. **Défi.** Passez le détecteur sur une feuille de papier millimétré : il devrait ne trouver que deux familles de lignes (horizontales et verticales). Vérifiez. Faites ensuite pivoter la feuille de 15° et observez les deux familles tourner d'autant. Le détecteur suit-il la rotation ?

---

## Exercice 3 · Trouver le cœur d'une forme pour préparer une découpe

![Masque binaire d'une étoile à cinq branches : fond noir, étoile blanche, branches fines et allongées, centre en pentagone plus large](../figures/ex_ch10_etoile_masque.jpg)

**Ce que vous voyez.** Une forme à bras fins et centre épais. La mission : mesurer « l'épaisseur intérieure » en chaque point pour trouver les cœurs des régions, étape clé avant de séparer des objets collés.

**Pipeline VNStudio**
`Image Source` → `Threshold (Advanced)` → `Distance Transform` → `Colormap` (LUT chaud) → `Output Display`

La carte colore chaque pixel selon son éloignement du bord le plus proche : froid près des bords, chaud au cœur.

---

**Questions**

1. Sur la carte colorée, où se trouve le point le plus « chaud » de l'étoile : au centre du pentagone ou au bout d'une branche ? Pourquoi ?

2. Comparez la couleur au cœur d'une branche fine et au cœur du pentagone. Laquelle est la plus chaude ? Que dit cette couleur sur l'épaisseur locale de la forme ?

3. Cette carte sert de relief pour séparer des objets collés : on plante un germe à chaque sommet chaud. Combien de sommets chauds distincts comptez-vous sur l'étoile ? Un par branche plus un au centre, ou un seul ?

4. **Défi.** Collez deux étoiles par le bout d'une branche et relancez la carte. Y a-t-il toujours deux cœurs bien séparés ? Branchez un `Watershed` qui part de ces cœurs et vérifiez qu'il recoupe les deux étoiles à l'endroit du collage.

---

*Corrigés disponibles en annexe.*
