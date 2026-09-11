/** Shrink an image in the browser before uploading it.
 *
 *  Phone photos arrive around 3200x5700 and the server resizes to 2200 anyway,
 *  so sending the original wastes several megabytes of upload on a connection
 *  that may be a phone's. Kept slightly above the server's working size so the
 *  server still controls the final resolution.
 *
 *  HEIC is passed through untouched: browsers cannot decode it, so it has to be
 *  uploaded as-is and converted server side.
 */

const MAX_EDGE = 2600;
const QUALITY = 0.9;
const UNREADABLE = /\.(heic|heif)$/i;

export async function downscale(file: File): Promise<File> {
  if (UNREADABLE.test(file.name) || !file.type.startsWith("image/")) return file;

  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    return file;   // undecodable here; let the server try
  }

  const longest = Math.max(bitmap.width, bitmap.height);
  if (longest <= MAX_EDGE) {
    bitmap.close();
    return file;
  }

  const scale = MAX_EDGE / longest;
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);

  const context = canvas.getContext("2d");
  if (!context) {
    bitmap.close();
    return file;
  }
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", QUALITY),
  );
  if (!blob || blob.size >= file.size) return file;

  return new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", {
    type: "image/jpeg",
    lastModified: file.lastModified,
  });
}
