import { useEffect, useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { api } from "../api/client";
import type { TasteRecommendation, TasteSummary } from "../types";

const GENRE_COLORS = ["#1db954", "#5b8def", "#e0577a", "#f0a63c", "#8b6de0", "#3cc7c9", "#e0525c", "#c9d15b"];

export function Taste() {
  const [summary, setSummary] = useState<TasteSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<TasteSummary>("/me/taste-summary")
      .then(setSummary)
      .catch(() => setError("Couldn't load your taste data. Try refreshing."));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!summary) return <p className="muted">Loading…</p>;

  const genreData = Object.entries(summary.genre_counts).map(([name, value]) => ({ name, value }));

  return (
    <div className="taste-page">
      <h1>Your taste</h1>

      <div className="taste-grid">
        <section className="taste-card">
          <h2>Genre breakdown</h2>
          {genreData.length === 0 ? (
            <p className="muted">Not enough genre data yet — Spotify hasn't tagged your top artists' genres.</p>
          ) : (
            <div className="pie-wrap">
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={genreData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} paddingAngle={2}>
                    {genreData.map((_, index) => (
                      <Cell key={index} fill={GENRE_COLORS[index % GENRE_COLORS.length]} stroke="none" />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#17171c", border: "1px solid #2a2a32", borderRadius: 8 }} />
                </PieChart>
              </ResponsiveContainer>
              <ul className="pie-legend">
                {genreData.map((entry, index) => (
                  <li key={entry.name}>
                    <span className="swatch" style={{ background: GENRE_COLORS[index % GENRE_COLORS.length] }} />
                    {entry.name} <span className="muted">({entry.value})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        <section className="taste-card">
          <h2>Recent listening</h2>
          <div className="stat-block">
            <div className="stat-number">{summary.recent_minutes_listened}</div>
            <div className="muted">minutes, across your last {summary.recent_track_count} plays</div>
          </div>
          <p className="muted taste-caveat">
            This is an estimate from your recent play history, not a full year total — Spotify's public
            API doesn't expose annual listening stats (that's exclusive to their own Wrapped feature).
          </p>
        </section>
      </div>

      <RecommendationsPanel />
    </div>
  );
}

function RecommendationsPanel() {
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const [result, setResult] = useState<TasteRecommendation | null>(null);

  async function generate() {
    setState("loading");
    try {
      const data = await api.get<TasteRecommendation>("/me/recommendations");
      setResult(data);
      setState("idle");
    } catch {
      setState("error");
    }
  }

  return (
    <section className="taste-card recommendations-card">
      <h2>AI taste summary &amp; recommendations</h2>

      {result === null && (
        <div className="recommendations-placeholder">
          <p className="muted">
            Get a short, personalized summary of your taste and a few genres/artists worth exploring next.
          </p>
          <button className="button" onClick={generate} disabled={state === "loading"}>
            {state === "loading" ? "Thinking…" : "Generate my recommendations"}
          </button>
          {state === "error" && <p className="error">Something went wrong — try again.</p>}
        </div>
      )}

      {result && !result.available && (
        <p className="muted">AI recommendations aren't configured yet — coming soon.</p>
      )}

      {result && result.available && (
        <div className="recommendation-result">
          <p>{result.summary}</p>
          <div className="rec-columns">
            <div>
              <h3>Genres to explore</h3>
              <ul>
                {result.recommended_genres.map((genre) => (
                  <li key={genre}>{genre}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Artists to explore</h3>
              <ul>
                {result.recommended_artists.map((artist) => (
                  <li key={artist}>{artist}</li>
                ))}
              </ul>
            </div>
          </div>
          <button onClick={generate} disabled={state === "loading"}>
            {state === "loading" ? "Thinking…" : "Regenerate"}
          </button>
        </div>
      )}
    </section>
  );
}
