# Note de style — l'ordre de l'invention : intention → forme → formule

> **Statut.** Troisième document de style, qui surplombe les deux précédents. `INSTRUCTIONS_STYLE_PROJET.md` fixe la structure ; `NOTE_STYLE_DEGRAISSAGE.md` traite les tics rhétoriques. **Cette note fixe la doctrine pédagogique de l'ouvrage** — l'objectif premier auquel tout le reste se subordonne. En cas de conflit avec une consigne plus ancienne, c'est cette note qui tranche. Elle **amende explicitement** le gabarit de section (`INSTRUCTIONS_STYLE_PROJET` §2) ; voir §3 ci-dessous.

---

## 1. La thèse

C'est un ouvrage **pratique**, pas un ouvrage de mathématiques. Les maths n'en sont pas absentes, mais elles sont rendues **franchissables par la visualisation** : courbes, schémas, analogies dans le texte. Un lecteur non mathématicien doit pouvoir tout suivre, sans rien manquer de l'essentiel.

Le moyen d'y parvenir n'est pas d'illustrer les formules après coup. C'est de **rejouer l'ordre dans lequel l'outil a été inventé.**

Un chercheur ne commence jamais par griffonner une formule. Il se demande d'abord : *quelle part de l'information je veux valoriser, quelle part je veux éteindre ?* Puis il cherche, dans ses outils, la **forme de courbe** qui réalise cette intention — quelque chose qui écrase ici, amplifie là, sature au bon endroit. La formule vient en **dernier** : elle est la transcription d'une courbe déjà choisie, pas un axiome posé d'emblée.

Les manuels inversent cet ordre : formule d'abord, justification ensuite, illustration parfois. Le lecteur reçoit la réponse sans avoir vécu la question. **Le livre fait l'inverse de l'inverse : il restitue l'ordre génétique.** Quand la formule arrive, elle était attendue, presque devinable — le lecteur a parcouru le chemin de celui qui l'a composée.

C'est le prolongement direct du méta-fil de l'ouvrage (« le bon cadre rend le problème presque résolu ») : choisir la forme de la courbe *avant* la formule, c'est choisir le cadre où le problème est déjà à moitié résolu.

---

## 2. Les trois temps d'une section

L'ordre canonique d'exposition d'une formule :

1. **L'intention.** Quel problème d'information ? Qu'est-ce qu'on cherche à faire ressortir, qu'est-ce qu'on veut faire taire ? Posé **en mots, sans formule.**
2. **La forme recherchée.** Quelle allure de courbe (ou de comportement) ferait ce travail ? Elle doit écraser telle zone, amplifier telle autre, plafonner au bout. **On la décrit et, presque toujours, on la montre** : c'est la lecture de la courbe dans son repère qui fait comprendre instinctivement ce qu'on conserve et ce qu'on essaie de faire disparaître. Cette étape puise dans le **réservoir de formes de l'annexe C** (§2bis) : si la forme y figure déjà, on y renvoie au lieu de la réexpliquer.
3. **La formule.** Voici l'expression qui produit cette courbe. Elle arrive comme la mise en notation de ce qu'on vient de comprendre.

Puis on enchaîne comme avant : exemple chiffré, vocabulaire technique attaché, limites, code.

**Exemple de la voix visée** (factice) :
> « Ici, le logarithme augmente le poids des valeurs qui tombent dans la fourchette utile — les vrais positifs — et réduit à presque rien le bruit résiduel. »

On ne démontre pas pourquoi le log a cette propriété : on dit ce qu'il **fait**, et la courbe le donne à voir — la portion tassée près de l'origine, la portion étirée plus loin. La courbe ne décore pas la démonstration : **elle la remplace.**

### Portée du renversement

Le renversement est **littéral** pour les fonctions de réponse — coûts, log, sigmoïde, noyaux, pondérations, estimateurs robustes (Huber, Tukey). Là, « valoriser ceci / éteindre cela » et la courbe *sont* le sujet.

Pour les objets qui ne sont pas d'abord des courbes — une transformée, une homographie, une métrique de segmentation — l'**esprit reste le même** (partir de l'intention, de ce qu'on cherche à faire), mais l'incarnation n'est pas une courbe : c'est une forme géométrique, un comportement, une invariance visée. On ne force pas une courbe là où l'objet n'en est pas une ; on garde le geste « intention → forme → expression » sous la forme que l'objet appelle.

---

## 2bis. Le réservoir de formes (annexe C)

L'étape 2 d'une section — montrer la forme de courbe visée — **ne repart pas de zéro**. L'annexe C est la bibliothèque des **atomes visuels** du livre : une vignette par forme élémentaire, qui nomme l'intention puis la donne à lire sur la courbe (« log compresse les échelles, chaque ×10 vaut +1 marche » ; « σ, interrupteur doux » ; « x² amplifie les écarts » ; « a/b, mise en proportion, le rapport efface la taille » ; etc.). C'est exactement le coffre où le chercheur pioche pour composer une formule.

