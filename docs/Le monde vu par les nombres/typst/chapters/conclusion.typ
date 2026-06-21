#import "@preview/bookly:4.0.0": *

// --- Helpers locaux ---
#let subtitle(t) = block(above: 0.2em, below: 1.2em, sticky: true)[#text(style: "italic", fill: rgb("#64748b"))[#t]]

#let figtodo(id, desc) = figure(
  block(width: 100%, inset: 14pt, radius: 6pt,
    fill: luma(246), stroke: (dash: "dashed", thickness: 0.8pt, paint: luma(170)))[
    #align(center)[#text(fill: luma(110), style: "italic", size: 0.9em)[
      Figure à créer — #raw(id)\
      #desc
    ]]
  ]
)

#let figfull(path) = block(above: 1em, below: 1.4em, width: 100%)[#image(path, width: 100%)]
#let canvas(body) = tip-box(title: "Dans VNStudio")[#body]

#v(2em)
#block(breakable: false)[
  #text(size: 2.2em, weight: "bold", fill: rgb("#1e293b"), font: "Roboto")[Du formulaire au jugement]
  #v(0.4em)
  #line(length: 100%, stroke: 1.5pt + rgb("#c1002a"))
]
#v(1.5em)

Dix-sept chapitres durant, une même phrase est revenue, à peine déguisée : tout choix de représentation encode une hypothèse sur ce qui compte. Elle a clos chaque encadré, et la fin du livre l'a énoncée presque en entier — voir, c'est décider ce à quoi l'on accorde de l'importance. Cette conclusion ne la répétera pas. Un refrain n'est pas une démonstration, et l'idée mérite mieux qu'une dernière récitation : qu'on la prenne au sérieux comme une thèse, qu'on la pousse jusqu'à ses conséquences — y compris celles que l'apprentissage profond semble lui opposer — et qu'on dise enfin ce qu'un formulaire, par construction, ne peut pas donner.

== L'angle mort n'est pas un défaut : c'est la condition de voir


Chaque chapitre a comporté une rubrique « angle mort ». On l'a lue chapitre après chapitre comme une honnêteté de praticien : voici ce que l'outil ne voit pas, prenez garde. Mais relus ensemble, ces aveux dessinent autre chose qu'une liste de limitations. Ils disent que l'angle mort n'est pas le prix accidentel d'un outil imparfait — c'est la condition même pour qu'il y ait quelque chose à voir.

La preuve la plus nette est venue de la texture (chapitre 13). L'invariance qu'un descripteur récolte — à la position, à l'éclairage, à la rotation — est exactement l'information qu'il a délibérément jetée. Le LBP achète l'invariance à l'illumination en ne gardant que le signe des différences ; la magnitude de Gabor achète l'invariance de position en oubliant la phase ; la GLCM moyennée achète l'invariance directionnelle en effaçant l'angle. Être invariant à quelque chose, c'est en être aveugle, volontairement. Il n'y a pas d'invariance gratuite : chacune se paie d'une cécité choisie.

Ce que la texture rend visible, tout le livre le pratiquait sans le nommer. Une distance (chapitre 3) déclare ce qui rapproche deux points en décrétant indifférentes les différences qu'elle ne mesure pas. Les moments de Hu (chapitre 2) reconnaissent une forme à toute orientation parce qu'ils ont effacé l'orientation. Une caméra (chapitre 8) encode la scène en sacrifiant la profondeur — et toute la stéréovision n'est que l'art de récupérer ce que la projection a consenti à perdre. CIELAB (chapitre 7) ne mesure si bien les écarts perceptuels que parce qu'il a renoncé à l'arithmétique du capteur. Dans chaque cas, l'utilité naît du renoncement.

La limite de ce raisonnement en éclaire le sens. Une représentation qui n'omettrait rien existe : c'est l'image brute elle-même, le tableau de pixels. Elle ne distingue rien, ne mesure rien, ne décide rien — précisément parce qu'elle n'a renoncé à rien. Décrire, mesurer, segmenter, reconnaître : ces gestes commencent tous au moment où l'on accepte de perdre une part du signal pour faire ressortir le reste. L'angle mort n'est donc pas le défaut du formulaire ; c'est l'autre nom de ce qu'il sait faire.

== Le même geste, lu à l'endroit


