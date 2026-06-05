"""
LLM Conversation — two AI personas dialogue for a fixed number of turns.

A single orchestrator node (the engine is a DAG; a bounded loop lives inside
process(), not as a graph cycle). Persona A and Persona B alternate, each
seeing the exchange from its own point of view (its lines = assistant, the
other's = user). Outputs the full transcript, a per-turn list, and the last
message. Reuses the shared provider plumbing (_llm_shared/providers.py).
"""
from registry import vision_node, NodeProcessor, send_notification
import os
import importlib.util

# Load shared provider module (not a plugin → import by path)
_PROV_PATH = os.path.join(os.path.dirname(__file__), '_llm_shared', 'providers.py')
_spec = importlib.util.spec_from_file_location('_llm_providers', _PROV_PATH)
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)

_NOTIF_ID = 'llm_conversation'


def _build_history(transcript: list, speaker: str, system_prompt: str, opening: str) -> list:
    """Build a provider-ready history from THIS speaker's POV.
    Its own lines → 'assistant'; the other speaker's lines + opening → 'user'."""
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
    label='LLM Conversation',
    category='logic',
    icon='MessagesSquare',
    description=(
        "Two AI personas dialogue for a fixed number of turns. Each persona "
        "has its own provider, model and system prompt. The loop runs inside "
        "the node (no graph cycle). Outputs the full transcript, a per-turn "
        "list, and the last message. Supports Ollama (local/cloud), OpenAI, "
        "Anthropic, Groq, DeepSeek, Custom."
    ),
    inputs=[
        {'id': 'image', 'color': 'image',  'label': 'Image (vision, turn 1)'},
        {'id': 'seed',  'color': 'string', 'label': 'Opening Message (port)'},
    ],
    outputs=[
        {'id': 'transcript', 'color': 'string', 'label': 'Transcript'},
        {'id': 'turns',      'color': 'list',   'label': 'Turns [{speaker,text}]'},
        {'id': 'last',       'color': 'string', 'label': 'Last Message'},
    ],
    params=[
        {'id': 'run',       'label': 'Run Conversation', 'type': 'trigger', 'default': False},
        {'id': 'opening',   'label': 'Opening Message', 'type': 'string',
         'default': 'Let us debate: is a stone wall better dry-stacked or mortared?'},
        {'id': 'num_turns', 'label': 'Number of Turns', 'type': 'int',
         'default': 6, 'min': 2, 'max': 40},

        # ── Persona A ──
        {'id': 'a_name',     'label': 'A · Name', 'type': 'string', 'default': 'Alice'},
        {'id': 'a_provider', 'label': 'A · Provider', 'type': 'enum',
         'options': P.PROVIDERS, 'default': 0},
        {'id': 'a_model',    'label': 'A · Model (empty=default)', 'type': 'string', 'default': ''},
        {'id': 'a_api_key',  'label': 'A · API Key', 'type': 'string', 'default': ''},
        {'id': 'a_system',   'label': 'A · System Prompt', 'type': 'string',
         'default': 'You are Alice, a pragmatic builder. Be concise (2-3 sentences). Stay in character.'},

        # ── Persona B ──
        {'id': 'b_name',     'label': 'B · Name', 'type': 'string', 'default': 'Bob'},
        {'id': 'b_provider', 'label': 'B · Provider', 'type': 'enum',
         'options': P.PROVIDERS, 'default': 0},
        {'id': 'b_model',    'label': 'B · Model (empty=default)', 'type': 'string', 'default': ''},
        {'id': 'b_api_key',  'label': 'B · API Key', 'type': 'string', 'default': ''},
        {'id': 'b_system',   'label': 'B · System Prompt', 'type': 'string',
         'default': 'You are Bob, a traditionalist mason. Be concise (2-3 sentences). Stay in character.'},

        # ── Generation ──
        {'id': 'temperature', 'label': 'Temperature', 'type': 'float',
         'default': 0.8, 'min': 0.0, 'max': 2.0, 'step': 0.05},
        {'id': 'max_tokens',  'label': 'Max Tokens / turn', 'type': 'int',
         'default': 200, 'min': 32, 'max': 2048, 'step': 32},
        {'id': 'timeout',     'label': 'Timeout (s) / turn', 'type': 'int',
         'default': 60, 'min': 5, 'max': 180},
        {'id': 'thinking',    'label': 'Thinking (Ollama)', 'type': 'bool', 'default': False},
    ],
    colorable=True,
    resizable=True,
)
class LLMConversationNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._cache_result = None

    def _empty(self, msg: str = '') -> dict:
        return {'transcript': msg, 'turns': [], 'last': ''}

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
        # Trigger gate
        if not bool(params.get('run', False)):
            if self._cache_result is not None:
                return self._cache_result
            return self._empty('Press Run Conversation to start')

        opening   = (inputs.get('seed') or params.get('opening', '')).strip()
        num_turns = int(params.get('num_turns', 6))
        temperature = float(params.get('temperature', 0.8))
        max_tokens  = int(params.get('max_tokens', 200))
        timeout     = int(params.get('timeout', 60))
        thinking    = bool(params.get('thinking', False))

        A = self._persona(params, 'a')
        B = self._persona(params, 'b')

        # Validate keys
        for who in (A, B):
            if who['provider'] in P.REQUIRES_KEY and not who['api_key']:
                return self._empty(f"{who['name']} ({who['provider']}): no API key")

        if not self.ensure_packages(['requests'], notif_id=_NOTIF_ID):
            return self._empty('requests package unavailable')

        # Image attaches to the very first model call only
        img = inputs.get('image')
        img_b64 = P.img_to_b64(img) if img is not None else None

        transcript: list = []   # [{'speaker': name, 'text': ...}]
        speakers = [A, B]

        try:
            for t in range(num_turns):
                who = speakers[t % 2]            # A starts
                other = speakers[(t + 1) % 2]
                self.report_progress((t + 0.5) / num_turns,
                                     f'Turn {t + 1}/{num_turns}: {who["name"]}…')

                history = _build_history(transcript, who['name'], who['system'], opening)
                use_img = img_b64 if t == 0 else None

                text, _ = P.call_llm(
                    who['provider'], who['model'], who['api_key'], who['base_url'],
                    history, use_img,
                    json_mode=False, temperature=temperature,
                    max_tokens=max_tokens, timeout=timeout, thinking=thinking,
                )
                text = (text or '').strip()
                transcript.append({'speaker': who['name'], 'text': text})

        except Exception as e:
            err = str(e)
            print(f'[LLMConversation] Error: {err}')
            send_notification(f'Conversation error: {err[:120]}', level='error', notif_id=_NOTIF_ID)
            # Return whatever was gathered so far + the error
            partial = self._format(transcript, opening, A, B)
            return {'transcript': partial + f'\n\n[ERROR] {err[:200]}',
                    'turns': transcript, 'last': transcript[-1]['text'] if transcript else ''}

        self.report_progress(1.0, f'Conversation done ({num_turns} turns)')
        full = self._format(transcript, opening, A, B)
        result = {
            'transcript': full,
            'turns': transcript,
            'last': transcript[-1]['text'] if transcript else '',
        }
        self._cache_result = result
        return result

    def _format(self, transcript: list, opening: str, A: dict, B: dict) -> str:
        lines = []
        if opening:
            lines.append(f'[Opening] {opening}\n')
        for turn in transcript:
            lines.append(f"{turn['speaker']}: {turn['text']}")
        return '\n\n'.join(lines)
