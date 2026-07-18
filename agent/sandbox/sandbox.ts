import { defineSandbox } from "eve/sandbox";

// The rx-intake-form skill scripts need reportlab (PDF generation with
// AcroForm fields), pypdf (post-processing), and PyMuPDF (text extraction).
// Installing them at template build time means every session starts ready.
export default defineSandbox({
  revalidationKey: () => "rx-intake-python-deps-v1",
  async bootstrap({ use }) {
    const sandbox = await use();
    const result = await sandbox.run({
      command:
        "python3 -m pip install --quiet reportlab pypdf PyMuPDF " +
        "|| python3 -m pip install --quiet --break-system-packages reportlab pypdf PyMuPDF " +
        "|| pip3 install --quiet reportlab pypdf PyMuPDF",
    });
    if (result.stderr) {
      console.warn("rx sandbox bootstrap pip output:", result.stderr.slice(0, 2000));
    }
  },
});
