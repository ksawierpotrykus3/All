from unittest.mock import MagicMock, patch
import server
from server import DeepSeek, AccountPool, Session

mock_ap = MagicMock(spec=AccountPool)
mock_ses = MagicMock(spec=Session)
mock_ses.cookies = {}
mock_ses.auth_token = "fake-token"
mock_ses.user_agent = "Mozilla/5.0"
mock_ap.slots = [mock_ses]

ds = DeepSeek(mock_ap)
ds._retry_on_network = lambda fn, *a, max_retries=3, **kw: fn(*a, **kw)
ds._get_pow = lambda idx: "pow-sol"

lines_data = [
    b'data: {"response_message_id": 2}',
    b'data: {"v": {"response": {"fragments": [{"type": "RESPONSE"}]}}}',
    b'data: {"p": "response/fragments/-1/content", "v": "<tool_call name=\"Read\"><parameter name=\"file_path\">test.md</parameter></tool_call>"}',
]
mock_resp = MagicMock()
mock_resp.status_code = 200
mock_resp.iter_lines.return_value = lines_data

with patch("server.requests.post", return_value=mock_resp):
    gen, meta = ds.stream_completion(0, "sess-1", "prompt", parent_message_id=1, _auto_continue_budget=2)
    out = list(gen)
    print("Meta:", meta)
    print("Out:", out)