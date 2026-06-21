# Exercices — Chapitre 3 · Mesurer un écart : distances et similarités

---

## Exercice 1 · Choisir la bonne distance pour comparer deux couleurs

![Nuancier de peinture : une couleur de référence au centre, entourée de huit échantillons proches. Certains ne diffèrent que sur un canal (plus rouge), d'autres sur plusieurs à la fois](../figures/ex_ch3_nuancier.jpg)

**Ce que vous voyez.** Une couleur de référence et ses voisines. La mission : trouver laquelle est « la plus proche », et constater que la réponse change selon la façon de mesurer l'écart.

**Pipeline VNStudio**
`Image File` → `Histogram Compare` → `Apply Colormap` → `Display`

Le nœud calcule la distance de chaque pixel à la couleur de référence, au choix en mode L1 (somme des écarts), L2 (distance directe) ou L∞ (plus grand écart sur un canal).

---

**Questions**

1. En mode L2, quelle teinte du nuancier ressort comme la plus proche de la référence ? Repérez-la sur la carte de distance.

2. Basculez en mode L∞. La couleur jugée la plus proche change-t-elle ? Pourquoi ce mode ne regarde-t-il que le canal qui s'écarte le plus, en ignorant les autres ?

3. Prenez une teinte qui diffère un peu sur les trois canaux et une autre qui diffère beaucoup sur un seul. Selon le mode, laquelle est déclarée la plus proche ? Pour assortir une retouche de peinture, quel mode vous semble le plus juste ?

4. **Défi.** Réglez le mode et le seuil pour qu'une chaîne de contrôle qualité accepte les échantillons « assez proches » de la référence et rejette les autres. Combien d'échantillons passent ? Le résultat change-t-il selon le mode de distance choisi ?

---

## Exercice 2 · Repérer une anomalie discrète sur un fond qui varie

![Pelouse vue du dessus : fond vert dont la teinte varie naturellement, quelques plaques de terre brune étendues, et une petite fleur violette isolée. L'œil saute sur la fleur, pas sur la terre](../figures/ex_ch3_pelouse.jpg)

**Ce que vous voyez.** Un fond dont la couleur varie beaucoup tout seul. L'intrus à trouver (la fleur) est petit ; la terre, plus étendue, n'est pas vraiment une anomalie. La mission : détecter ce qui sort vraiment de l'ordinaire.

**Pipeline VNStudio**
`Image File` → `Color Convert (BGR→HSV)` → `Histogram Compare` → `Apply Colormap` → `Display`

Le nœud apprend la couleur « normale » sur une zone de pelouse que vous sélectionnez, puis allume chaque pixel selon son étrangeté en tenant compte de la façon dont la pelouse varie.

---

**Questions**

1. Sélectionnez une zone de pelouse comme référence, puis lancez le calcul. Qu'est-ce qui s'allume le plus fort sur la carte : la fleur violette ou la terre brune ?

2. Branchez à la place une simple distance de couleur ordinaire (mode L2 du nœud précédent). La terre brune ressort-elle maintenant à tort comme une anomalie ? Pourquoi tenir compte de la variation naturelle du fond change le verdict ?

3. Agrandissez la zone de référence pour qu'elle inclue un peu de terre. La fleur ressort-elle toujours autant ? Qu'est-ce que cela vous dit sur l'importance de bien choisir la zone « normale » ?

4. **Défi.** Réglez le seuil pour ne marquer que la fleur, sans aucune fausse alarme sur la pelouse ou la terre. Existe-t-il un réglage parfait, ou faut-il accepter un compromis ? Ajoutez une deuxième petite fleur et vérifiez qu'elle est aussi détectée.

---

## Exercice 3 · Distinguer une variation de lot d'un vrai changement de produit

![Trois boîtes de céréales côte à côte : deux de la même marque mais de lots différents (même teinte, l'une un peu plus claire), et une troisième d'une marque concurrente, de couleur franchement différente](../figures/ex_ch3_cereales.jpg)

**Ce que vous voyez.** Deux produits presque identiques (simple variation d'impression) et un produit vraiment différent. La mission : régler une comparaison qui tolère la variation de lot mais détecte le vrai changement.

**Pipeline VNStudio**
`Image File` → `Color Convert (BGR→Lab)` → `Histogram` → `Histogram Compare` → `Display`

Le nœud compare les histogrammes deux à deux et affiche leur écart, au choix avec une mesure « case par case » (χ²) ou une mesure « de glissement » (Wasserstein, sensible au décalage d'ensemble).

---

**Questions**

1. Comparez les deux boîtes de la même marque. La mesure de glissement les juge-t-elle proches ? La mesure case par case est-elle d'accord, ou les déclare-t-elle très différentes à cause du léger décalage de luminosité ?

2. Comparez maintenant une boîte de la marque avec celle du concurrent. Les deux mesures s'accordent-elles cette fois sur une grande différence ?

3. Éclaircissez progressivement une boîte (réglez son exposition). Suivez les deux écarts. Lequel grimpe doucement avec le décalage, lequel s'emballe dès le premier glissement ? Lequel reflète mieux « c'est le même produit, juste un autre lot » ?

4. **Défi.** Réglez la comparaison et un seuil pour qu'un contrôle qualité accepte les variations de lot et n'alerte que sur un vrai changement de produit. Quelle mesure choisissez-vous ? Testez sur les trois boîtes et vérifiez qu'une seule alerte se déclenche.

---

*Corrigés disponibles en annexe.*
