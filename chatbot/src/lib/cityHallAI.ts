// /lib/cityHallAI.ts
// Handles simulated or real RAG-based responses for city hall queries

const fallbackResponses = [
  "Sorry, I couldn't find an answer to that.",
  "Please contact your local city department for further details.",
  "That topic may need human assistance. Try reaching out to City Hall directly."
];

export interface Message {
  type: "user" | "assistant";
  content: string;
}

export async function generateCityHallResponse(messages: Message[]): Promise<string> {
  try {
    // Build prompt with history
    const prompt = messages
      .map(m => (m.type === "user" ? "User" : "Assistant") + ": " + m.content)
      .join("\n") + "\nAssistant:";

    const res = await fetch("http://localhost:8000/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: prompt }),
    });

    const data = await res.json();

    return data.answer || fallbackResponses[0];
  } catch (error) {
    console.error("Error fetching RAG response:", error);
    return fallbackResponses[2];
  }
}