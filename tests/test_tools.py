"""Tests for apify_hermes_agent_plugin.tools — all mocked, no live Actor calls."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client(monkeypatch):
    """Patch _get_client to return a MagicMock client.

    NOTE: _attr() checks hasattr() first, which always returns True on MagicMock.
    The 'default' argument in _attr() is never used on MagicMock objects.
    Always explicitly set every attribute you want to read in your tests.
    """
    client = MagicMock()
    monkeypatch.setattr(
        'apify_hermes_agent_plugin.tools._get_client',
        lambda: client,
    )
    return client


@pytest.fixture(autouse=True)
def not_interrupted(monkeypatch):
    """Default: is_interrupted() returns False."""
    monkeypatch.setattr('tools.interrupt.is_interrupted', lambda: False)


# ---------------------------------------------------------------------------
# apify_discover — store search
# ---------------------------------------------------------------------------


class TestDiscoverStoreSearch:
    def test_returns_actors_list(self, mock_client):
        # apify-client 3.x returns Pydantic models, whose attributes are the
        # snake_case field name (e.g. `total_runs`), not the camelCase JSON
        # alias (`totalRuns`) — mock the real attribute names here.
        actor_mock = MagicMock()
        actor_mock.username = 'apify'
        actor_mock.name = 'instagram-scraper'
        actor_mock.title = 'Instagram Scraper'
        actor_mock.description = 'Scrapes Instagram profiles.'
        stats_mock = MagicMock()
        stats_mock.total_runs = 50000
        actor_mock.stats = stats_mock

        list_result = MagicMock()
        list_result.items = [actor_mock]
        mock_client.store.return_value.list.return_value = list_result

        from apify_hermes_agent_plugin.tools import _discover_handler

        result = _discover_handler({'query': 'instagram scraper'})

        assert 'actors' in result
        assert len(result['actors']) == 1
        a = result['actors'][0]
        assert a['actor_id'] == 'apify~instagram-scraper'
        assert a['name'] == 'instagram-scraper'
        assert a['title'] == 'Instagram Scraper'
        assert a['username'] == 'apify'
        assert a['run_count'] == 50000
        mock_client.store.return_value.list.assert_called_once_with(
            search='instagram scraper', limit=10, sort_by='relevance'
        )

    def test_description_truncated_to_200_chars(self, mock_client):
        actor_mock = MagicMock()
        actor_mock.username = 'apify'
        actor_mock.name = 'test-actor'
        actor_mock.title = 'Test'
        actor_mock.description = 'x' * 300
        actor_mock.stats = MagicMock(total_runs=0)

        list_result = MagicMock()
        list_result.items = [actor_mock]
        mock_client.store.return_value.list.return_value = list_result

        from apify_hermes_agent_plugin.tools import _discover_handler

        result = _discover_handler({'query': 'test'})

        assert len(result['actors'][0]['description']) == 200

    def test_store_search_api_error_returns_error_dict(self, mock_client):
        mock_client.store.return_value.list.side_effect = RuntimeError('API error')

        from apify_hermes_agent_plugin.tools import _discover_handler

        result = _discover_handler({'query': 'test'})

        assert 'error' in result
        assert 'API error' in result['error']


# ---------------------------------------------------------------------------
# apify_discover — actor schema fetch
# ---------------------------------------------------------------------------


class TestDiscoverActorSchema:
    def _setup_build_mock(self, mock_client, *, input_schema=None, readme=None):
        """Helper: wire up actor + build mock chain for default_build() path."""
        actor_info = MagicMock()
        actor_info.username = 'apify'
        actor_info.name = 'google-search-scraper'
        actor_info.title = 'Google Search Scraper'
        actor_info.description = 'Scrapes Google Search.'
        mock_client.actor.return_value.get.return_value = actor_info

        # Build.actor_definition / Build.input_schema are the real (snake_case)
        # Pydantic attribute names on apify-client 3.x — see note in _discover_actor().
        build_detail = MagicMock()
        actor_def = MagicMock()
        actor_def.input = input_schema  # dict or None
        actor_def.readme = readme
        build_detail.actor_definition = actor_def
        build_detail.input_schema = None
        build_detail.readme = None
        mock_client.actor.return_value.default_build.return_value.get.return_value = build_detail

        return actor_info, build_detail

    def test_returns_actor_schema(self, mock_client):
        schema = {'type': 'object', 'properties': {'query': {'type': 'string'}}}
        self._setup_build_mock(mock_client, input_schema=schema, readme='# README content')

        from apify_hermes_agent_plugin.tools import _discover_handler

        result = _discover_handler({'actor_id': 'apify~google-search-scraper'})

        assert result['actor_id'] == 'apify~google-search-scraper'
        assert result['name'] == 'google-search-scraper'
        assert result['title'] == 'Google Search Scraper'
        assert result['username'] == 'apify'
        assert result['description'] == 'Scrapes Google Search.'
        assert json.loads(result['input_schema']) == schema
        assert result['readme'] == '# README content'
        assert 'apify_start' in result['tip']
        assert 'apify~google-search-scraper' in result['tip']

    def test_readme_truncated_to_3000_chars(self, mock_client):
        self._setup_build_mock(mock_client, readme='R' * 4000)

        from apify_hermes_agent_plugin.tools import _discover_handler

        result = _discover_handler({'actor_id': 'apify~google-search-scraper'})

        assert len(result['readme']) == 3000

    def test_falls_back_to_build_input_schema_string(self, mock_client):
        """When actor_definition.input is None, fall back to build.input_schema string."""
        _, build_detail = self._setup_build_mock(mock_client, input_schema=None)
        build_detail.input_schema = '{"type":"object"}'
        build_detail.actor_definition.input = None

        from apify_hermes_agent_plugin.tools import _discover_handler

        result = _discover_handler({'actor_id': 'apify~google-search-scraper'})

        assert result['input_schema'] == '{"type":"object"}'

    def test_actor_not_found_returns_error(self, mock_client):
        mock_client.actor.return_value.get.return_value = None

        from apify_hermes_agent_plugin.tools import _discover_handler

        result = _discover_handler({'actor_id': 'apify~nonexistent'})

        assert 'error' in result
        assert 'not found' in result['error']


# ---------------------------------------------------------------------------
# apify_discover — validation
# ---------------------------------------------------------------------------


class TestDiscoverValidation:
    def test_missing_both_params_returns_error(self, mock_client):
        from apify_hermes_agent_plugin.tools import _discover_handler

        result = _discover_handler({})
        assert 'error' in result
        assert 'query' in result['error']
        assert 'actor_id' in result['error']

    def test_empty_string_params_treated_as_missing(self, mock_client):
        from apify_hermes_agent_plugin.tools import _discover_handler

        result = _discover_handler({'query': '  ', 'actor_id': ''})
        assert 'error' in result

    def test_interrupted_returns_error(self, mock_client, monkeypatch):
        monkeypatch.setattr('tools.interrupt.is_interrupted', lambda: True)
        from apify_hermes_agent_plugin.tools import _discover_handler

        result = _discover_handler({'query': 'test'})
        assert result == {'error': 'Interrupted'}
        mock_client.store.assert_not_called()


# ---------------------------------------------------------------------------
# apify_start
# ---------------------------------------------------------------------------


class TestStart:
    def _make_run_mock(self, run_id='r1', dataset_id='d1', status='QUEUED'):
        run = MagicMock()
        run.id = run_id
        run.default_dataset_id = dataset_id
        run.status = status
        return run

    def test_single_run_returns_run_ref(self, mock_client):
        mock_client.actor.return_value.start.return_value = self._make_run_mock()

        from apify_hermes_agent_plugin.tools import _start_handler

        result = _start_handler({'runs': [{'actor_id': 'apify~test', 'input': {'key': 'val'}}]})

        assert 'runs' in result
        assert len(result['runs']) == 1
        r = result['runs'][0]
        assert r['run_id'] == 'r1'
        assert r['actor_id'] == 'apify~test'
        assert r['dataset_id'] == 'd1'
        assert r['status'] == 'QUEUED'
        mock_client.actor.return_value.start.assert_called_once_with(run_input={'key': 'val'})

    def test_label_included_when_provided(self, mock_client):
        mock_client.actor.return_value.start.return_value = self._make_run_mock()

        from apify_hermes_agent_plugin.tools import _start_handler

        result = _start_handler({'runs': [{'actor_id': 'apify~test', 'input': {}, 'label': 'my-run'}]})

        assert result['runs'][0]['label'] == 'my-run'

    def test_label_absent_when_not_provided(self, mock_client):
        mock_client.actor.return_value.start.return_value = self._make_run_mock()

        from apify_hermes_agent_plugin.tools import _start_handler

        result = _start_handler({'runs': [{'actor_id': 'apify~test', 'input': {}}]})

        assert 'label' not in result['runs'][0]

    def test_batch_start_two_runs(self, mock_client):
        run1 = self._make_run_mock(run_id='r1', dataset_id='d1')
        run2 = self._make_run_mock(run_id='r2', dataset_id='d2')
        mock_client.actor.return_value.start.side_effect = [run1, run2]

        from apify_hermes_agent_plugin.tools import _start_handler

        result = _start_handler(
            {
                'runs': [
                    {'actor_id': 'apify~actor-a', 'input': {}},
                    {'actor_id': 'apify~actor-b', 'input': {}},
                ]
            }
        )

        assert len(result['runs']) == 2
        assert result['runs'][0]['run_id'] == 'r1'
        assert result['runs'][1]['run_id'] == 'r2'

    def test_per_run_api_error_goes_to_errors(self, mock_client):
        mock_client.actor.return_value.start.side_effect = RuntimeError('not found')

        from apify_hermes_agent_plugin.tools import _start_handler

        result = _start_handler({'runs': [{'actor_id': 'apify~bad-actor', 'input': {}}]})

        assert result['runs'] == []
        assert len(result['errors']) == 1
        assert 'not found' in result['errors'][0]['error']

    def test_interrupted_returns_early(self, mock_client, monkeypatch):
        monkeypatch.setattr('tools.interrupt.is_interrupted', lambda: True)

        from apify_hermes_agent_plugin.tools import _start_handler

        result = _start_handler({'runs': [{'actor_id': 'apify~test', 'input': {}}]})

        assert result == {'error': 'Interrupted'}
        mock_client.actor.assert_not_called()

    def test_interrupt_mid_batch_stops_remaining_runs(self, mock_client, monkeypatch):
        call_count = 0
        original_run = self._make_run_mock()

        def start_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original_run

        mock_client.actor.return_value.start.side_effect = start_side_effect

        # entry check → False, loop iter 1 → False (fires run), loop iter 2 → True (stops)
        interrupted_after_first = iter([False, False, True])
        monkeypatch.setattr('tools.interrupt.is_interrupted', lambda: next(interrupted_after_first))

        from apify_hermes_agent_plugin.tools import _start_handler

        result = _start_handler(
            {
                'runs': [
                    {'actor_id': 'apify~actor-a', 'input': {}},
                    {'actor_id': 'apify~actor-b', 'input': {}},
                    {'actor_id': 'apify~actor-c', 'input': {}},
                ]
            }
        )

        assert call_count == 1  # only the first run fired before interrupt
        assert len(result['runs']) == 1

    def test_batch_over_limit_returns_error(self, mock_client):
        from apify_hermes_agent_plugin.tools import _MAX_BATCH_RUNS, _start_handler

        oversized = [{'actor_id': f'apify~actor-{i}', 'input': {}} for i in range(_MAX_BATCH_RUNS + 1)]
        result = _start_handler({'runs': oversized})
        assert 'error' in result
        assert str(_MAX_BATCH_RUNS) in result['error']
        mock_client.actor.assert_not_called()


# ---------------------------------------------------------------------------
# apify_collect — non-terminal states and errors
# ---------------------------------------------------------------------------


class TestCollectNonTerminal:
    @pytest.mark.asyncio
    async def test_running_run_goes_to_pending(self, mock_client):
        run_info = MagicMock()
        run_info.status = 'RUNNING'
        mock_client.run.return_value.get.return_value = run_info

        from apify_hermes_agent_plugin.tools import _collect_handler

        result = await _collect_handler({'runs': [{'run_id': 'r1', 'actor_id': 'apify~test', 'dataset_id': 'd1'}]})

        assert result['all_done'] is False
        assert len(result['pending']) == 1
        assert result['pending'][0]['run_id'] == 'r1'
        assert result['pending'][0]['status'] == 'RUNNING'
        assert result['completed'] == []
        assert result['errors'] == []

    @pytest.mark.asyncio
    async def test_queued_run_goes_to_pending(self, mock_client):
        run_info = MagicMock()
        run_info.status = 'QUEUED'
        mock_client.run.return_value.get.return_value = run_info

        from apify_hermes_agent_plugin.tools import _collect_handler

        result = await _collect_handler({'runs': [{'run_id': 'r1', 'actor_id': 'apify~test', 'dataset_id': 'd1'}]})

        assert result['all_done'] is False
        assert result['pending'][0]['status'] == 'QUEUED'

    @pytest.mark.asyncio
    async def test_failed_run_goes_to_errors(self, mock_client):
        run_info = MagicMock()
        run_info.status = 'FAILED'
        mock_client.run.return_value.get.return_value = run_info

        from apify_hermes_agent_plugin.tools import _collect_handler

        result = await _collect_handler({'runs': [{'run_id': 'r1', 'actor_id': 'apify~test', 'dataset_id': 'd1'}]})

        assert result['all_done'] is True  # no pending
        assert result['errors'][0]['status'] == 'FAILED'
        assert 'FAILED' in result['errors'][0]['error']

    @pytest.mark.asyncio
    async def test_aborted_run_goes_to_errors(self, mock_client):
        run_info = MagicMock()
        run_info.status = 'ABORTED'
        mock_client.run.return_value.get.return_value = run_info

        from apify_hermes_agent_plugin.tools import _collect_handler

        result = await _collect_handler({'runs': [{'run_id': 'r1', 'actor_id': 'apify~test', 'dataset_id': 'd1'}]})

        assert result['errors'][0]['status'] == 'ABORTED'

    @pytest.mark.asyncio
    async def test_run_not_found_goes_to_errors(self, mock_client):
        mock_client.run.return_value.get.return_value = None

        from apify_hermes_agent_plugin.tools import _collect_handler

        result = await _collect_handler({'runs': [{'run_id': 'r1', 'actor_id': 'apify~test', 'dataset_id': 'd1'}]})

        assert 'not found' in result['errors'][0]['error']

    @pytest.mark.asyncio
    async def test_label_preserved_in_pending(self, mock_client):
        run_info = MagicMock()
        run_info.status = 'RUNNING'
        mock_client.run.return_value.get.return_value = run_info

        from apify_hermes_agent_plugin.tools import _collect_handler

        result = await _collect_handler(
            {'runs': [{'run_id': 'r1', 'actor_id': 'apify~test', 'dataset_id': 'd1', 'label': 'instagram'}]}
        )

        assert result['pending'][0]['label'] == 'instagram'


# ---------------------------------------------------------------------------
# apify_collect — succeeded path, output shape, size cap and paging
# ---------------------------------------------------------------------------

# Hermes' default per-result threshold: a tool result longer than this is saved to a file and the
# model only sees a ~1.5K-char preview of it (tools/budget_config.py::DEFAULT_RESULT_SIZE_CHARS).
_HERMES_RESULT_SIZE_CHARS = 100_000


def _ref(n=1, **extra):
    return {'run_id': f'r{n}', 'actor_id': 'apify~test', 'dataset_id': f'd{n}', **extra}


def _succeed_with_items(mock_client, items_by_dataset):
    """Make every run SUCCEEDED and serve each dataset's items from `items_by_dataset`."""
    mock_client.run.return_value.get.return_value = MagicMock(status='SUCCEEDED')
    datasets = {
        dataset_id: MagicMock(list_items=MagicMock(return_value=MagicMock(items=items)))
        for dataset_id, items in items_by_dataset.items()
    }
    mock_client.dataset.side_effect = datasets.__getitem__
    return datasets


