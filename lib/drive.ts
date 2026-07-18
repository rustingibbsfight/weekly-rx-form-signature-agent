/**
 * Minimal Google Drive v3 client using an OAuth refresh token.
 *
 * Auth model: a one-time OAuth consent is performed as the fightweightgain
 * Google account (see scripts/get-google-refresh-token.mjs). The resulting
 * refresh token is stored in env and exchanged for short-lived access tokens
 * here. No SDK dependency — plain fetch against the Drive REST API.
 */

const TOKEN_URL = "https://oauth2.googleapis.com/token";
const API = "https://www.googleapis.com/drive/v3";
const UPLOAD_API = "https://www.googleapis.com/upload/drive/v3";

const FILE_FIELDS =
  "id,name,mimeType,size,createdTime,modifiedTime,webViewLink,parents";

export interface DriveFile {
  id: string;
  name: string;
  mimeType: string;
  size?: string;
  createdTime?: string;
  modifiedTime?: string;
  webViewLink?: string;
  parents?: string[];
}

let cachedToken: { token: string; expiresAt: number } | null = null;

export async function getAccessToken(): Promise<string> {
  const clientId = process.env.GOOGLE_CLIENT_ID;
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET;
  const refreshToken = process.env.GOOGLE_REFRESH_TOKEN;
  if (!clientId || !clientSecret || !refreshToken) {
    throw new Error(
      "Google Drive is not configured: set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN.",
    );
  }
  if (cachedToken && cachedToken.expiresAt > Date.now() + 60_000) {
    return cachedToken.token;
  }
  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      client_id: clientId,
      client_secret: clientSecret,
      refresh_token: refreshToken,
    }),
  });
  if (!res.ok) {
    throw new Error(
      `Google token refresh failed (${res.status}): ${await res.text()}`,
    );
  }
  const data = (await res.json()) as { access_token: string; expires_in: number };
  cachedToken = {
    token: data.access_token,
    expiresAt: Date.now() + data.expires_in * 1000,
  };
  return cachedToken.token;
}

async function driveFetch(url: string, init?: RequestInit): Promise<Response> {
  const token = await getAccessToken();
  const res = await fetch(url, {
    ...init,
    headers: { ...init?.headers, authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`Drive API error (${res.status}): ${await res.text()}`);
  }
  return res;
}

/** Run a Drive files.list query, following pagination. */
export async function listFiles(q: string): Promise<DriveFile[]> {
  const files: DriveFile[] = [];
  let pageToken: string | undefined;
  do {
    const params = new URLSearchParams({
      q,
      fields: `nextPageToken,files(${FILE_FIELDS})`,
      pageSize: "100",
      supportsAllDrives: "true",
      includeItemsFromAllDrives: "true",
      orderBy: "createdTime desc",
    });
    if (pageToken) params.set("pageToken", pageToken);
    const res = await driveFetch(`${API}/files?${params}`);
    const data = (await res.json()) as {
      files: DriveFile[];
      nextPageToken?: string;
    };
    files.push(...data.files);
    pageToken = data.nextPageToken;
  } while (pageToken);
  return files;
}

export async function getFileMetadata(fileId: string): Promise<DriveFile> {
  const params = new URLSearchParams({
    fields: FILE_FIELDS,
    supportsAllDrives: "true",
  });
  const res = await driveFetch(
    `${API}/files/${encodeURIComponent(fileId)}?${params}`,
  );
  return (await res.json()) as DriveFile;
}

/** Download a file's binary content. */
export async function downloadFile(fileId: string): Promise<Uint8Array> {
  const params = new URLSearchParams({ alt: "media", supportsAllDrives: "true" });
  const res = await driveFetch(
    `${API}/files/${encodeURIComponent(fileId)}?${params}`,
  );
  return new Uint8Array(await res.arrayBuffer());
}

/** Upload binary content as a new file in a folder (multipart upload). */
export async function uploadFile(options: {
  name: string;
  parentId: string;
  content: Uint8Array;
  mimeType?: string;
}): Promise<DriveFile> {
  const { name, parentId, content, mimeType = "application/pdf" } = options;
  const boundary = `eve-rx-${Math.random().toString(36).slice(2)}`;
  const metadata = JSON.stringify({ name, parents: [parentId] });
  const encoder = new TextEncoder();
  const head = encoder.encode(
    `--${boundary}\r\ncontent-type: application/json; charset=UTF-8\r\n\r\n${metadata}\r\n--${boundary}\r\ncontent-type: ${mimeType}\r\n\r\n`,
  );
  const tail = encoder.encode(`\r\n--${boundary}--\r\n`);
  const body = new Uint8Array(head.length + content.length + tail.length);
  body.set(head, 0);
  body.set(content, head.length);
  body.set(tail, head.length + content.length);

  const params = new URLSearchParams({
    uploadType: "multipart",
    supportsAllDrives: "true",
    fields: FILE_FIELDS,
  });
  const res = await driveFetch(`${UPLOAD_API}/files?${params}`, {
    method: "POST",
    headers: { "content-type": `multipart/related; boundary=${boundary}` },
    body,
  });
  return (await res.json()) as DriveFile;
}
