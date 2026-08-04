"""List → DataFrame.

Turns one or more recorded series into a table, so the DataFrame nodes — plot,
stats, filter, export — can work on them. Collect and the Signal filters output
`list`; everything downstream in the DataFrame family expects `data`. This node
is the missing link between the two.

Extra inputs appear as you connect them: every connected list becomes a column,
named after its port. Lists of different lengths are padded rather than dropped,
so a wiring mistake is visible instead of silent.
"""
import numpy as np

from registry import vision_node, NodeProcessor, send_notification

_NOTIF = 'df_from_list'

try:
    import pandas as pd
    _PD_OK = True
except ImportError:
    pd = None  # type: ignore[assignment]
    _PD_OK = False

# Ports that carry engine plumbing rather than a series to plot.
_RESERVED = {'raw_frame', 'img_size'}


def _to_column(v):
    """Flat list of Python floats/values from a list, tuple or numpy array."""
    if isinstance(v, np.ndarray):
        return [float(x) for x in v.ravel()]
    if isinstance(v, (list, tuple)):
        out = []
        for x in v:
            if isinstance(x, (np.integer, np.floating)):
                out.append(float(x))
            elif isinstance(x, np.ndarray):
                out.append(float(x.flat[0]) if x.size else None)
            else:
                out.append(x)
        return out
    return None


def _df_meta(df) -> dict:
    """Same shape as the other DataFrame nodes — the inspector reads this."""
    def _ser(v):
        if isinstance(v, float) and v != v:
            return None
        if isinstance(v, np.integer):
            return int(v)
        if isinstance(v, (float, np.floating)):
            return float(v)
        if isinstance(v, int):
            return v
        return str(v)

    r, c = df.shape
    return {
        'shape': [r, c],
        'columns': [str(col) for col in df.columns],
        'dtypes': {str(col): str(df[col].dtype) for col in df.columns},
        'nulls': {str(col): int(df[col].isna().sum()) for col in df.columns},
        'head': [{str(k): _ser(v) for k, v in row.items()}
                 for _, row in df.head(8).iterrows()],
    }


@vision_node(
    type_id='df_from_list',
    label='List → DataFrame',
    category='DataFrame',
    icon='Table2',
    description="Builds a table from one or more lists — one column per connected input. "
                "Optionally adds a frame index and a time column, so a recorded series can "
                "be plotted against seconds rather than sample number.",
    inputs=[{'id': 'list', 'color': 'list', 'label': 'List'}],
    outputs=[
        {'id': 'table',   'color': 'data', 'label': 'DataFrame'},
        {'id': 'df_meta', 'color': 'dict', 'label': 'DF Metadata'},
        {'id': 'rows',    'color': 'scalar', 'label': 'Rows'},
    ],
    params=[
        {'id': 'name', 'label': 'Column names (comma-separated)', 'type': 'string',
         'default': 'valeur'},
        {'id': 'add_index', 'label': 'Add frame index', 'type': 'bool', 'default': True},
        {'id': 'fps', 'label': 'Time column at N fps (0 = none)', 'type': 'int',
         'default': 0, 'min': 0, 'max': 240},
    ],
    dynamic_inputs=True,
)
class ListToDataFrameNode(NodeProcessor):
    def __init__(self):
        self._signature = None
        self._sortie = None

    @staticmethod
    def _signature_contenu(colonnes, params):
        """Empreinte bon marche du contenu, pour ne pas refabriquer a l'identique.

        Le cache du moteur compare les entrees par `id()`. Collect renvoie une COPIE
        de sa liste a chaque image : l'identite change donc en permanence, meme quand
        la serie n'a pas bouge d'un iota. Sans l'empreinte ci-dessous, cette node
        reconstruirait son tableau a chaque tick, et tout ce qui la suit — un trace
        matplotlib de plusieurs milliers de points, plus de 100 ms — serait recalcule
        30 fois par seconde pour rien. L'interface se fige, sans le moindre message.
        """
        emp = []
        for cle in sorted(colonnes):
            v = colonnes[cle]
            n = len(v)
            pas = max(1, n // 32)
            emp.append((cle, n, tuple(v[::pas][:32]), v[-1] if n else None))
        return (tuple(emp), str(sorted(params.items())))

    def process(self, inputs, params):
        if not _PD_OK:
            send_notification("List → DataFrame: pandas not installed",
                              level='error', notif_id=_NOTIF)
            return {}

        # Les ports dynamiques sont nommes par le frontend « couleur__<index>_<alea> » ;
        # le moteur n'en garde que la partie apres le double souligne, du genre
        # « 0_a3f9 ». Ce n'est pas un identifiant Python valide : filtrer la-dessus
        # revenait a ne garder que le port de base, donc une seule colonne.
        brutes = {}
        for cle, val in inputs.items():
            if cle in _RESERVED:
                continue
            col = _to_column(val)
            if col:
                brutes[cle] = col

        if not brutes:
            send_notification("List → DataFrame: no list connected",
                              level='warning', notif_id=_NOTIF)
            return {}

        # Les noms sont donnes dans l'ordre de branchement : « brut, lisse » nomme la
        # premiere colonne brut et la seconde lisse. Ce qui n'est pas nomme retombe
        # sur le nom du port quand il est lisible, sinon sur serie_N.
        demandes = [s.strip() for s in str(params.get('name', 'valeur')).split(',') if s.strip()]

        # Ordre stable : les ports dynamiques portent un suffixe aleatoire, donc on
        # les trie pour que deux executions donnent les memes colonnes.
        ordre = (['list'] if 'list' in brutes else []) + sorted(k for k in brutes if k != 'list')

        colonnes = {}
        for i, cle in enumerate(ordre):
            if i < len(demandes):
                propre = demandes[i]
            elif str(cle).isidentifier() and cle != 'list':
                propre = str(cle)
            else:
                propre = f"serie_{i + 1}"
            while propre in colonnes:
                propre += "_"
            colonnes[propre] = brutes[cle]

        n = max(len(v) for v in colonnes.values())
        if len({len(v) for v in colonnes.values()}) > 1:
            send_notification(
                f"List → DataFrame: lists of different lengths, padded to {n}",
                level='warning', notif_id=_NOTIF)
            colonnes = {k: v + [None] * (n - len(v)) for k, v in colonnes.items()}

        # L'index et le temps viennent en premier : c'est l'axe des x naturel.
        tete = {}
        if bool(int(params.get('add_index', 1))):
            tete['image'] = list(range(n))
        fps = int(params.get('fps', 0))
        if fps > 0:
            tete['temps'] = [i / float(fps) for i in range(n)]

        signature = self._signature_contenu({**tete, **colonnes}, params)
        if signature == self._signature and self._sortie is not None:
            return self._sortie

        try:
            df = pd.DataFrame({**tete, **colonnes})
        except Exception as e:
            send_notification(f"List → DataFrame: could not build ({e})",
                              level='error', notif_id=_NOTIF)
            return {}

        send_notification(f"List → DataFrame: {df.shape[0]}×{df.shape[1]}",
                          level='info', notif_id=_NOTIF)
        self._signature = signature
        self._sortie = {'table': df, 'df_meta': _df_meta(df), 'rows': float(df.shape[0])}
        return self._sortie
