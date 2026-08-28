import type {
  FeatureVector,
  NormalizedRegion,
  TargetReference,
} from '../domain/types';

const FEATURE_SIZE = 40;

function sourceDimensions(source: CanvasImageSource): { width: number; height: number } {
  if (source instanceof HTMLVideoElement) {
    return { width: source.videoWidth, height: source.videoHeight };
  }
  if (source instanceof HTMLImageElement) {
    return { width: source.naturalWidth, height: source.naturalHeight };
  }
  if (source instanceof HTMLCanvasElement) {
    return { width: source.width, height: source.height };
  }
  if (typeof ImageBitmap !== 'undefined' && source instanceof ImageBitmap) {
    return { width: source.width, height: source.height };
  }
  throw new Error('不支持的图像来源');
}

function cropPixels(
  source: CanvasImageSource,
  region?: NormalizedRegion,
  outputWidth = FEATURE_SIZE,
  outputHeight = FEATURE_SIZE,
): ImageData {
  const { width, height } = sourceDimensions(source);
  if (width === 0 || height === 0) throw new Error('视频画面尚未就绪');

  const normalized = region ?? { x: 0, y: 0, width: 1, height: 1 };
  const canvas = document.createElement('canvas');
  canvas.width = outputWidth;
  canvas.height = outputHeight;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) throw new Error('无法创建图像分析画布');
  context.drawImage(
    source,
    normalized.x * width,
    normalized.y * height,
    normalized.width * width,
    normalized.height * height,
    0,
    0,
    outputWidth,
    outputHeight,
  );
  return context.getImageData(0, 0, outputWidth, outputHeight);
}

export function featureFromImageData(image: ImageData): FeatureVector {
  const { data, width, height } = image;
  const luminance = new Array<number>(width * height);
  const chroma = new Array<number>(width * height);
  const colorHistogram = new Array<number>(12).fill(0);

  for (let i = 0; i < width * height; i += 1) {
    const offset = i * 4;
    const r = data[offset] / 255;
    const g = data[offset + 1] / 255;
    const b = data[offset + 2] / 255;
    luminance[i] = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    chroma[i] = (g - b + 1) / 2;
    colorHistogram[Math.min(3, Math.floor(r * 4))] += 1;
    colorHistogram[4 + Math.min(3, Math.floor(g * 4))] += 1;
    colorHistogram[8 + Math.min(3, Math.floor(b * 4))] += 1;
  }

  const pixelCount = width * height;
  for (let i = 0; i < colorHistogram.length; i += 1) {
    colorHistogram[i] /= pixelCount * 3;
  }

  const edges = new Array<number>(pixelCount).fill(0);
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const index = y * width + x;
      const gx =
        -luminance[index - width - 1] +
        luminance[index - width + 1] -
        2 * luminance[index - 1] +
        2 * luminance[index + 1] -
        luminance[index + width - 1] +
        luminance[index + width + 1];
      const gy =
        -luminance[index - width - 1] -
        2 * luminance[index - width] -
        luminance[index - width + 1] +
        luminance[index + width - 1] +
        2 * luminance[index + width] +
        luminance[index + width + 1];
      edges[index] = Math.min(1, Math.hypot(gx, gy));
    }
  }

  return { luminance, chroma, edges, colorHistogram };
}

export function extractFeature(
  source: CanvasImageSource,
  region?: NormalizedRegion,
): FeatureVector {
  return featureFromImageData(cropPixels(source, region));
}

function zeroMeanCosine(left: number[], right: number[]): number {
  if (left.length !== right.length || left.length === 0) return 0;
  const meanLeft = left.reduce((sum, value) => sum + value, 0) / left.length;
  const meanRight = right.reduce((sum, value) => sum + value, 0) / right.length;
  let dot = 0;
  let normLeft = 0;
  let normRight = 0;
  for (let i = 0; i < left.length; i += 1) {
    const a = left[i] - meanLeft;
    const b = right[i] - meanRight;
    dot += a * b;
    normLeft += a * a;
    normRight += b * b;
  }
  if (normLeft < 1e-8 || normRight < 1e-8) {
    return Math.abs(meanLeft - meanRight) < 0.02 ? 1 : 0;
  }
  return Math.max(0, Math.min(1, (dot / Math.sqrt(normLeft * normRight) + 1) / 2));
}

function meanAbsoluteSimilarity(left: number[], right: number[]): number {
  if (left.length !== right.length || left.length === 0) return 0;
  let difference = 0;
  for (let i = 0; i < left.length; i += 1) difference += Math.abs(left[i] - right[i]);
  return Math.max(0, 1 - difference / left.length);
}

function histogramIntersection(left: number[], right: number[]): number {
  if (left.length !== right.length || left.length === 0) return 0;
  let overlap = 0;
  let total = 0;
  for (let i = 0; i < left.length; i += 1) {
    overlap += Math.min(left[i], right[i]);
    total += Math.max(left[i], right[i]);
  }
  return total === 0 ? 1 : overlap / total;
}

export function compareFeatures(left: FeatureVector, right: FeatureVector): number {
  const structure = zeroMeanCosine(left.luminance, right.luminance);
  const landWaterShape = zeroMeanCosine(left.chroma, right.chroma);
  const edgeShape = meanAbsoluteSimilarity(left.edges, right.edges);
  const color = histogramIntersection(left.colorHistogram, right.colorHistogram);
  return Math.max(
    0,
    Math.min(1, structure * 0.24 + landWaterShape * 0.38 + edgeShape * 0.28 + color * 0.1),
  );
}

export function capturePreview(
  source: CanvasImageSource,
  region?: NormalizedRegion,
  width = 320,
): string {
  const { width: sourceWidth, height: sourceHeight } = sourceDimensions(source);
  const normalized = region ?? { x: 0, y: 0, width: 1, height: 1 };
  const ratio = (normalized.height * sourceHeight) / (normalized.width * sourceWidth);
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = Math.max(1, Math.round(width * ratio));
  const context = canvas.getContext('2d');
  if (!context) throw new Error('无法创建预览图');
  context.drawImage(
    source,
    normalized.x * sourceWidth,
    normalized.y * sourceHeight,
    normalized.width * sourceWidth,
    normalized.height * sourceHeight,
    0,
    0,
    canvas.width,
    canvas.height,
  );
  return canvas.toDataURL('image/jpeg', 0.82);
}

export async function referenceFromFile(file: File): Promise<TargetReference> {
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    return {
      id: crypto.randomUUID(),
      name: file.name.replace(/\.[^.]+$/, ''),
      previewUrl: capturePreview(image),
      feature: extractFeature(image),
    };
  } finally {
    URL.revokeObjectURL(url);
  }
}
