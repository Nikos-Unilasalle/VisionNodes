"""
Shared LLM provider plumbing — used by both llm_inference and llm_conversation.

NOT a plugin (lives in a subdirectory the loader does not scan). Imported via
importlib from the node files. Single source of truth for provider URLs,
message formats, auth, and error surfacing.
"""
import os
import json
import base64

import cv2
import numpy as np

PROVIDERS = ['Ollama (local)', 'Ollama (cloud)', 'OpenAI', 'Anthropic', 'Groq', 'DeepSeek', 'Custom']

DEFAULT_MODELS = {
    'Ollama (local)':  'gemma4:e4b',
    'Ollama (cloud)':  'gemma4:31b',
    'OpenAI':          'gpt-4o-mini',
    'Anthropic':       'claude-haiku-4-5-20251001',
    'Groq':            'llama-3.2-11b-vision-preview',
    'DeepSeek':        'deepseek-chat',
    'Custom':          'gpt-4o-mini',
}

BASE_URLS = {
    'Ollama (local)':  'http://localhost:11434',
    'Ollama (cloud)':  'https://ollama.com',
    'OpenAI':          'https://api.openai.com',
    'Anthropic':       'https://api.anthropic.com',
    'Groq':            'https://api.groq.com/openai',
    'DeepSeek':        'https://api.deepseek.com',
    'Custom':          '',
}

REQUIRES_KEY = {'Ollama (cloud)', 'OpenAI', 'Anthropic', 'Groq', 'DeepSeek'}

_ENV_KEYS = {
    'OpenAI':    'OPENAI_API_KEY',
    'Anthropic': 'ANTHROPIC_API_KEY',
    'Groq':      'GROQ_API_KEY',
    'DeepSeek':  'DEEPSEEK_API_KEY',
}

SECRETS_PATH = os.path.expanduser('~/.vnstudio/secrets.json')


# ── Secrets ──────────────────────────────────────────────────────────────
def load_secrets() -> dict:
    try:
        with open(SECRETS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def save_secret(key: str, value: str) -> None:
    os.makedirs(os.path.dirname(SECRETS_PATH), exist_ok=True)
    secrets = load_secrets()
    secrets[key] = value
    try:
        with open(SECRETS_PATH, 'w') as f:
            json.dump(secrets, f)
    except Exception:
        pass


def resolve_api_key(provider: str, api_key_param: str) -> str:
    """API key from param → env var → persisted secrets (priority order)."""
    if api_key_param and api_key_param.strip():
        save_secret(f'llm_{provider}_key', api_key_param.strip())
        return api_key_param.strip()
    env_key = _ENV_KEYS.get(provider, '')
    if env_key and os.environ.get(env_key):
        return os.environ[env_key]
    return load_secrets().get(f'llm_{provider}_key', '')


# ── Image ────────────────────────────────────────────────────────────────
def img_to_b64(img: np.ndarray) -> str:
    """Encode numpy BGR image → JPEG base64 string (capped at 1280px wide)."""
    h, w = img.shape[:2]
    if w > 1280:
        scale = 1280 / w
        img = cv2.resize(img, (1280, int(h * scale)), interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf).decode('utf-8')


# ── HTTP ─────────────────────────────────────────────────────────────────
def extract_api_error(resp) -> str:
    """Pull the human-readable error out of a provider's JSON body."""
    try:
        body = resp.json()
    except Exception:
        txt = (resp.text or '').strip()
        # Strip HTML tags so a 502 Bad Gateway page doesn't flood the UI
        import re as _re
        txt = _re.sub(r'<[^>]+>', ' ', txt)
        txt = ' '.join(txt.split())
        return f'HTTP {resp.status_code}: {txt[:200]}' if txt else f'HTTP {resp.status_code}'
    err = body.get('error') if isinstance(body, dict) else None
    if isinstance(err, dict):
        msg = err.get('message') or err.get('type') or str(err)
    elif isinstance(err, str):
        msg = err
    elif isinstance(body, dict):
        msg = body.get('message') or json.dumps(body)
    else:
        msg = str(body)
    return f'HTTP {resp.status_code}: {str(msg)[:280]}'


def post_json(url: str, headers: dict, payload: dict, timeout: int):
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
        raise RuntimeError(extract_api_error(resp))
    return resp.json()


# ── Message builders ─────────────────────────────────────────────────────
def build_messages_openai(history: list, img_b64: str = None) -> list:
    """history = [{'role','content'},…]. Image (if any) attaches to the LAST
    user message as an OpenAI image_url content block."""
    msgs = [dict(m) for m in history]
    if img_b64:
        for m in reversed(msgs):
            if m.get('role') == 'user':
                m['content'] = [
                    {'type': 'image_url',
                     'image_url': {'url': f'data:image/jpeg;base64,{img_b64}', 'detail': 'auto'}},
                    {'type': 'text', 'text': m['content']},
                ]
                break
    return msgs


def build_messages_anthropic(history: list, img_b64: str = None) -> list:
    """Anthropic messages (no system role inside; passed separately)."""
    msgs = []
    for m in history:
        if m.get('role') == 'system':
            continue
        msgs.append({'role': m['role'], 'content': [{'type': 'text', 'text': m['content']}]})
    if img_b64 and msgs:
        for m in reversed(msgs):
            if m['role'] == 'user':
                m['content'].insert(0, {'type': 'image',
                    'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': img_b64}})
                break
    return msgs