On peut maintenant relire le livre dans le sens de la lecture, et voir une seule idée se rhabiller de chapitre en chapitre. Les premiers chapitres apprennent à _décrire_ : un descripteur choisit ce qu'il voit et ce qu'il oublie (chapitre 1), un moment regarde d'autant plus loin du centroïde qu'il amplifie le bruit (chapitre 2). Vient le temps de _comparer_ : une distance déclare ce qui compte (chapitre 3), et aucune métrique de segmentation ne capture tout à elle seule (chapitre 4). Puis de _traiter_ : un filtre est un a priori sur le signal (chapitre 5), et dériver oblige à doser lissage et dérivation parce que la dérivée amplifie le bruit (chapitre 6). Puis de _représenter l'espace_ : pas d'espace colorimétrique vrai, seulement des espaces adaptés à un usage (chapitre 7) ; une caméra linéarise au prix d'une perte (chapitre 8). Puis d'_inférer sous incertitude_ : un problème mal posé ne se résout qu'en ajoutant un a priori aux données insuffisantes (chapitre 9), et changer de base, c'est choisir où le problème devient simple (chapitre 10).

La seconde moitié pousse le même geste plus loin encore. Tester si une forme tient, c'est déclarer quelle géométrie mérite d'être vue (chapitre 11). Le curseur λ d'une segmentation rend littéral l'arbitrage entre fidélité aux données et régularité (chapitre 12). Une texture n'est pas une valeur mais une relation que l'on choisit d'interroger (chapitre 13). Une métrique de qualité est un observateur déguisé, qui ne punit que ce qu'il perçoit (chapitre 14). Un coût fabrique la pente qui mène à la cible (chapitre 15). Et un estimateur robuste déclare, à l'avance, ce qu'il refuse de croire (chapitre 16). Enfin, retrouver le même point du monde dans deux images, c'est ne garder que l'invariance qu'on s'autorise — ce qui ne change ni avec la lumière, ni avec l'angle (chapitre 17).

Énoncés à la file, ces fils ne forment pas dix-sept idées : ils forment une phrase, dite dix-sept fois dans dix-sept langages. Le bon cadre rend le problème presque résolu — et le cadre, à chaque fois, est une hypothèse sur ce qui compte.

== Là où l'hypothèse se déplace : du formulaire à l'appris


Une objection s'impose, que chaque chapitre a effleurée sans la traiter de front : l'apprentissage profond domine aujourd'hui la plupart de ces tâches. Les descripteurs appris surpassent Hu, RAFT bat Horn-Schunck sur le flot, U-Net et SAM relèguent le seuillage et le graph cut au rang de post-traitement, LPIPS prédit le jugement humain mieux que SSIM. Si la machine apprend seule la bonne représentation, le geste que ce livre décrit — choisir à la main ce qui compte — n'est-il pas périmé ?

La réponse est que l'apprentissage n'abolit pas ce choix : il le déplace. L'hypothèse ne disparaît pas, elle change de lieu. Là où le praticien posait une formule, le réseau pose une architecture, un coût et des données — et chacun de ces trois éléments est une hypothèse, simplement devenue implicite.

L'architecture, d'abord. Une couche de convolution n'est pas neutre : c'est l'a priori d'invariance par translation, le même que le chapitre 5 nommait, câblé dans le réseau avant qu'il ait vu une seule image. Le pooling bilinéaire qui sert aujourd'hui à classer les textures est l'héritier direct de la cooccurrence du chapitre 13 ; les scattering transforms sont cousines du banc de Gabor. Le réseau n'a pas inventé un regard sans hypothèse — il a hérité des nôtres et les a rendues profondes.

Le coût, ensuite. Le chapitre 15 a montré qu'une fonction de coût n'est rien d'autre qu'une déclaration de ce qui constitue une erreur, transformée en pente. Choisir une entropie croisée plutôt qu'un Dice, une perte L1 plutôt qu'une L2, c'est exactement le même acte qu'un estimateur robuste qui borne le poids d'une observation (chapitre 16) : décider, avant d'apprendre, ce qui mérite d'être corrigé et ce qu'on tolère. Le réseau optimise ce qu'on lui a dit de craindre.

