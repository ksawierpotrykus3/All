import pytest
from unittest.mock import MagicMock, patch
from server.services.proxy_service import _extract_prompt_parts, _stream_gen


def test_extract_prompt_parts_new_session_merges_user_messages():
    """On new session (is_resume=False), consecutive user messages are merged into user_message."""
    msgs = [
        {"role": "system", "content": "You are assistant."},
        {"role": "user", "content": "<user_info>OS: win32</user_info>"},
        {"role": "user", "content": "<user_query>Audit bot</user_query>"},
    ]
    sp, hist, um = _extract_prompt_parts(msgs, is_resume=False)
    assert sp == "You are assistant."
    assert hist == []
    assert "<user_info>OS: win32</user_info>" in um
    assert "<user_query>Audit bot</user_query>" in um


def test_extract_prompt_parts_resume_does_not_merge_user_messages():
    """In resume mode (is_resume=True), consecutive user messages are NOT merged by NEW_SESSION_FIX."""
    msgs = [
        {"role": "user", "content": "<open_files>a.py</open_files>"},
        {"role": "user", "content": "continue"},
    ]
    sp, hist, um = _extract_prompt_parts(msgs, is_resume=True)
    assert sp is None
    # Prior user message remains in history, last is in user_message
    assert len(hist) == 1
    assert hist[0]["role"] == "user"
    assert hist[0]["content"] == "<open_files>a.py</open_files>"
    assert um == "continue"


def test_native_continue_triggers_when_tools_present_and_stopped_after_thinking():
    """Native continue must trigger if model stops prematurely after thinking without tool call or response."""
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "kontynuuj"},
    ]
    tools = [{"name": "Shell", "description": "run shell"}]
    stream_meta = {
        "resp_msg_id": 436,
        "thinking_fallback": "I need to run the debug script. Let me just run it.",
    }

    def fake_empty_gen():
        return
        yield

    fake_stream = fake_empty_gen()
    continue_called = []

    def fake_stream_continue(account_idx, chat_id, message_id, **kwargs):
        continue_called.append((account_idx, chat_id, message_id, kwargs))
        def _dummy():
            yield 'data: {"v": {"response": {"message_id": 436, "status": "FINISHED", "fragments": [{"fragment": "ok"}]}}}'
        return _dummy(), {"resp_msg_id": 436}

    mock_ds = MagicMock()
    mock_ds.stream_continue = fake_stream_continue

    with patch("server.services.proxy_service.ds", mock_ds), \
         patch("server.services.proxy_service.rate_limiter"), \
         patch("server.services.proxy_service._save_state"), \
         patch("server.services.proxy_service._dashboard"):
        chunks = list(_stream_gen(
            stream_gen=fake_stream,
            stream_meta=stream_meta,
            messages=messages,
            parent_id="435",
            chat_id="chat-123",
            conv_uuid="conv-123",
            account_idx=0,
            tools=tools,
            model="deepseek-chat",
            t0=0.0,
            t4=0.0,
            prompt="kontynuuj",
            _depth=0,
        ))

    assert len(continue_called) == 1
    acc_idx, cid, mid, kw = continue_called[0]
    assert acc_idx == 0
    assert cid == "chat-123"
    assert mid == 436


