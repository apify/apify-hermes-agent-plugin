"""Apify Actor execution tools — discover, start, collect."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = {'SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'}
_MAX_BATCH_RUNS = 10
_COLLECT_DEFAULT_LIMIT = 100
_MAX_CONTENT_CHARS = 50_000


def _attr(obj: Any, key: str, default: Any = None) -> Any:
    """Get attribute or dict key from SDK response objects (apify_client returns either)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    if obj is not None and hasattr(obj, key):
        return getattr(obj, key)
    return default


def _get_client() -> Any:
    from apify_hermes_agent_plugin.client import get_apify_client

    return get_apify_client()


def _check_token() -> bool:
    from apify_hermes_agent_plugin.client import check_apify_api_key

    return check_apify_api_key()


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _discover_handler(args: dict[str, Any]) -> dict[str, Any]:
    from tools.interrupt import is_interrupted

    if is_interrupted():
        return {'error': 'Interrupted'}

    query = (_attr(args, 'query') or '').strip() or None
    actor_id = (_attr(args, 'actor_id') or '').strip() or None

    if not query and not actor_id:
        return {
            'error': (
                "Provide exactly one of 'query' (to search the Apify Store) "
                "or 'actor_id' (to fetch an Actor's input schema)."
            )
        }

    client = _get_client()
    if actor_id:
        return _discover_actor(client, actor_id)
    assert query is not None, 'guaranteed by the query/actor_id check above'
    return _discover_store(client, query)


def _discover_actor(client: Any, actor_id: str) -> dict[str, Any]:
    """Fetch a single Actor's input schema and README by ID or username~actor-name."""
    try:
        actor_info = client.actor(actor_id).get()
        if actor_info is None:
            return {'error': (f"Actor '{actor_id}' not found. Check the ID format: username~actor-name.")}

        input_schema: Any = None
        readme: Any = None

        build_detail = client.actor(actor_id).default_build().get()
        if build_detail is not None:
            # apify-client 3.x returns Pydantic models with snake_case attributes
            # (e.g. Build.actor_definition, Build.input_schema) — the JSON's
            # camelCase names only exist as (de)serialization aliases, not as
            # real attributes, so _attr() must be called with the snake_case name.
            actor_def = _attr(build_detail, 'actor_definition')
            raw_schema = _attr(actor_def, 'input')
            if raw_schema:
                input_schema = json.dumps(raw_schema)
            else:
                fallback = _attr(build_detail, 'input_schema')
                if fallback:
                    input_schema = str(fallback)

            raw_readme = _attr(actor_def, 'readme') or _attr(build_detail, 'readme')
            if raw_readme:
                readme = str(raw_readme)[:3000]

        username = _attr(actor_info, 'username', '')
        name = _attr(actor_info, 'name', '')
        title = _attr(actor_info, 'title', '') or name
    except Exception as exc:
        logger.warning('apify_discover schema fetch error for %s: %s', actor_id, exc)
        return {'error': str(exc)}
    else:
        return {
            'actor_id': f'{username}~{name}',
            'name': name,
            'title': title,
            'username': username,
            'description': _attr(actor_info, 'description', ''),
            'input_schema': input_schema,
            'readme': readme,
            'tip': (f"Use apify_start with actor_id='{username}~{name}' and an input matching the input_schema above."),
        }


def _discover_store(client: Any, query: str) -> dict[str, Any]:
    """Search the Apify Store by keyword."""
    try:
        result = client.store().list(search=query, limit=10, sort_by='relevance')
        items = _attr(result, 'items') or []
        actors: list[dict[str, Any]] = []
        for item in items:
            stats = _attr(item, 'stats')
            name = _attr(item, 'name', '')
            username = _attr(item, 'username', '')
            title = _attr(item, 'title') or name
            desc = (_attr(item, 'description') or '')[:200]
            # ActorStats.total_runs — see the snake_case note in _discover_actor().
            run_count = _attr(stats, 'total_runs', 0) or 0
            actors.append(
                {
                    'actor_id': f'{username}~{name}',
                    'name': name,
                    'title': title,
                    'username': username,
                    'description': desc,
                    'run_count': run_count,
                }
            )
    except Exception as exc:
        logger.warning("apify_discover store search error for '%s': %s", query, exc)
        return {'error': str(exc)}
    else:
        return {'actors': actors}