Les données, enfin, et le cas le plus révélateur. LPIPS (chapitre 14) ne s'évade pas de l'observateur : il l'ajuste. Là où SSIM codait à la main une approximation du système visuel humain, LPIPS apprend cette approximation sur des jugements humains réels. L'observateur n'a pas disparu de la métrique — il a cessé d'être déclaré pour devenir appris. C'est tout l'écart entre les deux mondes : l'hypothèse passe de l'explicite à l'implicite, du lisible au tacite. Elle devient plus puissante et plus difficile à inspecter en même temps.

D'où la place exacte du formulaire à l'âge des réseaux. Il ne concurrence pas l'apprentissage ; il en fournit le vocabulaire. Comprendre qu'une couche convolutive est un a priori, qu'un coût est une déclaration, qu'une augmentation de données est une invariance imposée — c'est lire à voix haute les hypothèses que le réseau garde sous silence. Les méthodes classiques, par ailleurs, ne disparaissent pas : sans données d'entraînement, interprétables, légères, elles restent imbattables sur les problèmes contraints, et survivent à l'intérieur même des pipelines profonds — une matrice de Gram au cœur du transfert de style, un CRF dense raffinant une sortie de segmentation, la morphologie nettoyant des masques qu'aucun réseau ne garantit. L'outil change ; la question reste la même.

== Ce qu'un formulaire ne peut pas écrire : le jugement


Il faut alors avouer la limite de cet ouvrage, et elle est de taille. Pour chaque formule, on a donné la dérivation, l'exemple chiffré, le piège, le code. On a tout donné — sauf la seule chose qui décide vraiment du résultat : quel cadre adopter pour l'image qu'on a réellement devant soi.

Aucune méta-formule ne choisit la formule. Rien dans le livre ne dit s'il faut, pour cette tâche-ci, un seuillage d'Otsu ou un graph cut, un σ de 1 ou de 5, une distance euclidienne ou une divergence, un estimateur des moindres carrés ou un M-estimateur. Ce choix dépend du signal, du bruit, de la tolérance à l'erreur, du coût d'un faux positif contre un faux négatif — bref, de tout ce que le formulaire ne connaît pas et que seul connaît celui qui regarde l'image. Le formulaire est une carte des cadres possibles ; il n'est pas la décision.

C'est exactement pourquoi ce livre a fait passer l'intuition avant la dérivation. Une formule apprise sans son intuition ne s'applique qu'aux cas pour lesquels on l'a vue appliquer ; comprise dans son pourquoi, elle se transporte aux cas qu'on n'a jamais rencontrés. La dérivation, le code, l'exemple servaient à une seule fin : armer le jugement, cette part irréductible qu'aucune table récapitulative ne contient. Le formulaire ne dispense pas de décider — il rend la décision lucide.

== Envoi — le livre est lui-même un descripteur


Le premier chapitre l'affirmait : un descripteur choisit ce qu'il voit et ce qu'il oublie. Ce livre est lui-même un descripteur. Dix-sept sections retenues, et beaucoup d'autres laissées de côté ; des familles entières d'outils réduites à une note, des architectures à peine nommées. Cette table des matières encode une hypothèse — la sienne — sur ce qui compte. Et l'hypothèse n'était pas de couvrir l'état de l'art le plus récent, qui aura changé avant qu'on ait fini de l'écrire, mais de transmettre ce qui se garde longtemps : non pas le dernier modèle, mais l'habitude durable de demander ce que chaque représentation suppose.

C'est cette habitude qui survit à un changement d'outils, de poste, de décennie. Les formules de ce livre vieilliront, certaines plus vite qu'on ne le croit. La question qu'elles enseignent — qu'est-ce que ce cadre déclare important, et qu'est-ce qu'il accepte de ne pas voir ? — ne vieillira pas. On reviendra à ce formulaire non pour réviser un examen, mais parce qu'on butera sur une image réelle, un cas que personne n'avait prévu, et qu'il faudra, une fois de plus, choisir le bon cadre. Ce jour-là, le livre n'aura pas pour rôle de fournir la réponse, mais de rappeler comment se pose la question.

Voir n'a jamais été enregistrer ce qui est là. Voir, c'est décider ce à quoi l'on accorde de l'importance — et ce à quoi l'on n'en accorde pas. Tout le reste, distances, filtres, descripteurs, bases, coûts, estimateurs, n'est qu'une manière de plus en plus fine de prendre cette décision. Le formulaire en donne les outils. La décision, elle, vous appartient.

∎