def test_is_intent_without_action():
    from server.services.proxy_service import _is_intent_without_action
    # Polish action statements
    assert _is_intent_without_action("Parsuję HAR programowo, żeby wyciągnąć body builda, PUT i odpowiedzi.")
    assert _is_intent_without_action("Mam już kluczowe dowody z APK. Dokańczam weryfikację HAR i szukam jakiegoś stanu.")
    assert _is_intent_without_action("Czytam kluczowe pliki APK i przeszukuję HAR pod kątem trwałego stanu.")
    assert _is_intent_without_action("Sprawdzam kod.")
    assert _is_intent_without_action("Zaraz uruchomię skrypt.")
    assert _is_intent_without_action("Wynik znowu 99 — znalazłem prawdziwą przyczynę: PAYMENT_ON_BUILD_CHECKSUM odpala payment z checksumem builda zanim PUT się wykona, dostaje 99 i oznacza paid, więc poprawny payment po PUT jest blokowany. Naprawiam.")
    assert _is_intent_without_action("Naprawione. Usuwam teraz martwy PAYMENT_ON_BUILD_CHECKSUM (to on powodował payment 99 przed PUT) i porządkuję skrypt.")
    assert _is_intent_without_action("Znalazłem coś istotnego: istnieją realne ciała buildów z selected_pickup_option i pełnymi pickup_options — m.in. build_default_response.json, com_pickup_details_full.json, probe_payment_method_1788842744385.json, point_stability_C_preseed_put_*.json. To otwiera możliwość offline'owej walidacji _extract_route_debug na prawdziwych danych i próby rozstrzygnięcia hipotezy code 99 bez sieci. Deleguję.")
    assert _is_intent_without_action("Deleguję to zadanie do subagenta.")
    # English action statements
    assert _is_intent_without_action("Let me read the key scripts to understand the current state.")
    assert _is_intent_without_action("I will check the configuration file.")
    assert _is_intent_without_action("Checking the repository structure.")
    assert _is_intent_without_action("I will delegate the fix.")
    # Negative cases: final answer or text without intent
    assert not _is_intent_without_action("FINAL ANSWER: Zadanie zostało wykonane.")
    assert not _is_intent_without_action("Oto wyjaśnienie problemu: funkcja X nie działa, ponieważ...")
    assert not _is_intent_without_action("X" * 500)


def test_native_continue_triggers_on_intent_without_action():
    """When model emits a short statement of intent without tool calls, native continue must trigger."""
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "analizuj pliki"},
    ]
    tools = [{"name": "Shell", "description": "run shell"}]
    stream_meta = {
        "resp_msg_id": 501,
        "thinking_fallback": "I should parse the har file now.",
    }

    # Model yields only intent statement in stream
    def fake_intent_stream():
        yield 'Parsuję HAR programowo, żeby wyciągnąć body builda.'

    continue_called = []

    def fake_stream_continue(account_idx, chat_id, message_id, **kwargs):
        continue_called.append((account_idx, chat_id, message_id))
        def _dummy():
            yield 'data: {"v": {"response": {"message_id": 501, "status": "FINISHED", "fragments": [{"fragment": "ok"}]}}}'
        return _dummy(), {"resp_msg_id": 501}

    mock_ds = MagicMock()
    mock_ds.stream_continue = fake_stream_continue

    with patch("server.services.proxy_service.ds", mock_ds), \
         patch("server.services.proxy_service.rate_limiter"), \
         patch("server.services.proxy_service._save_state"), \
         patch("server.services.proxy_service._dashboard"):
        chunks = list(_stream_gen(
            stream_gen=fake_intent_stream(),
            stream_meta=stream_meta,
            messages=messages,
            parent_id="500",
            chat_id="chat-456",
            conv_uuid="conv-456",
            account_idx=0,
            tools=tools,
            model="deepseek-chat",
            t0=0.0,
            t4=0.0,
            prompt="analizuj pliki",
            _depth=0,
        ))

    assert len(continue_called) == 1
    assert continue_called[0] == (0, "chat-456", 501)


