# Security policy

Resonance Lite handles paid API keys, so security reports are taken seriously.

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's private vulnerability reporting:
**Security → Report a vulnerability** on this repository.

Include what you found, how to reproduce it, and the impact. You will get an acknowledgement as soon as possible.

## Scope

- The `rlite` CLI (`cli/`) and the Claude Code plugin (`plugin/`).
- Anything that could leak API keys, spend money without an approved plan, bypass the budget, or make Claude run unintended commands.

Out of scope: vulnerabilities in third-party providers (ElevenLabs, Apiframe, Higgsfield, YouTube). Report those to the provider.
