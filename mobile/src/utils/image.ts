import * as ImageManipulator from "expo-image-manipulator";

export interface NormalizedReceiptImage {
  uri: string;
  width: number;
  height: number;
  mimeType: "image/jpeg";
  fileName: string;
}

/**
 * Normalizes mobile camera / library photos (including iOS HEIC & EXIF orientation)
 * into a <=2048px JPEG suitable for multipart upload to POST /api/v1/ocr/scan.
 */
export async function normalizeReceiptImage(
  sourceUri: string
): Promise<NormalizedReceiptImage> {
  const result = await ImageManipulator.manipulateAsync(
    sourceUri,
    [{ resize: { width: 1600 } }],
    {
      compress: 0.82,
      format: ImageManipulator.SaveFormat.JPEG,
    }
  );

  return {
    uri: result.uri,
    width: result.width,
    height: result.height,
    mimeType: "image/jpeg",
    fileName: `receipt-${Date.now()}.jpg`,
  };
}

