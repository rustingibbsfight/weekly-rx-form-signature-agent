import { defineSandbox } from "eve/sandbox";

// The rx-intake-form skill scripts need reportlab (PDF generation with
// AcroForm fields), pypdf (post-processing), and PyMuPDF (text extraction).
// Installing them at template build time means every session starts ready.
//
// Versions are pinned: the template is only rebuilt when this file changes,
// so an unpinned install silently picks up new majors on the next rebuild.
// That matters most for PyMuPDF, whose legacy `fitz` import is deprecated.
const PYTHON_DEPS = "reportlab==5.0.1 pypdf==6.17.0 PyMuPDF==1.28.2";

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