def test_native_continue_triggers_without_thinking_fallback():
    """When thinking_fallback is empty/absent but response text contains intent statement, continue must trigger."""
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "sprawdź adres"},
    ]
    tools = [{"name": "Shell", "description": "run shell"}]
    stream_meta = {
        "resp_msg_id": 502,
        # thinking_fallback is absent or empty (normal case when model outputs response text)
    }

    def fake_stream():
        yield "Kluczowe: adres w HAR ma created_at: 2026-09-10T16:44:45 — powstał 27 s przed zapisem HAR. Sprawdzam live, czy build teraz domyślnie daje home."

    continue_called = []

    def fake_stream_continue(account_idx, chat_id, message_id, **kwargs):
        continue_called.append((account_idx, chat_id, message_id))
        def _dummy():
            yield 'data: {"v": {"response": {"message_id": 502, "status": "FINISHED", "fragments": [{"fragment": "ok"}]}}}'
        return _dummy(), {"resp_msg_id": 502}

    mock_ds = MagicMock()
    mock_ds.stream_continue = fake_stream_continue

    with patch("server.services.proxy_service.ds", mock_ds), \
         patch("server.services.proxy_service.rate_limiter"), \
         patch("server.services.proxy_service._save_state"), \
         patch("server.services.proxy_service._dashboard"):
        chunks = list(_stream_gen(
            stream_gen=fake_stream(),
            stream_meta=stream_meta,
            messages=messages,
            parent_id="500",
            chat_id="chat-789",
            conv_uuid="conv-789",
            account_idx=0,
            tools=tools,
            model="deepseek-chat",
            t0=0.0,
            t4=0.0,
            prompt="sprawdź adres",
            _depth=0,
        ))

    assert len(continue_called) == 1
    assert continue_called[0] == (0, "chat-789", 502)


def test_native_continue_triggers_on_repair_and_delete_intents():
    """Verify that action phrases with 'Naprawiam' or 'Usuwam teraz... i porządkuję' trigger stream_continue."""
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "napraw bugi"},
    ]
    tools = [{"name": "Shell", "description": "run shell"}]

    for phrase in [
        "Wynik znowu 99 — znalazłem prawdziwą przyczynę: PAYMENT_ON_BUILD_CHECKSUM odpala payment z checksumem builda zanim PUT się wykona, dostaje 99 i oznacza paid, więc poprawny payment po PUT jest blokowany. Naprawiam.",
        "Naprawione. Usuwam teraz martwy PAYMENT_ON_BUILD_CHECKSUM (to on powodował payment 99 przed PUT) i porządkuję skrypt.",
    ]:
        continue_called = []

        def fake_stream_continue(account_idx, chat_id, message_id, **kwargs):
            continue_called.append((account_idx, chat_id, message_id))
            def _dummy():
                yield 'data: {"v": {"response": {"message_id": 503, "status": "FINISHED", "fragments": [{"fragment": "ok"}]}}}'
            return _dummy(), {"resp_msg_id": 503}

        mock_ds = MagicMock()
        mock_ds.stream_continue = fake_stream_continue

        with patch("server.services.proxy_service.ds", mock_ds), \
             patch("server.services.proxy_service.rate_limiter"), \
             patch("server.services.proxy_service._save_state"), \
             patch("server.services.proxy_service._dashboard"):
            chunks = list(_stream_gen(
                stream_gen=iter([phrase]),
                stream_meta={"resp_msg_id": 503},
                messages=messages,
                parent_id="500",
                chat_id="chat-999",
                conv_uuid="conv-999",
                account_idx=0,
                tools=tools,
                model="deepseek-chat",
                t0=0.0,
                t4=0.0,
                prompt="napraw bugi",
                _depth=0,
            ))

        assert len(continue_called) == 1, f"Failed for phrase: {phrase}"
        assert continue_called[0] == (0, "chat-999", 503)


