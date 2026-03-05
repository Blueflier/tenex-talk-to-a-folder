const DRIVE_URL_REGEX =
  /drive\.google\.com\/(drive\/folders\/|file\/d\/|open\?id=)([-\w]+)/;

export function isValidDriveUrl(url: string): boolean {
  return DRIVE_URL_REGEX.test(url);
}

export function extractDriveId(url: string): string | null {
  const match = url.match(DRIVE_URL_REGEX);
  return match ? match[2] : null;
}
