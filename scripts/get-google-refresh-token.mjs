#!/usr/bin/env node
/**
 * One-time helper: mint a Google OAuth refresh token for the agent.
 *
 * Run this locally, signed in to the browser as the fightweightgain Google
 * account (the one that owns the Rx forms Drive folder):
 *
 *   GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... node scripts/get-google-refresh-token.mjs
 *
 * Prerequisite: a Google Cloud OAuth client of type "Web application" with
 * http://localhost:53682 in its Authorized redirect URIs (see README).
 * The script opens a consent URL, catches the redirect on localhost:53682,
 * exchanges the code, and prints the refresh token to paste into Vercel env.
 */

import http from "node:http";

const clientId = process.env.GOOGLE_CLIENT_ID;
const clientSecret = process.env.GOOGLE_CLIENT_SECRET;
if (!clientId || !clientSecret) {
  console.error("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET env vars first.");
  process.exit(1);
}

const PORT = 53682;
const REDIRECT_URI = `http://localhost:${PORT}`;
const SCOPE = "https://www.googleapis.com/auth/drive";

const authUrl =
  "https://accounts.google.com/o/oauth2/v2/auth?" +
  new URLSearchParams({
    client_id: clientId,
    redirect_uri: REDIRECT_URI,
    response_type: "code",
    scope: SCOPE,
    access_type: "offline",
    prompt: "consent", // force a refresh token even if previously consented
  });

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, REDIRECT_URI);
  const code = url.searchParams.get("code");
  const error = url.searchParams.get("error");
  if (!code && !error) {
    res.writeHead(404).end();
    return;
  }
  if (error) {
    res.writeHead(200, { "content-type": "text/plain" }).end(`OAuth error: ${error}`);
    console.error(`OAuth error: ${error}`);
    server.close();
    process.exit(1);
  }
  const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code,
      client_id: clientId,
      client_secret: clientSecret,
      redirect_uri: REDIRECT_URI,
      grant_type: "authorization_code",
    }),
  });
  const data = await tokenRes.json();
  if (!tokenRes.ok || !data.refresh_token) {
    res.writeHead(200, { "content-type": "text/plain" }).end("Token exchange failed — see terminal.");
    console.error("Token exchange failed:", JSON.stringify(data, null, 2));
    server.close();
    process.exit(1);
  }
  res
    .writeHead(200, { "content-type": "text/plain" })
    .end("Success! Refresh token printed in your terminal. You can close this tab.");
  console.log("\nGOOGLE_REFRESH_TOKEN:\n");
  console.log(data.refresh_token);
  console.log("\nAdd it (plus GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET) to your Vercel project env vars.");
  server.close();
  process.exit(0);
});

server.listen(PORT, () => {
  console.log("Open this URL in a browser signed in as the fightweightgain account:\n");
  console.log(authUrl + "\n");
  console.log(`Waiting for the OAuth redirect on ${REDIRECT_URI} ...`);
});
