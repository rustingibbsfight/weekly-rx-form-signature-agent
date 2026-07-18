import { defineTool } from "eve/tools";
import { z } from "zod";

import { downloadFile, getFileMetadata } from "../../lib/drive";

export default defineTool({
  description:
    "Download a file from the fightweightgain Google Drive into the sandbox filesystem so scripts can process it. Returns the sandbox path it was written to.",
  inputSchema: z.object({
    fileId: z.string().min(1).describe("Drive file id to download."),
    sandboxPath: z
      .string()
      .min(1)
      .describe(
        "Destination path in the sandbox, relative to /workspace (e.g. 'incoming/consult.pdf').",
      ),
  }),
  async execute({ fileId, sandboxPath }, ctx) {
    const [meta, content] = await Promise.all([
      getFileMetadata(fileId),
      downloadFile(fileId),
    ]);
    const sandbox = await ctx.getSandbox();
    await sandbox.writeBinaryFile({ path: sandboxPath, content });
    return {
      sandboxPath,
      name: meta.name,
      mimeType: meta.mimeType,
      sizeBytes: content.length,
    };
  },
});
