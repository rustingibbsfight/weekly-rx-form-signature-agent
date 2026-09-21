# Go-live runbook

Step-by-step deployment of the weekly Rx form agent, in the order that avoids backtracking. The Slack channel is eve's native implementation (`slackChannel` + Vercel Connect) — there is no Slack app to configure by hand. For Google credentials there are two paths; both end with the same three env values.

## Step 0 — Prerequisites

```bash
node --version          # must be >= 24 (eve requires Node 24)
npm i -g vercel@latest
vercel login
git clone https://github.com/rustingibbsfight/weekly-rx-form-signature-agent.git
cd weekly-rx-form-signature-agent
npm install
```

## Step 1 — Create the Vercel project and deploy

```bash
vercel link        # create a new project when prompted (e.g. "weekly-rx-forms")
VERCEL_USE_EXPERIMENTAL_FRAMEWORKS=1 vercel deploy --prod
```

The flag lets the Vercel CLI recognize eve as a framework. The first deploy works but the agent isn't wired to anything yet — that's expected.

Confirm the cron registered: **Vercel dashboard → project → Settings → Cron Jobs** should show `0 23 * * 6` for `weekly-rx-forms`.

## Step 2 — Slack via Vercel Connect

Connect provisions and installs the Slack app, holds the bot token, and verifies inbound webhooks — you never touch api.slack.com. From the project directory:

```bash
vercel connect create slack --triggers
```

This walks you through installing the app into the Slack workspace and prints a client UID like `slack/weekly-rx-forms`. **Copy that UID.** Then re-point its trigger at eve's Slack route (Connect's default path isn't the one eve serves):

```bash
vercel connect detach <uid> --yes
vercel connect attach <uid> --triggers --trigger-path /eve/v1/slack --yes
```

In Slack:

1. Invite the bot to the ops channel: `/invite @<botname>`.
2. Grab the **channel ID**: right-click the channel → *View channel details* → About tab, bottom (starts with `C`).

If the UID isn't exactly `slack/rx-forms-agent`, set `SLACK_CONNECT_UID` in Step 4.

## Step 3 — Google Drive credentials (as rustin@fightweightgain.com)

Both paths produce `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REFRESH_TOKEN` — all the agent needs (`lib/drive.ts`).

### Path A — your own OAuth client (most durable)

Signed in as rustin@fightweightgain.com, check [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials) for an existing "OAuth 2.0 Client ID" you can reuse, or create one (type **Web application**).

1. Add `http://localhost:53682` to its **Authorized redirect URIs**.
2. Enable the **Google Drive API** in that project (APIs & Services → Library).
3. On the OAuth consent screen, set **User type: Internal** — only fightweightgain.com accounts can consent, there's no test-user list, and tokens don't expire under unverified-app rules.
4. Mint the token locally, in a browser signed in as **rustin@fightweightgain.com**:
   ```bash
   GOOGLE_CLIENT_ID=<id> GOOGLE_CLIENT_SECRET=<secret> node scripts/get-google-refresh-token.mjs
   ```
   It prints `GOOGLE_REFRESH_TOKEN`.

### Path B — gcloud CLI, no console clicking

If gcloud is already installed, mint Drive-scoped user credentials with Google's own OAuth client:

```bash
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/cloud-platform
```

Sign in as rustin@fightweightgain.com when the browser opens, then read the values out of the file it writes:

```bash
cat ~/.config/gcloud/application_default_credentials.json
```

Map `client_id` → `GOOGLE_CLIENT_ID`, `client_secret` → `GOOGLE_CLIENT_SECRET`, `refresh_token` → `GOOGLE_REFRESH_TOKEN`.

Caveats: this rides Google's shared gcloud OAuth client — fine for one scheduled run a week, but switch to Path A if you ever see quota errors, and note a Workspace admin re-authorization sweep can revoke gcloud tokens. Path A under an Internal client is the more durable long-term choice.

### Folder ID

Open the parent **Rx forms** folder (the one containing the weekly dated subfolders) in Drive as rustin@fightweightgain.com and copy the ID from the URL: `https://drive.google.com/drive/folders/<THIS_PART>`. My Drive and Shared Drives both work — the client passes `supportsAllDrives`.

## Step 4 — Set env vars and redeploy

Dashboard → project → Settings → Environment Variables (Production), or via CLI:

```bash
vercel env add GOOGLE_CLIENT_ID production
vercel env add GOOGLE_CLIENT_SECRET production
vercel env add GOOGLE_REFRESH_TOKEN production
vercel env add RX_PARENT_FOLDER_ID production
vercel env add SLACK_CHANNEL_ID production
vercel env add SLACK_CONNECT_UID production      # the UID from step 2
VERCEL_USE_EXPERIMENTAL_FRAMEWORKS=1 vercel deploy --prod
```

## Step 5 — First-run verification

1. In the ops channel, mention the bot: **"@bot run the weekly rx forms."**
2. Expected on an empty week: it checks Drive and replies asking you to download this week's consult forms — that's the "ask" path working.
3. Real dry run: create a subfolder named for this week (e.g. `7/18` or `Week of July 18`) under the parent folder, drop one consult PDF in it, and mention the bot again. Expect a `Patient_Intake_Prescription_Form_<First>_<Last>.pdf` uploaded next to it and a Slack summary with the link.
4. Watch the run live under **Observability → Agent Runs** (every turn and tool call is visible — useful if anything stalls).
5. The Saturday cron needs nothing further; execution history shows under **Observability → Cron Jobs**.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Bot doesn't respond to mentions | Re-run the `detach`/`attach --trigger-path /eve/v1/slack` pair from Step 2; confirm `SLACK_CONNECT_UID` matches the UID exactly. |
| "Google Drive is not configured" in the run | One of the three `GOOGLE_*` vars is missing in Production; redeploy after adding. |
| `invalid_grant` on token refresh | Refresh token revoked or minted as the wrong account; re-run Step 3 signed in as rustin@fightweightgain.com. |
| Folder found but "no forms" | The weekly folder name needs a recognizable date; the matcher is loose but won't guess undated names. |
| `SandboxTemplateNotProvisionedError` on every bash call | Should no longer happen: the sandbox installs its Python deps per session instead of baking a template, so there is no template to lose. If it reappears, something reintroduced a `bootstrap()` hook or `agent/sandbox/workspace/**` seed files in `agent/sandbox/sandbox.ts` — which recreates the template, and Vercel reaps that template after a couple of weeks. A redeploy rebuilds it; removing the bootstrap fixes it for good. |
| Cron fired at the wrong hour | Vercel cron is UTC-only: `0 23 * * 6` = 4 pm PDT / 3 pm PST. Use `0 0 * * 0` for 4 pm PST in winter (edit `agent/schedules/weekly-rx-forms.ts`). |