Trois règles d'usage :

1. **Le renvoi va du chapitre vers l'annexe, jamais l'inverse.** Quand le corps emploie une forme déjà en annexe, il y renvoie d'une ligne (« voir la forme *log*, annexe C ») plutôt que de réexpliquer la courbe. L'image, vue une fois, revient à chaque emploi — c'est tout l'intérêt d'avoir fabriqué ces atomes : ils s'amortissent sur l'ensemble de l'ouvrage. C'est le geste « renvoi d'une ligne » de `NOTE_STYLE_DEGRAISSAGE`.
2. **Les vignettes restent génériques.** Une vignette dit une forme pure ; on ne la leste pas d'une liste « utilisée aux chapitres 1, 3, 15 ». Un répertoire de formes fonctionne comme un glossaire ou un index de notation : on renvoie *vers* lui, il ne renvoie pas *vers* le texte. Léger, robuste, sans dette de maintenance quand un nouveau chapitre réutilise la forme.
3. **Les exemples d'une vignette sont illustratifs, pas limitatifs.** La vignette `a/b` cite `C = 4π·A / P²` comme *un* cas de « proportion qui efface la taille » — pas comme son seul usage. Le chapitre 1 développe alors la circularité pour elle-même, avec son angle mort (elle confond deux causes), et renvoie à la forme `a/b` pour l'intuition. L'annexe donne la forme ; le chapitre donne le cas précis et ses pièges. Aucune duplication.

