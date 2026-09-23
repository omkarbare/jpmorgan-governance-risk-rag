import { NextRequest, NextResponse } from "next/server";

const backendUrl = process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const query = typeof body.query === "string" ? body.query.trim() : "";
    const topK = Number.isInteger(body.top_k) ? body.top_k : 5;
    const sessionGroqKey = request.headers.get("x-groq-api-key") ?? "";

    if (!query) {
      return NextResponse.json(
        { detail: "query is required" },
        { status: 400 },
      );
    }

    if (query.length > 4000) {
      return NextResponse.json(
        { detail: "query must be 4000 characters or fewer" },
        { status: 400 },
      );
    }

    const response = await fetch(`${backendUrl}/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(sessionGroqKey
          ? { "x-groq-api-key": sessionGroqKey }
          : {}),
      },
      body: JSON.stringify({
        query,
        top_k: Math.min(Math.max(topK, 1), 10),
      }),
      cache: "no-store",
    });

    const raw = await response.text();
    let data: unknown;

    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = { detail: raw || "Backend returned an invalid response" };
    }

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          error instanceof Error
            ? error.message
            : "Unable to connect to the FastAPI backend",
      },
      { status: 502 },
    );
  }
}
