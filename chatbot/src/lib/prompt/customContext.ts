export function buildCustomContext(content?: string): string {
    return content ? `Additional context:\n${content.trim()}` : '';
  }