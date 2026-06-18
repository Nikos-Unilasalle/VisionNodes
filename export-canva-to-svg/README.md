# Export `.vn` → SVG — schémas de nœuds vectoriels (mono rose)

Convertit une scène VNStudio en schéma **propre et vectoriel**, sans capturer le
DOM (donc sans previews ni thème sombre). Une seule spec visuelle, deux moteurs
identiques : **TypeScript** dans l'app, **Python** pour le livre / la CI.

## Fichiers

| Fichier | Rôle |
|---|---|
| `vnToSvg.ts` | Cœur du rendu (scène + registre → string SVG). Aucune dépendance. |
| `exportSvg.ts` | Action Tauri v2 (save SVG/PNG) + adaptateur ReactFlow. |
| `ExportSvgButton.tsx` | Exemple de bouton toolbar + raccourci `Cmd+Shift+E`. |
| `vn_to_svg.py` | Référence Python : `.vn` + node-defs → SVG (batch livre/CI). |
| `vnfig.py` | Générateur « à la main » pour figures non issues d'un vrai `.vn`. |

## Intégration dans l'app (3 étapes)

1. Copier `vnToSvg.ts` et `exportSvg.ts` dans `src/`.
2. `npm i @tauri-apps/plugin-dialog @tauri-apps/plugin-fs` et autoriser
   `dialog:allow-save` + `fs:allow-write-file` dans les capabilities Tauri.
3. Brancher `ExportSvgButton` dans la toolbar. Remplacer `useNodeRegistry()` par
   votre store de registre réel (celui qui alimente le menu d'ajout `Cmd+M`).

C'est tout : « Export SVG » apparaît, l'utilisateur sauvegarde un schéma propre de
sa scène (ou de sa sélection).

## Le seul prérequis : le registre de nœuds

Le rendu a besoin, pour chaque `type`, de `{ label, inputs[], outputs[] }` où
chaque port porte `{ id, color }`. Le front **possède déjà** cette info (sinon il
ne saurait pas dessiner les ports ReactFlow). On la lui demande via `getNodeDef`,
on ne duplique rien.

> Les `.vn` ne stockent pas toujours les ports ; ils viennent du registre
> (décorateur `@vision_node`). D'où le passage explicite du registre, et non une
> lecture du seul JSON.

## Convention visuelle (mono-teinte)

Pour rester en monoculture rose **tout en gardant l'info de type**, le type de port
est encodé par la **forme**, pas la couleur :

| Type (couleur VNStudio) | Forme | Type | Forme |
|---|---|---|---|
| `image` | disque plein | `dict` | carré creux |
| `mask` | anneau | `list` | losange creux |
| `scalar` | carré plein | `any` | cercle annelé |
| `string` | losange plein | `flow` | triangle (+ arête pointillée) |

Palette unique dans `PALETTE` (un seul endroit, `vnToSvg.ts` **et** `vn_to_svg.py`
en miroir — gardez-les synchronisés, ou générez l'un depuis un JSON partagé).

## Usage livre / CI (Python)

```bash
# scene.vn + defs.json (export ponctuel du registre) → scene.svg
python3 vn_to_svg.py scene.vn defs.json "Titre de la figure"
# puis, pour l'impression :
python3 -c "import cairosvg; cairosvg.svg2pdf(url='scene.svg', write_to='scene.pdf')"
```

Vous pouvez ainsi régénérer **toutes** les figures du livre depuis les `.vn`
réels : elles restent synchronisées avec les pipelines, zéro re-dessin.

## Notes

- **PDF dans l'app** : la rasterisation PNG se fait en webview (canvas) ; pour du
  PDF vectoriel, passez par le script Python/CLI (chaîne d'impression du livre).
- **Sélection** : si des nœuds sont sélectionnés, seul le sous-graphe est exporté.
- Béziers calqués sur `getBezierPath` de ReactFlow → tracé identique à l'écran.
