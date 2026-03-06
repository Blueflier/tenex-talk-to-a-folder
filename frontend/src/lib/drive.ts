const DRIVE_URL_REGEX =
  /drive\.google\.com\/(drive\/folders\/|file\/d\/|open\?id=)([-\w]+)/;

export function isValidDriveUrl(url: string): boolean {
  return DRIVE_URL_REGEX.test(url);
}

export function extractDriveId(url: string): string | null {
  const match = url.match(DRIVE_URL_REGEX);
  return match ? match[2] : null;
}

/**
 * Resolve a Drive URL to an array of file IDs.
 * For folders, lists children. For single files, returns [fileId].
 * Returns empty array on any error (graceful degradation).
 */
export async function resolveDriveFileIds(
  driveUrl: string,
  accessToken: string
): Promise<string[]> {
  try {
    const driveId = extractDriveId(driveUrl);
    if (!driveId) return [];

    const headers = { Authorization: `Bearer ${accessToken}` };

    // Check if folder or file
    const metaRes = await fetch(
      `https://www.googleapis.com/drive/v3/files/${driveId}?fields=id,mimeType`,
      { headers }
    );
    if (!metaRes.ok) return [];

    const meta = (await metaRes.json()) as { id: string; mimeType: string };

    if (meta.mimeType === "application/vnd.google-apps.folder") {
      // List children
      const listRes = await fetch(
        `https://www.googleapis.com/drive/v3/files?q='${driveId}'+in+parents&fields=files(id)&pageSize=1000`,
        { headers }
      );
      if (!listRes.ok) return [];
      const data = (await listRes.json()) as { files: { id: string }[] };
      return data.files.map((f) => f.id);
    }

    return [meta.id];
  } catch {
    return [];
  }
}
