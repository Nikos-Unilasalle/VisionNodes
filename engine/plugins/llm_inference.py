"""
LLM Inference — Universal LLM node supporting local Ollama and cloud providers.
Supports text + vision (image input). JSON structured output mode.
Providers: Ollama (local), OpenAI, Anthropic, Groq, Custom (any OpenAI-compatible).
"""
from registry import vision_node, NodeProcessor, send_notification
import cv2
import numpy as np
import json
import base64
import threading
import os

_NOTIF_ID = 'llm_inference'

_PROVIDERS = ['Ollama (local)', 'Ollama (cloud)', 'OpenAI', 'Anthropic', 'Groq', 'Custom']

_DEFAULT_MODELS = {
    'Ollama (local)':  'gemma4:e4b',
    'Ollama (cloud)':  'gemma4:31b',
    'OpenAI':          'gpt-4o-mini',
    'Anthropic':       'claude-haiku-4-5-20251001',
    'Groq':            'llama-3.2-11b-vision-preview',
    'Custom':          'gpt-4o-mini',
}

_BASE_URLS = {
    'Ollama (local)':  'http://localhost:11434',
    'Ollama (cloud)':  'https://ollama.com',
    'OpenAI':          'https://api.openai.com',
    'Anthropic':       'https://api.anthropic.com',
    'Groq':            'https://api.groq.com/openai',
    'Custom':          '',
}

# Providers that require an API key
_REQUIRES_KEY = {'Ollama (cloud)', 'OpenAI', 'Anthropic', 'Groq'}

_SECRETS_PATH = os.path.expanduser('~/.vnstudio/secrets.json')


def _load_secrets() -> dict:
    try:
        with open(_SECRETS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_secret(key: str, value: str) -> None:
    os.makedirs(os.path.dirname(_SECRETS_PATH), exist_ok=True)
    secrets = _load_secrets()
    secrets[key] = value
    try:
        with open(_SECRETS_PATH, 'w') as f:
            json.dump(secrets, f)
    except Exception:
        pass


def _img_to_b64(img: np.ndarray) -> str:
    """Encode numpy BGR image → JPEG base64 string."""
    h, w = img.shape[:2]
    if w > 1280:
        scale = 1280 / w
        img = cv2.resize(img, (1280, int(h * scale)), interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf).decode('utf-8')


def _extract_api_error(resp) -> str:
    """Pull the human-readable error out of a provider's JSON body.
    Providers return the real reason (bad model, no credit, invalid param)
    in the body — raise_for_status() throws it away, so we dig it out."""
    try:
        body = resp.json()
    except Exception:
        txt = (resp.text or '').strip()
        return txt[:300] if txt else f'HTTP {resp.status_code}'
    # OpenAI / Ollama / Groq: {"error": {"message": "..."}} or {"error": "..."}
    err = body.get('error') if isinstance(body, dict) else None
    if isinstance(err, dict):
        msg = err.get('message') or err.get('type') or str(err)
    elif isinstance(err, str):
        msg = err
    elif isinstance(body, dict):
        # Anthropic: {"type":"error","error":{"type":"...","message":"..."}}
        msg = body.get('message') or json.dumps(body)
    else:
        msg = str(body)
    return f'HTTP {resp.status_code}: {str(msg)[:280]}'


def _post_json(url: str, headers: dict, payload: dict, timeout: int):
    """POST JSON, returning parsed response. On HTTP error, raise with the
    provider's actual error message (not the opaque raise_for_status text)."""
    import requests
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f'Connection failed to {url} — is the server running? ({str(e)[:100]})')
    except requests.exceptions.Timeout:
        raise RuntimeError(f'Request timed out after {timeout}s — try raising Timeout')
    if not resp.ok:
        raise RuntimeError(_extract_api_error(resp))
    return resp.json()


