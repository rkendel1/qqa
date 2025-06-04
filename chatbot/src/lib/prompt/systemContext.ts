export function buildSystemContext(system?: string): string {
    return `System: ${
      system?.trim() ||
      'You are a helpful assistant trained to answer municipal questions like permits, zoning, and city services.'
    }`;
  }