def _start_one_run(client: Any, spec: dict[str, Any]) -> dict[str, Any]:
    actor_id = (spec.get('actor_id') or '').strip()
    run_input = spec.get('input') or {}
    label = spec.get('label')

    if not actor_id:
        return {'_ok': False, 'error': "Missing 'actor_id' in run spec."}

    try:
        run = client.actor(actor_id).start(run_input=run_input)
        entry: dict[str, Any] = {
            'run_id': _attr(run, 'id'),
            'actor_id': actor_id,
            'dataset_id': _attr(run, 'default_dataset_id'),
            'status': _attr(run, 'status'),
        }
        if label:
            entry['label'] = label
    except Exception as exc:
        logger.warning('apify_start error for %s: %s', actor_id, exc)
        err: dict[str, Any] = {'actor_id': actor_id, 'error': str(exc)}
        if label:
            err['label'] = label
        return {'_ok': False, **err}
    else:
        return {'_ok': True, **entry}


def _start_handler(args: dict[str, Any]) -> dict[str, Any]:
    from tools.interrupt import is_interrupted

    if is_interrupted():
        return {'error': 'Interrupted'}

    run_specs = args.get('runs') or []
    if not run_specs:
        return {'error': "Provide at least one run spec in 'runs'."}
    if len(run_specs) > _MAX_BATCH_RUNS:
        return {'error': f'Batch too large: {len(run_specs)} runs requested, maximum is {_MAX_BATCH_RUNS}.'}

    client = _get_client()
    started: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for spec in run_specs:
        from tools.interrupt import is_interrupted

        if is_interrupted():
            break
        outcome = _start_one_run(client, spec)
        ok = outcome.pop('_ok')
        (started if ok else errors).append(outcome)

    result: dict[str, Any] = {'runs': started}
    if errors:
        result['errors'] = errors
    return result


async def _check_run(client: Any, limit: int, ref: dict[str, Any]) -> dict[str, Any]:
    run_id = ref.get('run_id', '')
    actor_id = ref.get('actor_id', '')
    dataset_id = ref.get('dataset_id', '')
    label = ref.get('label')

    base: dict[str, Any] = {
        'run_id': run_id,
        'actor_id': actor_id,
        'dataset_id': dataset_id,
    }
    if label:
        base['label'] = label

    try:
        run_info = await asyncio.to_thread(client.run(run_id).get)

        if run_info is None:
            return {**base, '_type': 'error', 'error': 'Run not found.'}

        status = _attr(run_info, 'status', 'UNKNOWN')
        base['status'] = status

        if status not in _TERMINAL_STATUSES:
            return {**base, '_type': 'pending'}

        if status != 'SUCCEEDED':
            return {**base, '_type': 'error', 'error': f'Run ended with status: {status}'}

        return await _collect_dataset(client, limit, run_id, dataset_id, base)

    except Exception as exc:
        logger.warning('apify_collect error for run %s: %s', run_id, exc)
        return {**base, '_type': 'error', 'error': str(exc)}


async def _collect_dataset(
    client: Any, limit: int, run_id: str, dataset_id: str, base: dict[str, Any]
) -> dict[str, Any]:
    dataset_result = await asyncio.to_thread(client.dataset(dataset_id).list_items, limit=limit)
    items = list(_attr(dataset_result, 'items') or [])
    may_have_more = len(items) == limit
    if may_have_more:
        logger.warning(
            'apify_collect run %s: fetched %d items (hit limit=%d) — '
            'dataset may have more; re-call with a higher limit if needed',
            run_id,
            len(items),
            limit,
        )
    raw = json.dumps(items, indent=2, default=str)
    if len(raw) > _MAX_CONTENT_CHARS:
        raw = raw[:_MAX_CONTENT_CHARS] + '\n\n[…truncated]'
    wrapped = '<<<EXTERNAL_UNTRUSTED_CONTENT>>>\n' + raw + '\n<<<END_EXTERNAL_UNTRUSTED_CONTENT>>>'
    result: dict[str, Any] = {
        **base,
        '_type': 'completed',
        'result_count': len(items),
        'data': wrapped,
    }
    if may_have_more:
        result['may_have_more'] = True
    return result


