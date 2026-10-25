# ElevenLabs (required)

- Used for: ambient sound effects (`/v1/sound-generation`, ~22 s per clip, loopable) and music
  (`/v1/music`, up to 10 minutes per call, instrumental forced).
- Account: yours. Paid plans include commercial use; the free plan requires attribution and does
  not allow monetization.
- Key: `rlite key set elevenlabs` in your own terminal. Stored in your OS keychain.
- Not resumable: a call that times out may have been charged, so `rlite` counts it as spent and does
  not retry automatically. Sections of 300 s are safer than 600 s.
- Check your balance: `rlite doctor` (approximate remaining credits).
