# Uploading in YouTube Studio

`rlite` prepares everything; you upload by hand (about 5 minutes).

1. Open YouTube Studio → **Create** → **Upload videos** → choose `final/video.mp4`.
2. Open `final/UPLOAD.md` and paste the title, description and tags.
3. Thumbnail: `final/thumbnail.png` (custom thumbnails need a phone-verified channel).
4. Audience: "No, it's not made for kids" (unless the plan says otherwise).
5. **Altered or synthetic content**: follow what `UPLOAD.md` says.
6. Add the video to your niche playlist, then publish or schedule.
7. After 7 days, check retention and click-through rate in Analytics and write down what worked.

## Why not automatic upload?
Videos uploaded through the YouTube API from a Google Cloud project that has not passed Google's
API audit can be locked as private, and Google's documentation is inconsistent on whether they can
ever be made public. Until that is verified, uploading by hand is the safe default. Automatic upload
is planned for a later version.