# ── Unified call ─────────────────────────────────────────────────────────
def call_llm(provider: str, model: str, api_key: str, base_url: str,
             history: list, img_b64: str = None, *,
             json_mode: bool = False, temperature: float = 0.7,
             max_tokens: int = 512, timeout: int = 30, thinking: bool = False,
             num_ctx: int = 0, keep_alive: str = '') -> tuple:
    """Run one completion against any provider.

    history: list of {'role': 'system'|'user'|'assistant', 'content': str}.
    num_ctx: Ollama context-window size (tokens). 0 = leave the model default.
        MUST be set large enough when the prompt is big (e.g. an injected node
        catalog) — Ollama silently truncates the prompt to num_ctx otherwise,
        dropping the oldest tokens (the system prompt) with no error.
    keep_alive: Ollama only. How long to keep the model resident after the call
        ('5m', '30m', '1h', '-1' = forever, '0' = unload now). '' = server
        default (~5m). Keeping it loaded preserves the KV cache so a stable
        prompt prefix isn't re-processed on the next Run.
    Returns (text, tokens). Raises RuntimeError with a clear message on failure.
    """
    system = ''
    for m in history:
        if m.get('role') == 'system':
            system = m['content']
            break

    if provider == 'Anthropic':
        url = 'https://api.anthropic.com/v1/messages'
        headers = {'x-api-key': api_key, 'anthropic-version': '2023-06-01',
                   'content-type': 'application/json'}
        payload = {
            'model': model, 'max_tokens': max_tokens,
            'temperature': max(0.0, min(1.0, temperature)),   # Anthropic needs [0,1]
            'messages': build_messages_anthropic(history, img_b64),
        }
        if system:
            # Cache the system prompt as a stable prefix. When it carries the
            # node catalog (~17k tokens, memoised so it's byte-identical across
            # Runs) repeat calls read it at ~0.1x instead of full input price.
            # Below the model's min cacheable size this is a silent no-op.
            payload['system'] = [{'type': 'text', 'text': system,
                                  'cache_control': {'type': 'ephemeral'}}]
        data = post_json(url, headers, payload, timeout)
        text = data['content'][0]['text']
        tokens = float(data.get('usage', {}).get('input_tokens', 0) +
                       data.get('usage', {}).get('output_tokens', 0))
        return text, tokens

    if provider in ('Ollama (local)', 'Ollama (cloud)'):
        url = f"{base_url.rstrip('/')}/api/chat"
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        # Native format: attach image to last user message via 'images'
        messages = [dict(m) for m in history]
        if img_b64:
            for m in reversed(messages):
                if m.get('role') == 'user':
                    m['images'] = [img_b64]
                    break
        options = {'temperature': temperature, 'num_predict': max_tokens}
        if num_ctx > 0:
            options['num_ctx'] = int(num_ctx)   # else Ollama truncates a big prompt to its default (~4k)
        payload = {
            'model': model, 'messages': messages, 'stream': False,
            'think': bool(thinking), 'options': options,
        }
        if keep_alive:
            payload['keep_alive'] = keep_alive   # keep model + KV cache resident between Runs
        if json_mode:
            payload['format'] = 'json'
        data = post_json(url, headers, payload, timeout)
        message = data.get('message', {})
        text = message.get('content', '')
        if not text and message.get('thinking'):
            text = message['thinking']
        tokens = float(data.get('eval_count', 0) + data.get('prompt_eval_count', 0))
        return text, tokens

    # OpenAI, Groq, DeepSeek, Custom — OpenAI-compatible
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {
        'model': model, 'messages': build_messages_openai(history, img_b64),
        'temperature': temperature, 'max_tokens': max_tokens,
    }
    if json_mode:
        payload['response_format'] = {'type': 'json_object'}
    data = post_json(url, headers, payload, timeout)
    text = data['choices'][0]['message']['content']
    tokens = float(data.get('usage', {}).get('total_tokens', 0))
    return text, tokens
