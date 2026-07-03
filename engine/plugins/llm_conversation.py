"""
LLM — one or two AI personas. Single persona = simple Q&A assistant.
Two personas = dialogue/debate for N turns.

A single orchestrator (the engine is a DAG; the bounded loop lives inside
process(), not as a graph cycle). Uses _llm_shared/providers.py for all
provider logic. API keys are persisted in ~/.vnstudio/secrets.json.
"""
from registry import vision_node, NodeProcessor, send_notification
import registry
import os
import importlib.util

_PROV_PATH = os.path.join(os.path.dirname(__file__), '_llm_shared', 'providers.py')
_spec = importlib.util.spec_from_file_location('_llm_providers', _PROV_PATH)
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)

_NOTIF_ID = 'llm_conversation'

# Ollama keep_alive values, indexed by the 'keep_alive' enum (UI stores the
# integer index, not the label — read by position, never by string).
_KEEP_ALIVE = ['5m', '30m', '1h', '-1', '0']

_LIB_PREAMBLE = (
    "You are assisting inside VNStudio, a node-based computer-vision studio. "
    "Below is the catalog of ALL available nodes (type_id, label, inputs and "
    "outputs as id:color, and a short description). When suggesting a pipeline, "
    "compose these existing nodes, refer to them by their type_id, and wire an "
    "output color to an input of the same color. Do NOT invent nodes that are "
    "not in this list.\n\n=== NODE CATALOG ===\n"
)


_LIB_CACHE: dict = {'n': -1, 'text': ''}


def _build_node_library() -> str:
    """Compact catalog of every registered node from the live registry
    (NODE_SCHEMAS), grouped by category:
        `- type_id (label): in[id:color, …] out[…] — description`

    Memoised on the node count: built once per session (~1 ms for ~450 nodes),
    reused on every Run, and only rebuilt if the registry size changes. There is
    no hot-reload, so within a session the count is stable; a restart that adds a
    plugin invalidates the cache automatically without touching this code."""
    n = len(registry.NODE_SCHEMAS)
    if n == _LIB_CACHE['n']:
        return _LIB_CACHE['text']

    def _io(lst) -> str:
        return ', '.join(f"{p.get('id')}:{p.get('color')}" for p in (lst or [])) or '—'
    by_cat: dict = {}
    for s in registry.NODE_SCHEMAS:
        by_cat.setdefault(s.get('category') or 'other', []).append(s)
    lines: list = []
    for cat in sorted(by_cat):
        lines.append(f"\n## {cat}")
        for s in sorted(by_cat[cat], key=lambda x: x.get('type', '')):
            desc = ' '.join((s.get('description') or '').split())
            line = (f"- {s.get('type')} ({s.get('label')}): "
                    f"in[{_io(s.get('inputs'))}] out[{_io(s.get('outputs'))}]")
            if desc:
                line += f" — {desc}"
            lines.append(line)
    text = '\n'.join(lines)
    _LIB_CACHE['n'], _LIB_CACHE['text'] = n, text
    return text


def _build_history(transcript: list, speaker: str, system_prompt: str, opening: str) -> list:
    history = []
    if system_prompt:
        history.append({'role': 'system', 'content': system_prompt})
    if opening:
        history.append({'role': 'user', 'content': opening})
    for turn in transcript:
        role = 'assistant' if turn['speaker'] == speaker else 'user'
        history.append({'role': role, 'content': turn['text']})
    return history


