// /lib/cityHallAI.ts
// Handles simulated or real RAG-based responses for city hall queries

const fallbackResponses = [
  "Sorry, I couldn't find an answer to that.",
  "Please contact your local city department for further details.",
  "That topic may need human assistance. Try reaching out to City Hall directly."
];

export async function generateCityHallResponse(message: string): Promise<string> {
  try {
    // Note the key 'question' matches your backend QueryRequest model
    const res = await fetch("http://localhost:8000/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: message }),
    });

    const data = await res.json();

    // Your backend returns 'answer' inside the response body
    return data.answer || fallbackResponses[0];
  } catch (error) {
    console.error("Error fetching RAG response:", error);
    return fallbackResponses[2];
  }
}