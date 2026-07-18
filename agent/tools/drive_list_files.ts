import { defineTool } from "eve/tools";
import { z } from "zod";

import { listFiles } from "../../lib/drive";

export default defineTool({
  description:
    "List the files inside a Google Drive folder (fightweightgain Drive): names, ids, types, sizes, and timestamps. Use this to find source consult PDFs and to check which generated intake forms already exist.",
  inputSchema: z.object({
    folderId: z.string().min(1).describe("Drive folder id to list files in."),
  }),
  async execute({ folderId }) {
    const files = await listFiles(
      `'${folderId.replace(/'/g, "\\'")}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false`,
    );
    return {
      folderId,
      files: files.map((f) => ({
        id: f.id,
        name: f.name,
        mimeType: f.mimeType,
        sizeBytes: f.size ? Number(f.size) : undefined,
        createdTime: f.createdTime,
        modifiedTime: f.modifiedTime,
        webViewLink: f.webViewLink,
      })),
    };
  },
});