@vision_node(
    type_id='llm_conversation',
    label='LLM',
    category='logic',
    icon='MessagesSquare',
    description=(
        "One or two AI personas. Single persona = Q&A assistant (opening → response). "
        "Two personas = debate/dialogue for N turns. Each persona has its own "
        "provider, model and system prompt. API keys are saved locally. "
        "Supports Ollama (local/cloud), OpenAI, Anthropic, Groq, DeepSeek, Custom."
    ),
    inputs=[
        {'id': 'image', 'color': 'image',  'label': 'Image (vision)'},
        {'id': 'seed',  'color': 'string', 'label': 'Message (port)'},
    ],
    outputs=[
        {'id': 'transcript', 'color': 'string', 'label': 'Transcript'},
        {'id': 'turns',      'color': 'list',   'label': 'Turns'},
        {'id': 'last',       'color': 'string', 'label': 'Last'},
    ],
    params=[
        {'id': 'run',          'label': 'Run',           'type': 'trigger', 'default': False},
        {'id': 'clear',        'label': 'Clear',         'type': 'trigger', 'default': False},
        {'id': '_v',           'label': '',              'type': 'int',     'default': 0},
        {'id': '_ctx',         'label': '',              'type': 'string',  'default': ''},
        {'id': '_ctx_label',   'label': '',              'type': 'string',  'default': ''},
        {'id': 'num_personas',  'label': 'Mode',          'type': 'enum',
         'options': ['1 Persona (Q&A)', '2 Personas (Dialogue)'], 'default': 0},
        {'id': 'keep_context',  'label': 'Keep Context',  'type': 'bool', 'default': False},
        {'id': 'auto_context',  'label': 'Auto Node Context', 'type': 'bool', 'default': False},
        {'id': 'inject_library', 'label': 'Node Library (pipeline help)', 'type': 'bool', 'default': False},
        {'id': 'opening',       'label': 'Message / Opening', 'type': 'string',
         'default': 'What do you think about this?'},
        {'id': 'num_turns',     'label': 'Turns (dialogue only)', 'type': 'int',
         'default': 6, 'min': 2, 'max': 40,
         'show_if': {'param': 'num_personas', 'value': 1}},

        # ── Generation ──
        {'id': 'section_gen', 'label': 'Generation', 'type': 'section'},
        {'id': 'temperature', 'label': 'Temperature', 'type': 'float',
         'default': 0.8, 'min': 0.0, 'max': 2.0, 'step': 0.05},
        {'id': 'max_tokens',  'label': 'Max Tokens / turn', 'type': 'int',
         'default': 200, 'min': 32, 'max': 2048, 'step': 32},
        {'id': 'timeout',     'label': 'Timeout (s)', 'type': 'int',
         'default': 60, 'min': 5, 'max': 180},
        {'id': 'num_ctx',     'label': 'Context window (Ollama, 0 = model default)',
         'type': 'int', 'default': 0, 'min': 0, 'max': 131072, 'step': 1024},
        {'id': 'keep_alive',  'label': 'Keep model loaded (Ollama)', 'type': 'enum',
         'options': ['5 min (default)', '30 min', '1 hour', 'Until unloaded', 'Unload after run'],
         'default': 0},
        {'id': 'thinking',    'label': 'Thinking mode (Ollama)', 'type': 'bool', 'default': False},

        # ── Persona A ──
        {'id': 'section_a',  'label': 'Persona A', 'type': 'section'},
        {'id': 'a_name',     'label': 'Name',     'type': 'string', 'default': 'Assistant'},
        {'id': 'a_provider', 'label': 'Provider', 'type': 'enum',
         'options': P.PROVIDERS, 'default': 0},
        {'id': 'a_model',    'label': 'Model (empty = default)', 'type': 'string', 'default': ''},
        {'id': 'a_api_key',  'label': 'API Key',  'type': 'string', 'default': ''},
        {'id': 'a_system',   'label': 'System Prompt', 'type': 'string',
         'default': 'You are a helpful assistant. Be concise.'},

        # ── Persona B (2-persona mode only) ──
        {'id': 'section_b',  'label': 'Persona B',
         'type': 'section', 'show_if': {'param': 'num_personas', 'value': 1}},
        {'id': 'b_name',     'label': 'Name',     'type': 'string', 'default': 'Bob',
         'show_if': {'param': 'num_personas', 'value': 1}},
        {'id': 'b_provider', 'label': 'Provider', 'type': 'enum',
         'options': P.PROVIDERS, 'default': 0,
         'show_if': {'param': 'num_personas', 'value': 1}},
        {'id': 'b_model',    'label': 'Model (empty = default)', 'type': 'string', 'default': '',
         'show_if': {'param': 'num_personas', 'value': 1}},
        {'id': 'b_api_key',  'label': 'API Key',  'type': 'string', 'default': '',
         'show_if': {'param': 'num_personas', 'value': 1}},
        {'id': 'b_system',   'label': 'System Prompt', 'type': 'string',
         'default': 'You are Bob, a thoughtful critic. Be concise (2-3 sentences). Stay in character.',
         'show_if': {'param': 'num_personas', 'value': 1}},
    ],
    colorable=True,
    resizable=True,
)
class LLMConversationNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._cache_result = None
        # Persistent conversation history for keep_context mode.
        # 1-persona: list of {'role','content'} dicts (OpenAI format).
        # 2-persona: list of {'speaker','text'} turn dicts.
        self._ctx_history: list = []

    def _empty(self, msg: str = '') -> dict:
        return {'transcript': msg, 'turns': [], 'last': ''}

    def _bump_v(self, params: dict, result: dict) -> dict:
        """Increment _v (breaks engine params_sig cache) and reset both
        trigger params so neither re-fires on the next engine tick."""
        new_v = int(params.get('_v', 0)) + 1
        return {**result, '_command': {
            'type': 'set_param', 'node_id': '__self__',
            'params': {'_v': new_v, 'run': False, 'clear': False},
        }}

    def _persona(self, params: dict, prefix: str) -> dict:
        provider_idx = int(params.get(f'{prefix}_provider', 0))
        provider = P.PROVIDERS[min(provider_idx, len(P.PROVIDERS) - 1)]
        model = (params.get(f'{prefix}_model') or P.DEFAULT_MODELS.get(provider, '')).strip()
        api_key = P.resolve_api_key(provider, params.get(f'{prefix}_api_key', ''))
        return {
            'name':     (params.get(f'{prefix}_name') or prefix.upper()).strip(),
            'provider': provider,
            'model':    model,
            'api_key':  api_key,
            'base_url': P.BASE_URLS.get(provider, ''),
            'system':   params.get(f'{prefix}_system', '').strip(),
        }

    def process(self, inputs: dict, params: dict) -> dict:
        if bool(params.get('clear', False)):
            self._cache_result = None
            self._ctx_history = []
            return self._bump_v(params, self._empty(''))

        if not bool(params.get('run', False)):
            if self._cache_result is not None:
                return self._cache_result
            # Empty transcript so downstream nodes (Note, Variable) don't
            # receive a placeholder string before the user presses Run.
            return {'transcript': '', 'turns': [], 'last': ''}

        opening     = (inputs.get('seed') or params.get('opening', '')).strip()

        # Auto node context: prepend a snapshot of the node the user selected on
        # the canvas (captured by the frontend into _ctx) so the LLM can give
        # parameter advice without the user pasting anything.
        if bool(params.get('auto_context', False)):
            ctx = (params.get('_ctx', '') or '').strip()
            if ctx:
                opening = (
                    "The user is working in a node-based computer-vision studio "
                    "and is asking about this node:\n\n"
                    f"{ctx}\n\n---\n\n{opening}"
                )

        num_personas = int(params.get('num_personas', 0))
        num_turns   = int(params.get('num_turns', 6))
        temperature = float(params.get('temperature', 0.8))
        max_tokens  = int(params.get('max_tokens', 200))
        timeout     = int(params.get('timeout', 60))
        thinking    = bool(params.get('thinking', False))

        A = self._persona(params, 'a')

        # Node Library: prepend the full node catalog (built live from the
        # registry) to A's system prompt so the assistant can suggest pipelines
        # made of real, existing nodes. Toggled from this node's params.
        inject_library = bool(params.get('inject_library', False))
        if inject_library:
            A['system'] = (
                (A['system'] + '\n\n' if A['system'] else '')
                + _LIB_PREAMBLE + _build_node_library()
            )

        # Ollama context window: honour the user value, but auto-raise a floor
        # when the (large) node catalog is injected, so Ollama doesn't silently
        # truncate the prompt to its ~4k default and drop the catalog.
        num_ctx = int(params.get('num_ctx', 0))
        if inject_library:
            est = len(A['system']) // 4 + max_tokens + 2048   # ~chars/4 + output + headroom
            num_ctx = max(num_ctx, ((est // 1024) + 1) * 1024)

        ka_idx = int(params.get('keep_alive', 0))
        keep_alive = _KEEP_ALIVE[min(ka_idx, len(_KEEP_ALIVE) - 1)]

        if A['provider'] in P.REQUIRES_KEY and not A['api_key']:
            return self._empty(f"Persona A ({A['provider']}): no API key")

        if not self.ensure_packages(['requests'], notif_id=_NOTIF_ID):
            return self._empty('requests package unavailable')

        img = inputs.get('image')
        img_b64 = P.img_to_b64(img) if img is not None else None

        keep_context = bool(params.get('keep_context', False))

        try:
            # ── 1-persona mode: Q&A (with optional running context) ──
            if num_personas == 0:
                self.report_progress(0.3, f'LLM: asking {A["name"]}…')

                if keep_context and self._ctx_history:
                    # Continue the conversation: append new user message to existing history
                    history = [
                        *([{'role': 'system', 'content': A['system']}] if A['system'] else []),
                        *self._ctx_history,
                        {'role': 'user', 'content': opening},
                    ]
                else:
                    # Fresh conversation
                    self._ctx_history = []
                    history = [
                        *([{'role': 'system', 'content': A['system']}] if A['system'] else []),
                        {'role': 'user', 'content': opening},
                    ]

                text, _ = P.call_llm(
                    A['provider'], A['model'], A['api_key'], A['base_url'],
                    history, img_b64,
                    json_mode=False, temperature=temperature,
                    max_tokens=max_tokens, timeout=timeout, thinking=thinking,
                    num_ctx=num_ctx, keep_alive=keep_alive,
                )
                text = (text or '').strip()

                if keep_context:
                    self._ctx_history.append({'role': 'user',      'content': opening})
                    self._ctx_history.append({'role': 'assistant',  'content': text})

                self.report_progress(1.0, 'LLM: done')
                # Build full transcript from accumulated context
                ctx_turns = [
                    {'speaker': 'User' if m['role'] == 'user' else A['name'], 'text': m['content']}
                    for m in self._ctx_history
                    if m['role'] in ('user', 'assistant')
                ] if keep_context else [{'speaker': A['name'], 'text': text}]

                transcript_str = '\n\n'.join(
                    f"{'You' if t['speaker'] == 'User' else A['name']}: {t['text']}"
                    for t in ctx_turns
                )
                result = {'transcript': transcript_str, 'turns': ctx_turns, 'last': text}
                self._cache_result = result
                return self._bump_v(params, result)

            # ── 2-persona mode: dialogue (with optional running context) ──
            B = self._persona(params, 'b')
            if B['provider'] in P.REQUIRES_KEY and not B['api_key']:
                return self._empty(f"Persona B ({B['provider']}): no API key")

            # Seed from previous turns if keep_context, otherwise fresh
            if not (keep_context and self._ctx_history):
                self._ctx_history = []

            transcript: list = list(self._ctx_history)  # copy to extend
            speakers = [A, B]
            # If context has turns, next speaker alternates from where we left off
            start_t = len(self._ctx_history)

            for t in range(num_turns):
                who = speakers[(start_t + t) % 2]
                self.report_progress(
                    (t + 0.5) / num_turns,
                    f'Turn {t + 1}/{num_turns}: {who["name"]}…'
                )
                # Opening is used only on the very first turn ever
                eff_opening = opening if (start_t + t) == 0 else ''
                history = _build_history(transcript, who['name'], who['system'], eff_opening)
                use_img = img_b64 if (start_t + t) == 0 else None
                text, _ = P.call_llm(
                    who['provider'], who['model'], who['api_key'], who['base_url'],
                    history, use_img,
                    json_mode=False, temperature=temperature,
                    max_tokens=max_tokens, timeout=timeout, thinking=thinking,
                    num_ctx=num_ctx, keep_alive=keep_alive,
                )
                transcript.append({'speaker': who['name'], 'text': (text or '').strip()})

            if keep_context:
                self._ctx_history = transcript  # persist all turns

        except Exception as e:
            err = str(e)
            print(f'[LLM] Error: {err}')
            send_notification(f'LLM error: {err[:120]}', level='error', notif_id=_NOTIF_ID)
            turns = locals().get('transcript', [])
            return {
                'transcript': '\n\n'.join(f"{t['speaker']}: {t['text']}" for t in turns) + f'\n\n[ERROR] {err[:200]}',
                'turns': turns,
                'last': turns[-1]['text'] if turns else '',
            }

        self.report_progress(1.0, f'Done ({num_turns} turns)')
        lines = [f"[Opening] {opening}\n"] if (opening and not self._ctx_history[:-num_turns]) else []
        lines += [f"{t['speaker']}: {t['text']}" for t in transcript]
        full = '\n\n'.join(lines)
        result = {
            'transcript': full,
            'turns': transcript,
            'last': transcript[-1]['text'] if transcript else '',
        }
        self._cache_result = result
        return self._bump_v(params, result)
