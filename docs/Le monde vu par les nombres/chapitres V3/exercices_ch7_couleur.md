# Exercices — Chapitre 7 · La couleur n'est pas dans l'objet

---

## Exercice 1 · Redresser un dégradé qui ment à l'œil

![Dégradé de gris imprimé puis photographié : dix bandes censées être régulièrement espacées de noir à blanc, mais les bandes sombres paraissent trop serrées entre elles](../figures/ex_ch7_degrade_gris.jpg)

**Ce que vous voyez.** Un dégradé qui semble irrégulier alors qu'il a été conçu régulier. La mission : comprendre et corriger l'encodage gamma qui déforme les valeurs sombres dans tout fichier d'image.

**Pipeline VNStudio**
`Image File` → `Split Half` :
— gauche : image brute → `Line Profile`
— droite : `Gamma Correction` *(à créer)* → `Line Profile`
→ `Display`

Le profil de ligne trace la luminosité le long du dégradé ; comparez avant et après correction.

---

**Questions**

1. Tracez le profil sur les deux moitiés. Lequel forme une belle droite régulière, lequel est courbé ? Le côté corrigé colle-t-il mieux à l'idée d'un dégradé uniforme ?

2. La correction relève surtout les tons sombres. Sur le profil, où l'écart entre brut et corrigé est-il le plus grand : dans les noirs ou dans les blancs ? Pourquoi l'œil et le fichier « tassent » les valeurs sombres ?

3. Floutez l'image avant correction, puis après correction, et comparez les deux résultats. Sont-ils identiques ? Lequel ressemble à un vrai flou d'objectif ?

4. **Défi.** Sur une photo d'objet blanc sous lampe orangée, faites une balance des blancs avant correction, puis après. Dans quel cas le blanc redevient-il vraiment neutre ? Concluez sur l'ordre correct des opérations couleur.

---

## Exercice 2 · Trier des fruits par couleur malgré l'éclairage inégal

![Corbeille de fruits mélangés (pommes rouges, citrons jaunes, oranges), un côté en pleine lumière, l'autre dans l'ombre : les mêmes fruits ont des valeurs très différentes selon leur position](../figures/ex_ch7_fruits.jpg)

**Ce que vous voyez.** Des fruits de teintes distinctes mais d'éclairages variables. La mission : les trier par couleur sans qu'une pomme à l'ombre soit confondue avec une orange au soleil.

**Pipeline VNStudio**
`Image File` → `Color Space` → `Channel Split` → `Display`

En HSV, la teinte est séparée de la luminosité : un objet garde sa teinte qu'il soit éclairé ou ombré.

---

**Questions**

1. Sur le canal de teinte, une pomme rouge au soleil et une pomme rouge à l'ombre ont-elles la même valeur ? Comparez avec le canal rouge brut : lequel reste stable malgré l'éclairage ?

2. Isolez le rouge en seuillant la seule teinte. Les pommes à l'ombre restent-elles dans le masque ? Combien auraient été perdues avec un tri sur les couleurs brutes ?

3. Montez un tri à trois sorties : pommes rouges, oranges, citrons jaunes, chacun sur sa plage de teinte. Combien de fruits de chaque type comptez-vous ? Un fruit tombe-t-il dans la mauvaise catégorie ?

4. **Défi.** Sur un reflet blanc brillant (une pomme cirée), la teinte devient instable et saute. Ajoutez une condition sur la saturation pour ignorer ces reflets ternes. Le tri redevient-il propre ? Pourquoi une couleur délavée n'a-t-elle plus de teinte fiable ?

---

## Exercice 3 · Mesurer une différence de couleur comme l'œil la perçoit

![Deux échantillons de peinture bleu roi côte à côte : l'un légèrement plus chaud, l'autre plus froid. L'écart de valeurs brutes est minime, mais l'œil voit clairement deux bleus différents](../figures/ex_ch7_peinture_bleus.jpg)

**Ce que vous voyez.** Deux couleurs que les valeurs brutes jugent presque identiques mais que l'œil distingue sans peine. La mission : mesurer la différence de couleur d'une façon fidèle à la perception, pour un contrôle qualité de teinte.

**Pipeline VNStudio**
`Image File` → `Color Space` → `Color Distance` → `Display`

L'espace Lab est construit pour que les écarts de couleur collent à la perception ; le nœud y mesure la distance perceptuelle entre deux zones.

---

**Questions**

1. Mesurez l'écart entre les deux bleus avec les couleurs brutes, puis en Lab. Laquelle des deux mesures reflète mieux la différence que vous voyez à l'œil ?

2. Comparez deux autres paires : un bleu très foncé contre un noir (à peine distinguables) et un orange vif contre un rouge (franchement différents). Dans quel cas les deux mesures s'accordent-elles, dans quel cas se contredisent-elles ?

3. La différence entre les deux bleus est-elle surtout une affaire de clair/foncé, ou de chaud/froid ? Le nœud peut isoler chaque aspect : lequel domine ici ?

4. **Défi.** Réglez un seuil de différence perceptuelle pour qu'une chaîne de contrôle accepte un échantillon « assez proche » de la teinte cible et rejette les autres. Testez sur plusieurs échantillons. Le seuil basé sur la perception est-il plus fiable que celui sur les couleurs brutes ?

---

*Corrigés disponibles en annexe.*
