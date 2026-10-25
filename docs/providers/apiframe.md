# Suno via Apiframe (optional, disabled by default)

Read before enabling:
- Suno has no official API. Apiframe is an unofficial intermediary that can change or be blocked.
- Suno grants usage rights, not ownership, and the generating account is Apiframe's, not yours:
  high risk for monetized channels.
- Requests can be blocked by Cloudflare. Credits are billed by Apiframe and do not roll over.

Enable it yourself, in your terminal: `rlite providers enable suno` (you will be asked to type a
confirmation), then add your key: `rlite key set apiframe`. Each track costs 11 Apiframe credits and
produces two takes; `rlite` picks the combination with the smoothest transitions.