@vision_node(
    type_id='llm_inference',
    label='LLM Inference',
    category='logic',
    icon='BrainCircuit',
    description=(
        "Universal LLM node — connects to Ollama (local) or cloud providers "
        "(OpenAI, Anthropic, Groq, Custom OpenAI-compatible). "
        "Supports text and vision (image) inputs. "
        "JSON mode parses structured output into a dict port. "
        "API keys are persisted locally."
    ),
    inputs=[
        {'id': 'image',   'color': 'image',  'label': 'Image (vision)'},
        {'id': 'prompt',  'color': 'string', 'label': 'User Prompt'},
        {'id': 'context', 'color': 'dict',   'label': 'Context (injected as JSON)'},
    ],
    outputs=[
        {'id': 'text',      'color': 'string', 'label': 'Response Text'},
        {'id': 'json_data', 'color': 'dict',   'label': 'JSON Data'},
        {'id': 'tokens',    'color': 'scalar', 'label': 'Tokens Used'},
    ],
    params=[
        {'id': 'run',          'label': 'Run',          'type': 'trigger', 'default': False},
        {'id': 'provider',     'label': 'Provider',     'type': 'enum',
         'options': _PROVIDERS, 'default': 0},
        {'id': 'model',        'label': 'Model (empty = provider default)', 'type': 'string', 'default': ''},
        {'id': 'api_key',      'label': 'API Key',      'type': 'string',  'default': ''},
        {'id': 'base_url',     'label': 'Custom Base URL', 'type': 'string', 'default': ''},
        {'id': 'system_prompt','label': 'System Prompt','type': 'string',
         'default': 'You are a helpful vision assistant. Be concise.'},
        {'id': 'user_prompt',  'label': 'User Prompt (param)', 'type': 'string',
         'default': 'Describe what you see.'},
        {'id': 'json_mode',    'label': 'JSON Mode',    'type': 'bool',    'default': False},
        {'id': 'thinking',     'label': 'Thinking (Ollama)', 'type': 'bool', 'default': False},
        {'id': 'temperature',  'label': 'Temperature',  'type': 'float',
         'default': 0.7, 'min': 0.0, 'max': 2.0, 'step': 0.05},
        {'id': 'max_tokens',   'label': 'Max Tokens',   'type': 'int',
         'default': 512, 'min': 64, 'max': 8192, 'step': 64},
        {'id': 'timeout',      'label': 'Timeout (s)',  'type': 'int',
         'default': 30, 'min': 5, 'max': 120},
    ],
    colorable=True,
    resizable=True,
)
class LLMInferenceNode(NodeProcessor):
    def __init__(self):
        super().__init__()
        self._cache_result = None
        self._running = False

    def _empty(self, msg: str = '') -> dict:
        return {'text': msg, 'json_data': None, 'tokens': 0.0}

    def _resolve_api_key(self, provider: str, api_key_param: str) -> str:
        """Return API key from param, env, or persisted secrets (priority order)."""
        if api_key_param.strip():
            _save_secret(f'llm_{provider}_key', api_key_param.strip())
            return api_key_param.strip()

        env_map = {
            'OpenAI':    'OPENAI_API_KEY',
            'Anthropic': 'ANTHROPIC_API_KEY',
            'Groq':      'GROQ_API_KEY',
        }
        env_key = env_map.get(provider, '')
        if env_key and os.environ.get(env_key):
            return os.environ[env_key]

        secrets = _load_secrets()
        return secrets.get(f'llm_{provider}_key', '')

    def _call_ollama_native(self, base_url: str, api_key: str, model: str, system: str,
                            user_text: str, img_b64: str | None,
                            json_mode: bool, temperature: float,
                            max_tokens: int, timeout: int, thinking: bool) -> tuple:
        """Call Ollama native /api/chat — works for both local and cloud.
        Cloud uses Bearer auth (https://ollama.com); local has no auth.
        Mirrors the GravityChat reference app contract.

        Note: gemma4/qwen3 etc. have a thinking mode. With thinking ON, the
        token budget is spent on hidden reasoning and 'content' comes back empty
        if num_predict is too small. Default OFF for direct answers."""
        url = f"{base_url.rstrip('/')}/api/chat"

        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        # Native format: image goes in 'images' array on the message, not in content
        user_msg: dict = {'role': 'user', 'content': user_text}
        if img_b64:
            user_msg['images'] = [img_b64]

        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append(user_msg)

        payload: dict = {
            'model':    model,
            'messages': messages,
            'stream':   False,
            'think':    bool(thinking),
            'options':  {'temperature': temperature, 'num_predict': max_tokens},
        }
        if json_mode:
            payload['format'] = 'json'

        data    = _post_json(url, headers, payload, timeout)
        message = data.get('message', {})
        text    = message.get('content', '')
        # Fallback: if a thinking model spent its budget reasoning and left
        # content empty, surface the thinking text rather than returning nothing.
        if not text and message.get('thinking'):
            text = message['thinking']
        tokens = float(data.get('eval_count', 0) + data.get('prompt_eval_count', 0))
        return text, tokens

    def _call_openai_compatible(self, base_url: str, api_key: str, model: str,
                                messages: list, json_mode: bool,
                                temperature: float, max_tokens: int, timeout: int) -> tuple:
        """Call any OpenAI-compatible API (/v1/chat/completions)."""
        url = f"{base_url.rstrip('/')}/v1/chat/completions"
        headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
        payload = {
            'model':       model,
            'messages':    messages,
            'temperature': temperature,
            'max_tokens':  max_tokens,
        }
        if json_mode:
            payload['response_format'] = {'type': 'json_object'}
        data = _post_json(url, headers, payload, timeout)
        text   = data['choices'][0]['message']['content']
        tokens = float(data.get('usage', {}).get('total_tokens', 0))
        return text, tokens

    def _call_anthropic(self, api_key: str, model: str, system: str, messages: list,
                        max_tokens: int, temperature: float, timeout: int) -> tuple:
        """Call Anthropic Messages API (distinct format)."""
        url = 'https://api.anthropic.com/v1/messages'
        headers = {
            'x-api-key':         api_key,
            'anthropic-version': '2023-06-01',
            'content-type':      'application/json',
        }
        payload = {
            'model':      model,
            'max_tokens': max_tokens,
            # Anthropic requires temperature in [0, 1]; the node allows up to 2.
            'temperature': max(0.0, min(1.0, temperature)),
            'messages':   messages,
        }
        if system:
            payload['system'] = system
        data   = _post_json(url, headers, payload, timeout)
        text   = data['content'][0]['text']
        tokens = float(data.get('usage', {}).get('input_tokens', 0) +
                       data.get('usage', {}).get('output_tokens', 0))
        return text, tokens

    def _build_messages_openai(self, system: str, user_text: str,
                               img_b64: str | None) -> list:
        """Build OpenAI-format messages list."""
        msgs = []
        if system:
            msgs.append({'role': 'system', 'content': system})

        if img_b64:
            content = [
                {'type': 'image_url',
                 'image_url': {'url': f'data:image/jpeg;base64,{img_b64}', 'detail': 'auto'}},
                {'type': 'text', 'text': user_text},
            ]
        else:
            content = user_text

        msgs.append({'role': 'user', 'content': content})
        return msgs

    def _build_messages_anthropic(self, user_text: str, img_b64: str | None) -> list:
        """Build Anthropic-format messages list."""
        if img_b64:
            content = [
                {'type': 'image',
                 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': img_b64}},
                {'type': 'text', 'text': user_text},
            ]
        else:
            content = [{'type': 'text', 'text': user_text}]
        return [{'role': 'user', 'content': content}]

    def process(self, inputs: dict, params: dict) -> dict:
        # Trigger gate
        triggered = bool(params.get('run', False))
        if not triggered:
            if self._cache_result is not None:
                return self._cache_result
            return self._empty('Press Run to execute')

        if self._running:
            return self._cache_result or self._empty('Running…')

        provider_idx = int(params.get('provider', 0))
        provider     = _PROVIDERS[min(provider_idx, len(_PROVIDERS) - 1)]
        model        = (params.get('model') or _DEFAULT_MODELS.get(provider, 'gemma4:e4b')).strip()
        api_key      = self._resolve_api_key(provider, params.get('api_key', ''))
        custom_url   = (params.get('base_url') or '').strip()
        system       = params.get('system_prompt', '').strip()
        temperature  = float(params.get('temperature', 0.7))
        max_tokens   = int(params.get('max_tokens', 512))
        timeout      = int(params.get('timeout', 30))
        json_mode    = bool(params.get('json_mode', False))
        thinking     = bool(params.get('thinking', False))

        # User prompt: port takes priority over param
        user_text = inputs.get('prompt') or params.get('user_prompt', 'Describe what you see.')
        if not isinstance(user_text, str):
            user_text = str(user_text)

        # Inject context dict if connected
        context = inputs.get('context')
        if isinstance(context, dict) and context:
            user_text += f'\n\nContext:\n{json.dumps(context, ensure_ascii=False, indent=2)}'

        if json_mode and 'json' not in user_text.lower():
            user_text += '\n\nRespond with valid JSON only.'

        # Encode image if connected
        img = inputs.get('image')
        img_b64 = _img_to_b64(img) if img is not None else None

        base_url = custom_url or _BASE_URLS.get(provider, '')

        # Cloud providers require an API key
        if provider in _REQUIRES_KEY and not api_key:
            return self._empty(f'{provider}: no API key — enter it in the param field')

        self.report_progress(0.1, f'LLM: calling {provider} / {model}…')

        try:
            if not self.ensure_packages(['requests'], notif_id=_NOTIF_ID):
                return self._empty('requests package unavailable')

            if provider == 'Anthropic':
                msgs = self._build_messages_anthropic(user_text, img_b64)
                text, tokens = self._call_anthropic(
                    api_key, model, system, msgs, max_tokens, temperature, timeout
                )
            elif provider in ('Ollama (local)', 'Ollama (cloud)'):
                # Both use native /api/chat; cloud adds Bearer auth (api_key)
                text, tokens = self._call_ollama_native(
                    base_url, api_key, model, system, user_text, img_b64,
                    json_mode, temperature, max_tokens, timeout, thinking
                )
            else:
                # OpenAI, Groq, Custom — OpenAI-compatible with Bearer auth
                msgs = self._build_messages_openai(system, user_text, img_b64)
                text, tokens = self._call_openai_compatible(
                    base_url, api_key, model, msgs, json_mode, temperature, max_tokens, timeout
                )

        except Exception as e:
            err = str(e)
            print(f'[LLM] Error: {err}')
            send_notification(f'LLM error: {err[:120]}', level='error', notif_id=_NOTIF_ID)
            result = self._empty(f'Error: {err[:200]}')
            self._cache_result = result
            return result

        # Parse JSON if mode enabled
        json_data = None
        if json_mode:
            try:
                # Strip markdown code fences if present
                cleaned = text.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
                json_data = json.loads(cleaned)
            except Exception:
                json_data = {'raw': text}

        self.report_progress(1.0, f'LLM: done ({int(tokens)} tokens)')

        result = {'text': text, 'json_data': json_data, 'tokens': tokens}
        self._cache_result = result
        return result
