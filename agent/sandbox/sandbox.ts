import { defineSandbox } from "eve/sandbox";

// The rx-intake-form skill scripts need reportlab (PDF generation with
// AcroForm fields), pypdf (post-processing), and PyMuPDF (text extraction).
//
// These install per session rather than in a `bootstrap()` hook, and that
// choice is deliberate — see the note below before moving them back.
//
// Versions are pinned so a rebuild months from now installs what was tested.
// PyMuPDF especially: the skill's extract script wants the modern `pymupdf`
// import, and an unpinned major could change that out from under it.
const PYTHON_DEPS = "reportlab==5.0.1 pypdf==6.17.0 PyMuPDF==1.28.2";

// The base image ships a PEP 668 "externally managed" Python, so the plain
// install always fails there; lead with the flag that works and keep the
// others as fallbacks for images that lack it.
const INSTALL_COMMAND =
  `python3 -m pip install --quiet --break-system-packages ${PYTHON_DEPS} ` +
  `|| python3 -m pip install --quiet ${PYTHON_DEPS} ` +
  `|| pip3 install --quiet ${PYTHON_DEPS}`;

// NOTE — why this is `onSession` and not `bootstrap`.
//
// A `bootstrap()` hook makes eve build a reusable sandbox *template*, and on
// the Vercel backend that template is a sandbox created with
// `persistent: false`. Vercel reaps non-persistent sandboxes, so the template
// disappears on its own after a couple of weeks while its snapshot lingers as
// an orphan. The runtime looks the template up by *name*, so once it is reaped
// every run fails with SandboxTemplateNotProvisionedError until someone
// redeploys. The runtime cannot repair this: eve's rebuild path
// (`ensureTemplateWithUnavailableRetry`) is reachable only from build-time
// prewarm, never from session create. This agent runs once a week unattended,
// so that failure surfaces as a silently skipped week of patient forms.
//
// With no `bootstrap()` and no `agent/sandbox/workspace/**` seed files, the
// template plan is "none" and the template key is null, so session create
// skips the template lookup entirely and boots from the base image. That
// removes the whole failure class. The cost is a few seconds of pip on each
// new session — a good trade for a weekly unattended job.
//
// Reintroducing `bootstrap()` or seed files opts back into the template, and
// into redeploying whenever Vercel reaps it.
export default defineSandbox({
  async onSession({ use }) {
    const sandbox = await use();
    const result = await sandbox.run({ command: INSTALL_COMMAND });
    if (result.stderr) {
      console.warn("rx sandbox pip output:", result.stderr.slice(0, 2000));
    }
    if (result.exitCode !== 0) {
      // Don't throw: the skill documents a manual pip fallback, so a session
      // that starts with a loud warning beats one that refuses to start.
      console.error(
        `rx sandbox: python dependency install failed (exit ${result.exitCode}). ` +
          "The rx-intake-form skill will need to install them itself.",
      );
    }
  },
});
