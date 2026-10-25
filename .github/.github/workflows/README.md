# Dino Pals - automatic YouTube channel (free setup)

Every day at a set time, GitHub runs the pipeline in the cloud (your PC can be off):

    Gemini writes the script -> Piper voices the characters -> video + thumbnail are built
    -> uploaded to YouTube as "Made for Kids" -> every Monday analytics are read
    -> data/insights.json steers the next scripts

## One-time setup (about 30-40 minutes)

### 1. Put the code on GitHub
1. Create a free GitHub account and a **public** repository (public = unlimited free run minutes).
2. Upload everything in this folder (keep the `.github` folder; do NOT upload `client_secret.json`).

### 2. Gemini API key (free)
1. Go to Google AI Studio, create an API key.
2. In your GitHub repo: Settings -> Secrets and variables -> Actions -> New repository secret
   -> name `GEMINI_API_KEY`, paste the key.

### 3. YouTube access (the fiddly part - do it carefully)
1. Create a YouTube channel (and verify it with your phone in YouTube Studio -> Settings -> Channel -> Feature eligibility, so custom thumbnails work).
2. Go to Google Cloud Console, create a project, then enable **YouTube Data API v3** and **YouTube Analytics API**.
3. OAuth consent screen: choose External, fill the basic fields, add your own Google account as a test user,
   then click **Publish app** so the status is **"In production"**.
   (If you leave it in "Testing", the login expires after 7 days and the automation silently stops.)
4. Credentials -> Create credentials -> OAuth client ID -> type **Desktop app**. Download the JSON,
   rename it `client_secret.json` and put it in this folder on your computer.
5. On your computer:  `pip install google-auth-oauthlib` then `python tools/get_refresh_token.py`.
   Log in with the Google account that owns the channel (click through the "unverified app" warning).
6. The script prints three values. Add each as a GitHub secret:
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.

### 4. First run
1. GitHub repo -> Actions tab -> **daily-video** -> Run workflow.
2. It takes roughly 15-30 minutes. When it finishes, open YouTube Studio: the video is there as **Private**.
3. Watch it. Check the facts and tone. If you are happy, publish it from Studio.

### 5. Going fully automatic
* New Google Cloud projects can only upload **private** videos through the API until Google approves
  the free "YouTube API Services compliance audit" (search for that phrase; apply with your project number).
  Until it is approved, the daily job uploads privately and you press Publish in Studio (10 seconds a day).
* After approval: repo -> Settings -> Secrets and variables -> Actions -> **Variables** -> new variable
  `UPLOAD_PRIVACY` = `public`.

### 6. Change the schedule
Edit `cron` in `.github/workflows/daily-video.yml`. GitHub uses **UTC**; India time = UTC + 5:30
(4:00 PM IST = `30 10 * * *`).

## Test on your own computer without any accounts
    pip install -r requirements.txt        # also needs ffmpeg installed
    python run_daily.py --mock             # fake script + silent audio, builds video.mp4 and thumbnail, no upload

For the real thing locally: `python tools/download_voice.py`, set `GEMINI_API_KEY`, run `python make_episode.py`.

## Customise
* `characters.json` - characters, voices, rules, the topic pool (add your own topics here).
* `tools/make_assets.py` then `tools/render_assets.py` - redraw characters/backgrounds
  (needs `pip install playwright && playwright install chromium`; commit the PNGs).
* Voices: the `speaker` numbers in `characters.json` are placeholders - listen and pick better ones.

## Things to keep an eye on
* **Failures:** if a run fails, GitHub emails you. Open the Actions tab to see the log.
* **Quality:** review the first 10-20 episodes by hand (facts, tone). Kids' content has strict rules.
* **Monetisation:** YouTube may treat fully templated, mass-produced videos as "inauthentic content".
  Keep improving stories and characters; don't expect ad revenue from day one.
* **Analytics need data:** `insights.json` stays empty until at least 3 episodes have views.
* GitHub pauses scheduled workflows after 60 days without repo activity; the daily history commits keep it alive.