class TestCollectSucceeded:
    @pytest.mark.asyncio
    async def test_succeeded_fetches_dataset_items(self, mock_client):
        items = [{'title': 'Result 1', 'url': 'https://example.com'}]
        datasets = _succeed_with_items(mock_client, {'d1': items})

        from apify_hermes_agent_plugin.tools import _COLLECT_DEFAULT_LIMIT, _collect_handler

        result = await _collect_handler({'runs': [_ref()]})

        assert result['all_done'] is True
        assert len(result['completed']) == 1
        c = result['completed'][0]
        assert c['status'] == 'SUCCEEDED'
        assert c['result_count'] == 1
        assert c['data'] == items
        assert 'truncated' not in c
        datasets['d1'].list_items.assert_called_once_with(offset=0, limit=_COLLECT_DEFAULT_LIMIT)

    @pytest.mark.asyncio
    async def test_tool_output_parses_as_plain_json(self, mock_client):
        # Regression test for #23: `data` used to be a JSON *string* wrapped in
        # <<<EXTERNAL_UNTRUSTED_CONTENT>>> markers, so json.loads() on it failed.
        items = [{'title': 'Result 1', 'rating': 4.5, 'tags': ['a', 'b']}, {'title': 'Result 2'}]
        _succeed_with_items(mock_client, {'d1': items})

        from apify_hermes_agent_plugin.tools import collect_handler_str

        output = await collect_handler_str({'runs': [_ref()]})

        assert json.loads(output)['completed'][0]['data'] == items
        assert 'EXTERNAL_UNTRUSTED_CONTENT' not in output

    @pytest.mark.asyncio
    async def test_tool_output_keeps_non_ascii_text_readable(self, mock_client):
        _succeed_with_items(mock_client, {'d1': [{'name': 'Kavárna Café Praha 😀'}]})

        from apify_hermes_agent_plugin.tools import collect_handler_str

        output = await collect_handler_str({'runs': [_ref()]})

        assert 'Kavárna Café Praha 😀' in output

    @pytest.mark.asyncio
    async def test_oversized_dataset_is_cut_between_whole_items(self, mock_client):
        items = [{'i': i, 'text': 'x' * 1000} for i in range(100)]
        _succeed_with_items(mock_client, {'d1': items})

        from apify_hermes_agent_plugin.tools import _MAX_DATA_CHARS, _collect_handler

        result = await _collect_handler({'runs': [_ref()]})

        c = result['completed'][0]
        returned = len(c['data'])
        assert 0 < returned < len(items)
        assert c['data'] == items[:returned]
        assert c['result_count'] == returned
        assert c['truncated'] is True
        assert c['may_have_more'] is True
        assert c['next_offset'] == returned
        assert len(json.dumps(c['data'], ensure_ascii=False)) <= _MAX_DATA_CHARS

    @pytest.mark.asyncio
    async def test_run_ref_offset_is_forwarded_and_continued(self, mock_client):
        items = [{'i': i, 'text': 'x' * 1000} for i in range(100)]
        datasets = _succeed_with_items(mock_client, {'d1': items})

        from apify_hermes_agent_plugin.tools import _COLLECT_DEFAULT_LIMIT, _collect_handler

        result = await _collect_handler({'runs': [_ref(offset=40)]})

        datasets['d1'].list_items.assert_called_once_with(offset=40, limit=_COLLECT_DEFAULT_LIMIT)
        c = result['completed'][0]
        assert c['next_offset'] == 40 + len(c['data'])

    @pytest.mark.asyncio
    async def test_many_large_runs_stay_under_hermes_result_threshold(self, mock_client):
        from apify_hermes_agent_plugin.tools import _MAX_BATCH_RUNS, collect_handler_str

        refs = [_ref(n) for n in range(1, _MAX_BATCH_RUNS + 1)]
        _succeed_with_items(
            mock_client,
            {ref['dataset_id']: [{'i': i, 'text': 'é' * 1000} for i in range(100)] for ref in refs},
        )

        output = await collect_handler_str({'runs': refs})

        assert len(output) < _HERMES_RESULT_SIZE_CHARS
        completed = json.loads(output)['completed']
        assert len(completed) == _MAX_BATCH_RUNS
        assert all(c['data'] and c['may_have_more'] for c in completed)

    @pytest.mark.asyncio
    async def test_small_run_leaves_unused_budget_to_large_run(self, mock_client):
        small = [{'name': 'only item'}]
        large = [{'i': i, 'text': 'x' * 1000} for i in range(100)]
        _succeed_with_items(mock_client, {'d1': small, 'd2': large})

        from apify_hermes_agent_plugin.tools import _MAX_DATA_CHARS, _collect_handler

        result = await _collect_handler({'runs': [_ref(1), _ref(2)]})

        small_run, large_run = result['completed']
        assert small_run['data'] == small
        assert 'truncated' not in small_run
        # An even split would cap the large run at half the budget.
        assert len(json.dumps(large_run['data'])) > _MAX_DATA_CHARS * 0.9

    @pytest.mark.asyncio
    async def test_single_oversized_item_has_long_strings_shortened(self, mock_client):
        item = {'url': 'https://example.com', 'content': {'pages': ['y' * 200_000]}}
        _succeed_with_items(mock_client, {'d1': [item]})

        from apify_hermes_agent_plugin.tools import _MAX_DATA_CHARS, _collect_handler

        result = await _collect_handler({'runs': [_ref()]})

        c = result['completed'][0]
        assert c['result_count'] == 1
        returned = c['data'][0]
        assert returned['url'] == 'https://example.com'
        page = returned['content']['pages'][0]
        assert page.startswith('yyyy')
        assert '…[truncated' in page
        assert len(json.dumps(c['data'], ensure_ascii=False)) <= _MAX_DATA_CHARS
        assert c['truncated'] is True
        assert 'may_have_more' not in c  # the dataset held just this one item

    @pytest.mark.asyncio
    async def test_oversized_item_keeps_most_of_the_budget(self, mock_client):
        _succeed_with_items(mock_client, {'d1': [{'text': 't' * 60_000}]})

        from apify_hermes_agent_plugin.tools import _MAX_DATA_CHARS, _collect_handler

        result = await _collect_handler({'runs': [_ref()]})

        size = len(json.dumps(result['completed'][0]['data'], ensure_ascii=False))
        assert _MAX_DATA_CHARS * 0.95 < size <= _MAX_DATA_CHARS

    @pytest.mark.asyncio
    async def test_item_that_does_not_fit_its_share_is_deferred_whole(self, mock_client):
        """In a batch, an item too big for its run's share is never shortened (issue #23 follow-up).

        It's deferred to a later page instead: `next_offset` stays put, so it isn't skipped.
        """
        from apify_hermes_agent_plugin.tools import _MAX_BATCH_RUNS, _collect_handler

        refs = [_ref(n) for n in range(1, _MAX_BATCH_RUNS + 1)]
        pages = [{'i': i, 'text': 'w' * 8000} for i in range(5)]
        _succeed_with_items(mock_client, {ref['dataset_id']: pages for ref in refs})

        result = await _collect_handler({'runs': refs})

        completed = result['completed']
        assert all(item['text'] == 'w' * 8000 for c in completed for item in c['data'])
        assert any(c['data'] for c in completed)
        deferred = [c for c in completed if not c['data']]
        assert deferred
        for c in deferred:
            assert c['may_have_more'] is True
            assert c['next_offset'] == 0
            assert c['collect_alone'] is True

        alone = await _collect_handler({'runs': [_ref(int(deferred[0]['run_id'].removeprefix('r')))]})
        assert alone['completed'][0]['data'] == pages

    @pytest.mark.asyncio
    async def test_oversized_item_in_batch_is_deferred_until_collected_alone(self, mock_client):
        _succeed_with_items(mock_client, {'d1': [{'name': 'small'}], 'd2': [{'text': 'y' * 200_000}]})

        from apify_hermes_agent_plugin.tools import _MAX_DATA_CHARS, _collect_handler

        batch = await _collect_handler({'runs': [_ref(1), _ref(2)]})

        small_run, big_run = batch['completed']
        assert small_run['data'] == [{'name': 'small'}]
        assert big_run['data'] == []
        assert big_run['collect_alone'] is True
        assert big_run['next_offset'] == 0

        alone = await _collect_handler({'runs': [_ref(2)]})
        c = alone['completed'][0]
        assert '…[truncated' in c['data'][0]['text']
        assert _MAX_DATA_CHARS * 0.95 < len(json.dumps(c['data'], ensure_ascii=False)) <= _MAX_DATA_CHARS
        assert 'collect_alone' not in c

    @pytest.mark.asyncio
    async def test_all_done_true_when_only_succeeded(self, mock_client):
        _succeed_with_items(mock_client, {'d1': []})

        from apify_hermes_agent_plugin.tools import _collect_handler

        result = await _collect_handler({'runs': [_ref()]})

        assert result['all_done'] is True
        assert result['pending'] == []

    @pytest.mark.asyncio
    async def test_may_have_more_set_when_result_count_equals_limit(self, mock_client):
        from apify_hermes_agent_plugin.tools import _COLLECT_DEFAULT_LIMIT, _collect_handler

        _succeed_with_items(mock_client, {'d1': [{'i': i} for i in range(_COLLECT_DEFAULT_LIMIT)]})

        result = await _collect_handler({'runs': [_ref()]})

        c = result['completed'][0]
        assert c.get('may_have_more') is True
        assert c['next_offset'] == _COLLECT_DEFAULT_LIMIT
        assert 'truncated' not in c

    @pytest.mark.asyncio
    async def test_may_have_more_absent_when_under_limit(self, mock_client):
        _succeed_with_items(mock_client, {'d1': [{'i': 0}]})

        from apify_hermes_agent_plugin.tools import _collect_handler

        result = await _collect_handler({'runs': [_ref()]})

        assert 'may_have_more' not in result['completed'][0]
        assert 'next_offset' not in result['completed'][0]

    @pytest.mark.asyncio
    async def test_custom_limit_forwarded_to_sdk(self, mock_client):
        datasets = _succeed_with_items(mock_client, {'d1': []})

        from apify_hermes_agent_plugin.tools import _collect_handler

        await _collect_handler({'runs': [_ref()], 'limit': 500})

        datasets['d1'].list_items.assert_called_once_with(offset=0, limit=500)


