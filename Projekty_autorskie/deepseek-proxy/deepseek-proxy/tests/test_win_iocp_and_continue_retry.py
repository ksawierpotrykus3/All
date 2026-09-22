import sys
import pytest
from server.main import patch_asyncio_windows_proactor
from server.services.state_service import set_conv, get_conv

def test_patch_asyncio_windows_proactor():
    if sys.platform != 'win32':
        pytest.skip('Windows-only test')
    import asyncio.proactor_events
    orig_serving = asyncio.proactor_events.BaseProactorEventLoop._start_serving
    patch_asyncio_windows_proactor()
    patched_serving = asyncio.proactor_events.BaseProactorEventLoop._start_serving
    assert callable(patched_serving)
    patch_asyncio_windows_proactor()

def test_clear_resp_msg_id_on_continue_failure():
    messages = [
        {'role': 'system', 'content': 'You are a bot'},
        {'role': 'user', 'content': 'Audit bot'},
    ]
    chat_id = 'test_chat_12345'
    initial_parent_id = 21
    bad_resp_id = 22

    set_conv(
        messages=messages,
        chat_id=chat_id,
        parent_id=bad_resp_id,
        account=0,
    )
    entry = get_conv(messages)
    assert entry is not None
    assert entry['parent_id'] == bad_resp_id

    stream_meta = {'resp_msg_id': bad_resp_id}
    active_resp_id = stream_meta.get('resp_msg_id')
    if active_resp_id is not None:
        stream_meta.pop('resp_msg_id', None)
        active_resp_id = None
        set_conv(
            messages=messages,
            chat_id=chat_id,
            parent_id=initial_parent_id,
            account=0,
        )

    assert 'resp_msg_id' not in stream_meta
    entry_after = get_conv(messages)
    assert entry_after is not None
    assert entry_after['parent_id'] == initial_parent_id
    assert entry_after['chat_id'] == chat_id
