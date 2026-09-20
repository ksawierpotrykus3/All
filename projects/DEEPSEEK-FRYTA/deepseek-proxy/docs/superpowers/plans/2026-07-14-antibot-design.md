# Design Specification: DeepSeek Proxy Anti-Bot Mitigation & Session Correlation

## 1. Session Correlation & Reuse
To prevent rapid chat session creation which triggers DeepSeek's bot mitigation, the proxy will correlate incoming requests using context fingerprinting:
* **Context Extraction:** Extract active project directories, modified file paths, and core instruction hashes from incoming messages (ignoring IDE wrapper syntax and rules).
* **Correlation Lookup:** Find the most recently active session in the last 2 hours matching the same workspace context.
* **Reuse:** Append the request to the existing `chat_id` using the last known `parent_message_id`.

## 2. Anti-Bot Protections
* **Payload Size Limits:** Automatically truncate tool outputs (role: `tool`) to a maximum of 4,000 characters to prevent suspiciously large HTTP request bodies.
* **Header Sanitization:** Remove all dynamic `x-hif-*` integrity headers. Use hardcoded Chrome 131 fingerprints and matching TLS configurations via `curl_cffi`.
* **Timing Jitter:** Inject 1.0 - 3.0 seconds of randomized delay between sequential requests on the same session to mimic human input speed.

## 3. History Management
* Limit the context window to the system prompt plus the last 15 messages to prevent hitting context limits on long-running IDE sessions.