# ---------------------------------------------------------------------------
# apify_collect — mixed states, interrupted, and full workflow
# ---------------------------------------------------------------------------


class TestCollectMixed:
    @pytest.mark.asyncio
    async def test_mixed_pending_and_succeeded(self, mock_client):
        run1_info = MagicMock()
        run1_info.status = 'RUNNING'
        run2_info = MagicMock()
        run2_info.status = 'SUCCEEDED'

        def _run_get_side_effect(run_id):
            m = MagicMock()
            if run_id == 'r1':
                m.get.return_value = run1_info
            else:
                m.get.return_value = run2_info
            return m

        mock_client.run.side_effect = _run_get_side_effect
        mock_client.dataset.return_value.list_items.return_value = MagicMock(items=[{'result': 1}])

        from apify_hermes_agent_plugin.tools import _collect_handler

        result = await _collect_handler(
            {
                'runs': [
                    {'run_id': 'r1', 'actor_id': 'apify~a', 'dataset_id': 'd1'},
                    {'run_id': 'r2', 'actor_id': 'apify~b', 'dataset_id': 'd2'},
                ]
            }
        )

        assert result['all_done'] is False
        assert len(result['pending']) == 1
        assert len(result['completed']) == 1
        assert result['pending'][0]['run_id'] == 'r1'
        assert result['completed'][0]['run_id'] == 'r2'

    @pytest.mark.asyncio
    async def test_interrupted_returns_early(self, mock_client, monkeypatch):
        monkeypatch.setattr('tools.interrupt.is_interrupted', lambda: True)

        from apify_hermes_agent_plugin.tools import _collect_handler

        result = await _collect_handler({'runs': [{'run_id': 'r1', 'actor_id': 'apify~test', 'dataset_id': 'd1'}]})

        assert result == {'error': 'Interrupted'}
        mock_client.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_api_exception_goes_to_errors(self, mock_client):
        mock_client.run.return_value.get.side_effect = RuntimeError('API error')

        from apify_hermes_agent_plugin.tools import _collect_handler

        result = await _collect_handler({'runs': [{'run_id': 'r1', 'actor_id': 'apify~test', 'dataset_id': 'd1'}]})

        assert result['all_done'] is True  # no pending
        assert 'API error' in result['errors'][0]['error']


