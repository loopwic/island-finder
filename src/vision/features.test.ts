import { describe, expect, it } from 'vitest';
import { compareFeatures, featureFromImageData } from './features';

function imageDataFrom(
  width: number,
  height: number,
  pixel: (x: number, y: number) => [number, number, number],
): ImageData {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const [r, g, b] = pixel(x, y);
      const offset = (y * width + x) * 4;
      data[offset] = r;
      data[offset + 1] = g;
      data[offset + 2] = b;
      data[offset + 3] = 255;
    }
  }
  return { data, width, height, colorSpace: 'srgb' } as ImageData;
}

describe('map feature comparison', () => {
  it('scores an identical layout as an exact match', () => {
    const map = imageDataFrom(40, 40, (x, y) =>
      x < 20 && y < 20 ? [45, 146, 88] : [65, 130, 185],
    );
    const feature = featureFromImageData(map);
    expect(compareFeatures(feature, feature)).toBeCloseTo(1, 8);
  });

  it('ranks a structurally similar map above a different layout', () => {
    const target = featureFromImageData(
      imageDataFrom(40, 40, (x, y) => (x < 20 ? [42, 150, 82] : [64, 128, 184])),
    );
    const similar = featureFromImageData(
      imageDataFrom(40, 40, (x, y) => (x < 21 ? [47, 145, 85] : [68, 133, 179])),
    );
    const different = featureFromImageData(
      imageDataFrom(40, 40, (_x, y) => (y < 20 ? [190, 110, 50] : [30, 38, 42])),
    );
    expect(compareFeatures(target, similar)).toBeGreaterThan(compareFeatures(target, different));
  });
});
