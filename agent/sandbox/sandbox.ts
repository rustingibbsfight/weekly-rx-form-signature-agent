import { defineSandbox } from "eve/sandbox";

// The rx-intake-form skill scripts need reportlab (PDF generation with
// AcroForm fields), pypdf (post-processing), and PyMuPDF (text extraction).
// Installing them at template build time means every session starts ready.
//
// Versions are pinned: the template is only rebuilt when this file changes,
// so an unpinned install silently picks up new majors on the next rebuild.
// That matters most for PyMuPDF, whose legacy `fitz` import is deprecated.
const PYTHON_DEPS = "reportlab==5.0.1 pypdf==6.17.0 PyMuPDF==1.28.2";

// NOTE — this agent always builds a sandbox template, and that template is
// perishable. Do not try to design the template away; it cannot be done here.
//
// eve builds a template when the sandbox has a bootstrap() hook OR any
// workspace resource content. Bundled skills count as workspace content:
// the compiler copies each skill into the node's resource root
// (`materializeNode` in eve's compiler/workspace-resources.js) and hashes the
// result, so `rx-intake-form` alone gives the root a contentHash and non-empty
// rootEntries. The template plan is then "workspace-content" and the template
// key is non-null whether or not this hook exists. Moving the pip install to
// onSession() was tried in d37f1c0 and reverted: it removed nothing, and only
// cost every session a pip run.
//
// The template is a Vercel sandbox created with `persistent: false`, so Vercel
// reaps it after roughly two weeks. The runtime resolves it by name and cannot
// rebuild it — eve's ensureTemplateWithUnavailableRetry is reachable only from
// build-time prewarm — so once reaped, every run fails with
// SandboxTemplateNotProvisionedError until someone redeploys. That is what
// took the agent down on 2026-09-06 and again on 2026-09-21.
//
// The mitigation is therefore operational, not structural: the scheduled
// redeploy in .github/workflows/refresh-sandbox-template.yml rebuilds the
// template weekly, ahead of the Saturday cron. If that workflow is removed or
// starts failing, this agent goes down within about two weeks.
export default defineSandbox({
  revalidationKey: () => "rx-intake-python-deps-v2",
  async bootstrap({ use }) {
    const sandbox = await use();
    // The base image ships a PEP 668 "externally managed" Python, so the
    // plain install always fails there; lead with the flag that works and
    // keep the others as fallbacks for images that lack it.
    const result = await sandbox.run({
      command:
        `python3 -m pip install --quiet --break-system-packages ${PYTHON_DEPS} ` +
        `|| python3 -m pip install --quiet ${PYTHON_DEPS} ` +
        `|| pip3 install --quiet ${PYTHON_DEPS}`,
    });
    if (result.stderr) {
      console.warn("rx sandbox bootstrap pip output:", result.stderr.slice(0, 2000));
    }
  },
});