class TestCollectFullWorkflow:
    """End-to-end: start two runs, collect until all done."""

    @pytest.mark.asyncio
    async def test_start_then_collect_workflow(self, mock_client):
        # apify_start
        run1 = MagicMock(id='r1', default_dataset_id='d1', status='QUEUED')
        run2 = MagicMock(id='r2', default_dataset_id='d2', status='QUEUED')
        mock_client.actor.return_value.start.side_effect = [run1, run2]

        from apify_hermes_agent_plugin.tools import _collect_handler, _start_handler

        start_result = _start_handler(
            {
                'runs': [
                    {'actor_id': 'apify~actor-a', 'input': {}, 'label': 'a'},
                    {'actor_id': 'apify~actor-b', 'input': {}, 'label': 'b'},
                ]
            }
        )
        assert len(start_result['runs']) == 2

        # First collect: both still running
        run_info_running = MagicMock(status='RUNNING')
        mock_client.run.return_value.get.return_value = run_info_running

        collect1 = await _collect_handler({'runs': start_result['runs']})
        assert collect1['all_done'] is False
        assert len(collect1['pending']) == 2

        # Second collect: both succeeded
        run_info_done = MagicMock(status='SUCCEEDED')
        mock_client.run.return_value.get.return_value = run_info_done
        mock_client.dataset.return_value.list_items.return_value = MagicMock(items=[{'row': 1}])

        collect2 = await _collect_handler({'runs': start_result['runs']})
        assert collect2['all_done'] is True
        assert len(collect2['completed']) == 2
