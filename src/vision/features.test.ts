import { describe, expect, it } from 'vitest';
import { featureFromImageData } from './features';

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

// Target features are scored by the Python backend; these tests pin the
// vector layout it expects from the browser.
describe('map reference features', () => {
  it('emits one value per pixel and a normalized colour histogram', () => {
    const feature = featureFromImageData(
      imageDataFrom(40, 40, (x) => (x < 20 ? [45, 146, 88] : [65, 130, 185])),
    );
    expect(feature.luminance).toHaveLength(1600);
    expect(feature.chroma).toHaveLength(1600);
    expect(feature.edges).toHaveLength(1600);
    expect(feature.colorHistogram).toHaveLength(12);
    const total = feature.colorHistogram.reduce((sum, value) => sum + value, 0);
    expect(total).toBeCloseTo(1, 8);
  });

  it('marks edges only where land meets water', () => {
    const feature = featureFromImageData(
      imageDataFrom(40, 40, (x) => (x < 20 ? [42, 150, 82] : [64, 128, 184])),
    );
    const at = (x: number, y: number) => feature.edges[y * 40 + x];
    expect(at(5, 10)).toBeCloseTo(0, 8);
    expect(at(30, 10)).toBeCloseTo(0, 8);
    expect(at(19, 10)).toBeGreaterThan(0.01);
    expect(at(20, 10)).toBeGreaterThan(0.01);
  });
});