async def _collect_handler(args: dict[str, Any]) -> dict[str, Any]:
    from tools.interrupt import is_interrupted

    if is_interrupted():
        return {'error': 'Interrupted'}

    run_refs = args.get('runs') or []
    if not run_refs:
        return {'error': "Provide 'runs' array (from apify_start)."}

    limit = int(args.get('limit') or _COLLECT_DEFAULT_LIMIT)
    client = _get_client()

    raw_results = await asyncio.gather(*[_check_run(client, limit, ref) for ref in run_refs])

    completed: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for r in raw_results:
        t = r.pop('_type', 'error')
        if t == 'pending':
            pending.append(r)
        elif t == 'error':
            errors.append(r)
        else:
            completed.append(r)

    return {
        'all_done': len(pending) == 0,
        'completed': completed,
        'pending': pending,
        'errors': errors,
    }


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_DISCOVER_SCHEMA: dict[str, Any] = {
    'name': 'apify_discover',
    'description': (
        "Search the Apify Store for Actors by keyword, or fetch an Actor's "
        "input schema and README. Provide 'query' to search, or 'actor_id' "
        'to inspect a specific Actor. Actor IDs accept either the unique ID '
        'or the username~actor-name format.'
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'query': {
                'type': 'string',
                'description': "Keywords to search the Apify Store (e.g. 'instagram scraper').",
            },
            'actor_id': {
                'type': 'string',
                'description': (
                    'Actor ID to fetch its input schema and README — either the '
                    "unique ID or 'username~actor-name' (e.g. 'apify~google-search-scraper')."
                ),
            },
        },
    },
}

_START_SCHEMA: dict[str, Any] = {
    'name': 'apify_start',
    'description': (
        'Start one or more Apify Actor runs. Returns run references immediately '
        f'(fire-and-forget). Pass the returned run refs to apify_collect to get results. '
        f'Maximum {_MAX_BATCH_RUNS} runs per call.'
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'runs': {
                'type': 'array',
                'description': f'List of Actor runs to start (max {_MAX_BATCH_RUNS}).',
                'maxItems': _MAX_BATCH_RUNS,
                'items': {
                    'type': 'object',
                    'properties': {
                        'actor_id': {
                            'type': 'string',
                            'description': 'Actor ID (username~actor-name).',
                        },
                        'input': {
                            'type': 'object',
                            'description': 'Actor input parameters.',
                        },
                        'label': {
                            'type': 'string',
                            'description': 'Optional label to identify this run in results.',
                        },
                    },
                    'required': ['actor_id'],
                },
            },
        },
        'required': ['runs'],
    },
}

_COLLECT_SCHEMA: dict[str, Any] = {
    'name': 'apify_collect',
    'description': (
        'Poll the status of Apify Actor runs started with apify_start. '
        'Returns completed results, still-running refs, and errors. '
        'Re-call with the same run refs until all_done is true.'
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'runs': {
                'type': 'array',
                'description': 'Run references returned by apify_start.',
                'items': {
                    'type': 'object',
                    'properties': {
                        'run_id': {'type': 'string'},
                        'actor_id': {'type': 'string'},
                        'dataset_id': {'type': 'string'},
                        'label': {'type': 'string'},
                    },
                    'required': ['run_id', 'actor_id', 'dataset_id'],
                },
            },
            'limit': {
                'type': 'integer',
                'description': (
                    f'Max dataset items to fetch per run (default {_COLLECT_DEFAULT_LIMIT}). '
                    'Increase if may_have_more is true in a previous response.'
                ),
            },
        },
        'required': ['runs'],
    },
}


# ---------------------------------------------------------------------------
# String-returning wrappers consumed by register(ctx) in __init__.py
# ---------------------------------------------------------------------------


def discover_handler_str(args: dict[str, Any], **_kw: Any) -> str:
    """String-returning wrapper around `_discover_handler`, for hermes-agent's tool dispatcher."""
    return json.dumps(_discover_handler(args), default=str)


def start_handler_str(args: dict[str, Any], **_kw: Any) -> str:
    """String-returning wrapper around `_start_handler`, for hermes-agent's tool dispatcher."""
    return json.dumps(_start_handler(args), default=str)


async def collect_handler_str(args: dict[str, Any], **_kw: Any) -> str:
    """String-returning wrapper around `_collect_handler`, for hermes-agent's tool dispatcher."""
    return json.dumps(await _collect_handler(args), default=str)
