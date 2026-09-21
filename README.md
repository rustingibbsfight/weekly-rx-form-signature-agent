# Weekly Rx Form Signature Agent

A [Vercel eve](https://eve.dev) agent for Breakthrough Medical Weight Loss that turns each week's downloaded consult forms into fillable, Adobe Sign–ready **Patient Intake & Prescription Order** PDFs and saves them back to Google Drive.

**What it does, every Saturday at 4 pm Pacific (or on demand):**

1. Looks in the fightweightgain Google Drive Rx forms folder for **this week's dated subfolder**.
2. If the week's consult forms aren't there yet → posts in Slack asking you to download them into Drive.
3. If they are → runs the bundled **rx-intake-form** skill: extracts patient data from each consult PDF and generates a 2-page fillable AcroForm PDF with Adobe Sign signer tags (signer1 = Clinic Director, signer2 = Physician).
4. Uploads each `Patient_Intake_Prescription_Form_<First>_<Last>.pdf` back to the same weekly folder and posts a Slack summary with links.

Re-runs are safe: sources that already have a generated form are skipped.

## Project layout

```
agent/
  agent.ts                    # model config (anthropic/claude-sonnet-5 via AI Gateway)
  instructions.md             # the weekly workflow the agent follows
  tools/                      # typed tools: Drive list/download/upload + current-week helper
  skills/rx-intake-form/      # the intake-form skill (SKILL.md + Python scripts + logo)
  channels/slack.ts           # Slack channel (Vercel Connect credentials)
  channels/eve.ts             # HTTP/dev-REPL channel
  schedules/weekly-rx-forms.ts# Saturday cron → runs the workflow into Slack
  sandbox/sandbox.ts          # per-session setup: pip install pinned reportlab, pypdf, PyMuPDF
lib/drive.ts                  # Google Drive REST client (OAuth refresh token)
scripts/get-google-refresh-token.mjs  # one-time OAuth token mint helper
```

## Setup

**Full walkthrough: [docs/GO-LIVE.md](docs/GO-LIVE.md)** — includes a no-console gcloud path for the Google credentials and a troubleshooting table. The short version follows.

Requires Node 24+ and the Vercel CLI (`npm i -g vercel`).

### 1. Deploy the project

```bash
npm install
vercel link                                # create/link the Vercel project
VERCEL_USE_EXPERIMENTAL_FRAMEWORKS=1 vercel deploy --prod
```

### 2. Google Drive access (rustin@fightweightgain.com)

1. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials) (any project), enable the **Google Drive API** and create or reuse an **OAuth client ID** of type **Web application** with `http://localhost:53682` added to *Authorized redirect URIs*. On a Workspace account, set the consent screen to **Internal** (no test users, no verification).
2. Mint the refresh token locally, signed in to the browser as **rustin@fightweightgain.com**:
   ```bash
   GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... node scripts/get-google-refresh-token.mjs
   ```
   *Alternative:* if gcloud is installed, skip the console entirely — see Path B in [docs/GO-LIVE.md](docs/GO-LIVE.md).
3. In Drive, note the id of the parent **Rx forms** folder (the one that contains the weekly dated subfolders) from its URL: `https://drive.google.com/drive/folders/<RX_PARENT_FOLDER_ID>`.

### 3. Slack

The Slack channel uses [Vercel Connect](https://vercel.com/docs/connect) — no bot token to manage:

```bash
vercel connect create slack --triggers          # creates the Slack app; note the UID (e.g. slack/rx-forms-agent)
vercel connect detach <uid> --yes
vercel connect attach <uid> --triggers --trigger-path /eve/v1/slack --yes
```

Invite the bot to your ops channel, then grab the channel id (channel → *View channel details* → About tab, bottom).

### 4. Environment variables

Set these on the Vercel project (Settings → Environment Variables), then redeploy. See `.env.example` for the full list:

| Variable | Value |
|---|---|
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | the OAuth client from step 2 |
| `GOOGLE_REFRESH_TOKEN` | printed by the mint script |
| `RX_PARENT_FOLDER_ID` | parent Rx forms folder id |
| `SLACK_CHANNEL_ID` | ops channel id for scheduled runs |
| `SLACK_CONNECT_UID` | Connect UID if different from `slack/rx-forms-agent` |
| `EVE_HTTP_AUTH_USER` / `EVE_HTTP_AUTH_PASSWORD` | *(optional)* both set opens the HTTP route behind Basic auth; unset keeps it closed |

### 5. Verify

- **Cron registered:** Vercel dashboard → Settings → Cron Jobs should show `0 23 * * 6`.
- **First run:** @mention the bot in the ops channel: *"run the weekly rx forms"*. It should find (or ask for) this week's folder.

## Running it

| How | What to do |
|---|---|
| **Scheduled** | Nothing — fires Saturdays 23:00 UTC (= 4 pm PDT; 3 pm during PST — Vercel cron is UTC-only; switch the cron in `agent/schedules/weekly-rx-forms.ts` to `0 0 * * 0` if winter wall-clock matters). |
| **On demand (Slack)** | @mention or DM the bot: "run the weekly rx forms". |
| **On demand (HTTP)** | Off unless `EVE_HTTP_AUTH_USER` and `EVE_HTTP_AUTH_PASSWORD` are set on the project (without them the route returns `eve_production_auth_not_configured`). With both set: `curl -X POST https://<deployment>/eve/v1/session -u "$EVE_HTTP_AUTH_USER:$EVE_HTTP_AUTH_PASSWORD" -H 'content-type: application/json' -d '{"message":"Process this week's Rx forms."}'` |
| **Local dev** | `cp .env.example .env`, fill it in, `npm run dev` (interactive REPL). Schedules don't fire in dev; trigger once with `curl -X POST http://localhost:3000/eve/v1/dev/schedules/weekly-rx-forms`. |

## Drive folder convention

The agent expects, under `RX_PARENT_FOLDER_ID`, one subfolder per week named with a date (it matches loosely: `7/18`, `07-18-2026`, `Week of July 18`, …, falling back to the newest folder created in the last 7 days). Drop the week's consult PDFs in that folder; generated forms are uploaded alongside them.

## PHI note

Consult forms contain patient health information. Runs, tool inputs/outputs, and token usage are captured by Vercel Agent Runs observability, patient names appear in Slack summaries, and model calls flow through Vercel AI Gateway. The agent is instructed to keep medical details out of Slack, but confirm this data path is acceptable under your BAA/compliance posture, and consider locking the sandbox network policy down (see `agent/sandbox/sandbox.ts`) if required.