Deux familles d'appui visuel coexistent et se complètent : les **courbes** de l'annexe C portent le quantitatif (ce qu'on conserve, ce qu'on éteint) ; les **illustrations au trait** (images mentales situées — l'inspecteur qui mesure, la file de gens alignés) portent l'intuition incarnée. Une section puise dans l'une, l'autre, ou les deux, selon ce que la formule appelle.

---

## 3. Amendement au gabarit (`INSTRUCTIONS_STYLE_PROJET` §2)

Le gabarit actuel impose, dans chaque section, l'étape **« Dérivation ou justification mathématique »**. Cette étape est **remplacée**. Les démonstrations sortent du corps.

**Ancien ordre de section :**
définition → *dérivation* → ce que ça mesure → exemple → piège → code

**Nouvel ordre de section :**
intention (en mots) → forme/courbe visée (montrée) → **formule** → ce qu'elle fait → exemple chiffré → limites → code

Règle sur l'algèbre : **pas de démonstration dans le corps du texte.** On ne conserve que le nécessaire. Une dérivation qui a un intérêt pour le lecteur curieux **descend en annexe maths** ; une dérivation de service **disparaît**. Le corps garde l'énoncé de la formule et l'explication, en langue naturelle, de ce qu'elle produit. (Le terme « dérivation » dans le titre de chapitre et au §4 des instructions se lit désormais comme « cheminement » au sens intention→forme→formule, jamais comme démonstration.)

Ce qui reste **intact** dans le gabarit : exemple numérique chiffré, vocabulaire technique, limites, code Python, tableau récapitulatif, encadré final, renvois croisés.

---

## 4. La métaphore — véhicule du vocabulaire, jamais son substitut

L'analogie est un **outil pédagogique central**, pas un ornement à rationner. Elle peut revenir autant que le concept le demande. Une seule contrainte, mais absolue :

**Le terme technique est présent en toutes circonstances. La métaphore lui reste attelée à chaque retour.**

Le défaut à traquer n'est donc **pas** l'image répétée — c'est l'**image orpheline du vocabulaire**. Une métaphore qui revient sans son terme apprend au lecteur à dire « film plastique » et non « enveloppe convexe » : c'est elle qu'on corrige, en réattachant le mot juste.

### Avant / après — la solidité (§1.4)

**Avant** (« film plastique » seul, 5 fois) :
> Le film plastique va s'appuyer sur les parties saillantes… la surface enfermée sous ce film plastique… l'objet touche le plastique partout…

**Après** (l'image attelée au terme) :
> L'**enveloppe convexe** — cette pellicule qu'on tendrait autour de l'objet — s'appuie sur les parties saillantes et passe au-dessus des creux sans y entrer. La solidité compare l'aire réelle à celle de cette enveloppe : sans creux, S = 1 ; plus les cavités sont profondes, plus S chute.

L'image revient si besoin (« la même enveloppe convexe, toujours tendue par-dessus les creux »), mais le terme l'accompagne. Le lecteur garde l'image **et** acquiert le mot.

Analogies établies, chacune toujours liée à son terme : pellicule → enveloppe convexe ; diapason → échelle caractéristique ; façade → invariance de rotation (SIFT) ; clé/serrure → test du ratio ; cartes joker → nombre d'itérations RANSAC ; gouttes de pluie → bruit de grenaille ; rééquilibrer une balance → normalisation ; relire avec une question → attention ; courbe élastique → contour actif (snake).

---

## 5. Le ton — guider, pas surveiller

Trois corrections de forme, signalées en relecture externe. Aucune ne touche au fond ni à la visualisation ; toutes retirent à la voix sa posture de surveillant.

### 5.1 Dédramatiser « Piège »

« Piège » (59 occurrences, dont ~30 en titres et en table des matières) sonne comme une alarme. Le mot n'est pas interdit, il est **rationné** : on le garde quand le lecteur risque vraiment un **résultat faux** sans le savoir (mauvaise convention d'axes, `.sum()` sur un masque 0/255, matrice singulière silencieuse). Partout ailleurs :

| Nature réelle | Étiquette |
|---|---|
| Résultat **faux** si ignoré | **Piège** (conservé) |
| Contre-intuitif mais non fautif | **Subtilité** / **À noter** |
| Borne de validité | **Limite** / **Domaine de validité** |
| Écart entre bibliothèques/versions | **Différence d'implémentation** |
| Réglage sensible (σ, seuil, tolérance) | **Réglage** / **Sensibilité** |

Dans les **titres** : « 2.5. Piège : en image, y descend » → « 2.5. En image, l'axe y descend ». Le titre nomme le phénomène ; il ne crie pas. **À conserver** : les angles morts chiffrés (périmètre +27 %, ±50 % sur Hu pour 2 px) — ce sont les meilleures pages ; seule l'étiquette change.

### 5.2 Renoncer à l'impératif

Test mécanique : toute phrase ouvrant sur « Il est impératif de », « Il faut », « Veillez à », « Vous devez », « On doit toujours », ou « Attention : » en tête, est à réécrire en **constat**.

| Avant (injonction) | Après (constat) |
|---|---|
| « …sans garantie d'ordre. Il est impératif de trier manuellement. » | « …renvoie les dimensions dans un ordre quelconque : un tri explicite est nécessaire avant de s'en servir. » |
| « Il faut être très vigilant avec les trous internes. » | « Les trous entièrement internes (l'intérieur d'un anneau) sont comptés ou non selon la bibliothèque. » |
| « Attention : `cvtColor` renvoie L dans [0, 255]. » | « `cvtColor` renvoie L dans [0, 255], et non [0, 100] : … » |

On décrit le fait ; le lecteur en tire la conduite.

### 5.3 Pas de leçon de morale en bas de page

La chute d'un chapitre ne sermonne pas. **Test de l'aphorisme** : si la phrase finale pourrait s'imprimer seule sur une affiche (« choisir une distance, c'est déclarer ce qui compte »), elle sermonne — on la fond dans le raisonnement ou on la coupe. Ce qui doit rester en bas de chapitre, c'est le **renvoi croisé concret** (« le chapitre 6 retrouvera cette amplification du bruit »), pas la formule frappante. On garde **un** atterrissage net par chapitre ; on supprime sa version sentencieuse et redondante (cf. `NOTE_STYLE_DEGRAISSAGE` §6).

---

## 6. Protocole de révision (par chapitre)

1. **Ré-ordonner chaque section** selon §2 : l'intention et la forme/courbe visée passent **avant** la formule. La démonstration sort (annexe ou suppression, §3).
2. **Vérifier l'appui visuel** sur chaque idée mathématique structurante du corps : une courbe lue, un schéma, ou une explication instinctive de ce que la formule fait. Si la forme figure déjà à l'annexe C, **renvoyer vers elle** plutôt que de la réexpliquer (§2bis). Le calcul de service peut rester nu ou descendre en annexe.
3. **Métaphores** : repérer toute image apparaissant **sans** son terme technique ; réattacher le mot juste (§4). Ne pas chasser la répétition en soi.
4. **Titres et étiquettes** : retirer « Piège : » des en-têtes sauf danger de résultat faux ; reclasser les blocs (§5.1). Répercuter dans la table des matières.
5. **Impératifs** : rechercher « impérati / il faut / veillez / vous devez / Attention » ; réécrire en constat (§5.2).
6. **Chutes** : appliquer le test de l'aphorisme ; garder le renvoi croisé concret (§5.3).

---

## 7. Ce qui ne bouge pas

Le contenu scientifique, les exemples chiffrés, le code, les angles morts quantifiés, la structure de chapitre hors gabarit amendé, le vouvoiement, les renvois croisés. Le but n'est pas d'aplatir la voix de l'auteur : c'est de lui retirer la cravate de surveillant et de remettre la pensée dans son ordre naturel — l'intention, puis la forme, puis la formule.
