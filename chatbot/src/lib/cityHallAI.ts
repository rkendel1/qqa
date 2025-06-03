// /lib/cityHallAI.ts
// Handles simulated or real RAG-based responses for city hall queries

const fallbackResponses = [
  "Sorry, I couldn't find an answer to that.",
  "Please contact your local city department for further details.",
  "That topic may need human assistance. Try reaching out to City Hall directly."
];

export async function generateCityHallResponse(message: string): Promise<string> {
  try {
    const res = await fetch("http://localhost:8000/rag-query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: message }),
    });

    const data = await res.json();
    return data.response || "Sorry, I couldn't find an answer.";
  } catch (error) {
    console.error("Error fetching RAG response:", error);
    return "There was an error processing your request.";
  }
}