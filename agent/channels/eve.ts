import { eveChannel } from "eve/channels/eve";
import { httpBasic, localDev, placeholderAuth, vercelOidc } from "eve/channels/auth";

// Optional HTTP Basic credential for on-demand runs over plain HTTP (curl,
// an internal script). Both variables must be set on the Vercel project for
// the route to open; with either missing the walk falls through to
// placeholderAuth() and production stays closed. Consult forms contain PHI,
// so this route is never made anonymous — do not swap in none().
const httpAuthUser = process.env.EVE_HTTP_AUTH_USER?.trim();
const httpAuthPassword = process.env.EVE_HTTP_AUTH_PASSWORD?.trim();
const httpAuthConfigured = Boolean(httpAuthUser && httpAuthPassword);

export default eveChannel({
  auth: [
    // Lets the eve TUI and your Vercel deployments reach the deployed agent.
    vercelOidc(),
    // Open on localhost for `eve dev` and the REPL; ignored in production.
    localDev(),
    // Password-protected entry point, only when both env vars are present.
    ...(httpAuthConfigured
      ? [
          httpBasic(
            { username: httpAuthUser!, password: httpAuthPassword! },
            { realm: "weekly-rx-forms" },
          ),
        ]
      : []),
    // Fails closed with a 401 when nothing above matched.
    placeholderAuth(),
  ],
});
