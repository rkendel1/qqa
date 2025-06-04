export function buildUserContext(context?: Record<string, string>): string {
    if (!context) return '';
    const lines = Object.entries(context).map(([key, val]) => `- ${key}: ${val}`);
    return `User context:\n${lines.join('\n')}`;
  }