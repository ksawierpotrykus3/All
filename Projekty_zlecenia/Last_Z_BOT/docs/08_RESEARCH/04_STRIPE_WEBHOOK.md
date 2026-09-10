# Research — Stripe webhook i aktywacja licencji

## Kontekst (co wiemy, bez wnioskowania)
- Backend FastAPI tworzy sesję Stripe Checkout z `metadata={"user_id": user.id}` (backend/main.py:213).
- Webhook `checkout.session.completed` wyszukuje użytkownika po adresie email płatnika (backend/main.py:337-340).
- Backend obsługuje już `customer.subscription.deleted` (main.py:413-427) oraz `customer.subscription.updated` (main.py:395-411) — dezaktywują licencje przy anulowaniu/braku płatności.

## Pytanie badawcze (otwarte)
Jak poprawnie powiązać płatność Stripe z kontem w aplikacji, gdy adres email płatnika może się różnić od adresu w koncie, i jakie są rekomendacje Stripe co do pełnego cyklu subskrypcji (aktywacja, anulowanie, błędy płatności)?

## Czego szukać (bez zakładania odpowiedzi)
- Kiedy używać `client_reference_id` a kiedy `metadata` przy tworzeniu sesji Checkout.
- Jak wygląda poprawny webhook pod kątem idempotencji (duplikaty zdarzeń).
- Czy obsługa `customer.subscription.deleted` + `customer.subscription.updated` jest wystarczająca, czy potrzebne są jeszcze inne zdarzenia (np. `invoice.payment_failed`).
- Jak testować webhooki lokalnie (Stripe CLI).

## Uwaga metodologiczna
Nie zakładaj, że `client_reference_id` jest zawsze lepszy od emaila. Zbierz rekomendacje Stripe i pokaż, w jakich scenariuszach każde podejście zawodzi.