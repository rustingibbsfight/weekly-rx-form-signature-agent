import { defineTool } from "eve/tools";
import { z } from "zod";

import { listFiles } from "../../lib/drive";

export default defineTool({
  description:
    "List subfolders of a Google Drive folder in the fightweightgain Drive. Defaults to the configured Rx forms parent folder (RX_PARENT_FOLDER_ID). Use this to find the current week's dated subfolder.",
  inputSchema: z.object({
    parentFolderId: z
      .string()
      .optional()
      .describe("Drive folder id to list. Omit to use RX_PARENT_FOLDER_ID."),
  }),
  async execute({ parentFolderId }) {
    const parent = parentFolderId ?? process.env.RX_PARENT_FOLDER_ID;
    if (!parent) {
      throw new Error(
        "No folder id given and RX_PARENT_FOLDER_ID is not set. Ask the user to configure the Rx forms parent folder id.",
      );
    }
    const folders = await listFiles(
      `'${parent.replace(/'/g, "\\'")}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false`,
    );
    return {
      parentFolderId: parent,
      folders: folders.map((f) => ({
        id: f.id,
        name: f.name,
        createdTime: f.createdTime,
        modifiedTime: f.modifiedTime,
        webViewLink: f.webViewLink,
      })),
    };
  },
});
