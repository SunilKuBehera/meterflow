"use client";

import { useState } from "react";
import { Send, Loader2, Bot, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export default function AIPlaygroundPage() {
  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || loading) return;

    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/v1/ai/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, max_tokens: 500 }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error?.message || "Failed to generate");
      }

      const data = await res.json();
      setResponse(data.text || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Sparkles className="text-primary" />
          AI Playground
        </h1>
        <p className="text-muted-foreground mt-1">Test AI models and see metered usage in real-time</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border bg-card flex flex-col">
          <div className="border-b p-4">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Bot className="h-5 w-5" />
              Prompt
            </h2>
          </div>
          <div className="flex-1 p-4">
            <form onSubmit={handleSubmit} className="flex flex-col h-full">
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Enter your prompt here..."
                rows={10}
                className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm focus-ring resize-none"
                disabled={loading}
              />
              {error && (
                <p className="mt-3 text-sm text-destructive">{error}</p>
              )}
              <button
                type="submit"
                disabled={loading || !prompt.trim()}
                className="mt-4 flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4" />
                    Generate
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        <div className="rounded-lg border bg-card flex flex-col">
          <div className="border-b p-4">
            <h2 className="text-lg font-semibold">Response</h2>
          </div>
          <div className="flex-1 p-4 overflow-auto">
            {response ? (
              <pre className="whitespace-pre-wrap text-sm">{response}</pre>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
                <Bot className="h-12 w-12 text-muted-foreground/50" />
                <p className="mt-4 text-center">Response will appear here</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}