def test_already_finished_triggers_instant_agentic_reprompt():
    """When stream_continue returns already_finished, proxy must immediately reprompt on the same session."""
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "wykonaj zadanie"},
    ]
    tools = [{"name": "Task", "description": "run task"}]
    phrase = "Znalazłem coś istotnego: istnieją realne ciała buildów... Deleguję."

    continue_called = []
    completion_called = []

    def fake_stream_continue(account_idx, chat_id, message_id, **kwargs):
        continue_called.append((account_idx, chat_id, message_id))
        # DeepSeek says message is already finished on server
        return iter([]), {"already_finished": True, "resp_msg_id": message_id}

    def fake_stream_completion(slot, chat_session_id, prompt, parent_message_id=None, **kwargs):
        completion_called.append((slot, chat_session_id, prompt, parent_message_id))
        def _dummy():
            yield '<|DSML|tool_calls>\n<|DSML|invoke name="Task">\n<|DSML|parameter name="description" string="true">walidacja buildow</|DSML|parameter>\n</|DSML|invoke>\n</|DSML|tool_calls>'
        return _dummy(), {"resp_msg_id": 505}

    mock_ds = MagicMock()
    mock_ds.stream_continue = fake_stream_continue
    mock_ds.stream_completion = fake_stream_completion

    with patch("server.services.proxy_service.ds", mock_ds), \
         patch("server.services.proxy_service.rate_limiter"), \
         patch("server.services.proxy_service._save_state"), \
         patch("server.services.proxy_service._dashboard"):
        chunks = list(_stream_gen(
            stream_gen=iter([phrase]),
            stream_meta={"resp_msg_id": 504},
            messages=messages,
            parent_id="500",
            chat_id="chat-111",
            conv_uuid="conv-111",
            account_idx=0,
            tools=tools,
            model="deepseek-chat",
            t0=0.0,
            t4=0.0,
            prompt="wykonaj zadanie",
            _depth=0,
        ))

    assert len(continue_called) == 1
    assert continue_called[0] == (0, "chat-111", 504)
    # stream_completion must be called with agentic reprompt on the same session
    assert len(completion_called) == 1
    assert completion_called[0][0] == 0
    assert completion_called[0][1] == "chat-111"
    assert "CRITICAL: You are an autonomous coding AGENT with tools" in completion_called[0][2]
    assert completion_called[0][3] == 504
    # The output chunk must contain tool_calls
    tc_chunks = [c for c in chunks if "tool_calls" in c]
    assert len(tc_chunks) > 0


@pytest.mark.parametrize("phrase", [
    "Znalazłem coś, co przeczy wcześniejszym wnioskom. Kopię głębiej.",
    "Kopię dalej w plikach.",
    "Drążę temat tego błędu.",
    "Let me dig in to the logs.",
    "Odkryłem problem w kodzie.",
])
def test_reprompt_triggers_on_kopie_glebiej_and_short_chatter(phrase):
    """Phrases like 'Kopię głębiej.' or short chatter without tool call must trigger agentic reprompt."""
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "zbadaj problem"},
    ]
    tools = [{"name": "Shell", "description": "run shell"}]

    continue_called = []
    completion_called = []

    def fake_stream_continue(account_idx, chat_id, message_id, **kwargs):
        continue_called.append((account_idx, chat_id, message_id))
        def _dummy():
            return
            yield
        return _dummy(), {"already_finished": True, "resp_msg_id": message_id}

    def fake_stream_completion(slot, chat_session_id, prompt, parent_message_id, **kwargs):
        completion_called.append((slot, chat_session_id, prompt, parent_message_id))
        def _dummy():
            yield '<|DSML|tool_calls>\n<|DSML|invoke name="Shell">\n<|DSML|parameter name="command" string="true">python check.py</|DSML|parameter>\n</|DSML|invoke>\n</|DSML|tool_calls>'
        return _dummy(), {"resp_msg_id": 605}

    mock_ds = MagicMock()
    mock_ds.stream_continue = fake_stream_continue
    mock_ds.stream_completion = fake_stream_completion

    with patch("server.services.proxy_service.ds", mock_ds), \
         patch("server.services.proxy_service.rate_limiter"), \
         patch("server.services.proxy_service._save_state"), \
         patch("server.services.proxy_service._dashboard"):
        chunks = list(_stream_gen(
            stream_gen=iter([phrase]),
            stream_meta={"resp_msg_id": 604},
            messages=messages,
            parent_id="600",
            chat_id="chat-222",
            conv_uuid="conv-222",
            account_idx=0,
            tools=tools,
            model="deepseek-chat",
            t0=0.0,
            t4=0.0,
            prompt="zbadaj problem",
            _depth=0,
        ))

    assert len(completion_called) == 1
    assert completion_called[0][1] == "chat-222"
    assert "CRITICAL: You are an autonomous coding AGENT with tools" in completion_called[0][2]
    tc_chunks = [c for c in chunks if "tool_calls" in c]
    assert len(tc_chunks) > 0





