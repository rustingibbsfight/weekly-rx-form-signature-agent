import { defineTool } from "eve/tools";
import { z } from "zod";

import { uploadFile } from "../../lib/drive";

export default defineTool({
  description:
    "Upload a file from the sandbox filesystem to a folder in the fightweightgain Google Drive. Use this to save generated intake/prescription PDFs back to the week's Drive folder. Returns the new Drive file id and link.",
  inputSchema: z.object({
    sandboxPath: z
      .string()
      .min(1)
      .describe("Source path in the sandbox, relative to /workspace."),
    folderId: z.string().min(1).describe("Destination Drive folder id."),
    name: z
      .string()
      .min(1)
      .describe("File name to create in Drive (e.g. 'Patient_Intake_Prescription_Form_Jane_Doe.pdf')."),
    mimeType: z.string().optional().describe("MIME type; defaults to application/pdf."),
  }),
  async execute({ sandboxPath, folderId, name, mimeType }, ctx) {
    const sandbox = await ctx.getSandbox();
    const content = await sandbox.readBinaryFile({ path: sandboxPath });
    if (!content) {
      throw new Error(`No file found in the sandbox at '${sandboxPath}'.`);
    }
    const file = await uploadFile({ name, parentId: folderId, content, mimeType });
    return {
      id: file.id,
      name: file.name,
      webViewLink: file.webViewLink,
      sizeBytes: content.length,
    };
  },
});
