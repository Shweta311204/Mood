import React, { useState, useRef, useEffect, useCallback } from "react";
import axios from "axios";
import { Moon, Sun, Clapperboard, Loader2 } from "lucide-react";
import "./App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
const API = `${BACKEND_URL}/api`;

const MOOD_WORDS = [
  "happy", "sad", "excited", "romantic", "nostalgic", "adventurous",
  "relaxed", "anxious", "angry", "hopeful", "melancholic", "energetic",
  "peaceful", "confused", "inspired",
];

const TABS = [
  { key: "movies", label: "Movies" },
  { key: "dramas", label: "Shows" },
  { key: "books", label: "Books" },
  { key: "songs", label: "Songs" },
];

/** The four-step read, in the order it actually happens — used for the
 *  editorial "index" list lower on the page. */
const STEPS = [
  {
    n: "01",
    title: "Write",
    desc: "Put down a memory, a passing thought, or just how today felt. There's no wrong way to say it.",
    meta: "no minimum",
  },
  {
    n: "02",
    title: "Read",
    desc: "A rolling anomaly model scores the emotional shape of what you wrote against a library of moods.",
    meta: "isolation forest",
  },
  {
    n: "03",
    title: "Score",
    desc: "The read comes back as a mood word, a confidence line, and the undertones sitting beneath it.",
    meta: "confidence + emotions",
  },
  {
    n: "04",
    title: "Roll",
    desc: "A program is built to match — movies, shows, books, and songs, pulled and shelved by feel.",
    meta: "four reels",
  },
];

/** Fades a section into view the first time it scrolls into the viewport. */
function useReveal() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add("is-visible");
          observer.unobserve(el);
        }
      },
      { threshold: 0.15 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return ref;
}

function Reveal({ as: Tag = "div", variant = "reveal", className = "", style, children, ...rest }) {
  const ref = useReveal();
  return (
    <Tag ref={ref} className={`${variant} ${className}`} style={style} {...rest}>
      {children}
    </Tag>
  );
}

function PosterCard({ item, index }) {
  return (
    <a
      href={item.url || undefined}
      target={item.url ? "_blank" : undefined}
      rel="noreferrer"
      className="poster-card reveal-scale"
      ref={(el) => {
        if (!el) return;
        const observer = new IntersectionObserver(
          ([entry]) => {
            if (entry.isIntersecting) {
              el.classList.add("is-visible");
              observer.unobserve(el);
            }
          },
          { threshold: 0.1 }
        );
        observer.observe(el);
      }}
      style={{ transitionDelay: `${Math.min(index, 6) * 60}ms` }}
    >
      {item.image_url ? (
        <img className="poster-art" src={item.image_url} alt={item.title} loading="lazy" />
      ) : (
        <div className="poster-art flex items-center justify-center px-3 text-center text-xs opacity-50">
          No artwork
        </div>
      )}
      <div className="p-3">
        <p className="font-semibold text-sm leading-snug line-clamp-2" style={{ fontFamily: "var(--font-body)" }}>
          {item.title}
        </p>
        <p className="mt-1 text-xs opacity-60 line-clamp-2">{item.description}</p>
        <div className="mt-2 flex items-center gap-2 text-[11px] opacity-50">
          {item.year && <span>{item.year}</span>}
          {item.rating != null && <span>★ {item.rating.toFixed ? item.rating.toFixed(1) : item.rating}</span>}
        </div>
      </div>
    </a>
  );
}

export default function App() {
  const [theme, setTheme] = useState("day"); // "day" (light) | "night" (dark)
  const [memoryText, setMemoryText] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [loadingRecs, setLoadingRecs] = useState(false);
  const [moodResult, setMoodResult] = useState(null);
  const [activeTab, setActiveTab] = useState("movies");
  const [recommendations, setRecommendations] = useState({});
  const [error, setError] = useState("");
  const [showContinueBar, setShowContinueBar] = useState(true);
  const [showCredits, setShowCredits] = useState(false);
  const programRef = useRef(null);

  useEffect(() => {
    document.body.setAttribute("data-theme", theme === "night" ? "night" : "");
  }, [theme]);

  useEffect(() => {
    if (moodResult?.mood) {
      document.body.setAttribute("data-mood", moodResult.mood);
      setShowContinueBar(true);
    }
  }, [moodResult]);

  // Ambient hero strip: shows the live program once one exists, otherwise a
  // generic placeholder set of mood-tagged art so the hero never feels empty.
  const stripItems = React.useMemo(() => {
    const flat = Object.values(recommendations).flat().filter((r) => r.image_url);
    if (flat.length >= 6) return flat.slice(0, 14);
    return MOOD_WORDS.map((m) => ({
      id: m,
      title: m,
      image_url: `https://picsum.photos/seed/moods-${m}/220/300`,
    }));
  }, [recommendations]);

  const fetchRecommendations = useCallback(async (mood) => {
    setLoadingRecs(true);
    try {
      const { data } = await axios.post(`${API}/recommendations`, {
        mood,
        content_types: ["movies", "dramas", "books", "songs"],
        languages: ["en"],
      });
      const grouped = { movies: [], dramas: [], books: [], songs: [] };
      for (const item of data.recommendations || []) {
        const key = item.content_type === "movie" ? "movies"
          : item.content_type === "drama" ? "dramas"
          : item.content_type === "book" ? "books"
          : item.content_type === "song" ? "songs" : null;
        if (key) grouped[key].push(item);
      }
      setRecommendations(grouped);
    } catch (e) {
      setError("Couldn't load recommendations. Is the backend running?");
    } finally {
      setLoadingRecs(false);
    }
  }, []);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!memoryText.trim()) return;
    setAnalyzing(true);
    setError("");
    setMoodResult(null);
    try {
      const { data } = await axios.post(`${API}/analyze-mood`, {
        memory_text: memoryText,
      });
      setMoodResult(data);
      fetchRecommendations(data.mood);
    } catch (e) {
      setError("Couldn't analyze that just now. Give it another try.");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleDirectMood = (mood) => {
    setMoodResult({ mood, confidence: 1, emotions: [], analysis: "Selected directly." });
    fetchRecommendations(mood);
  };

  return (
    <div className="app" style={{ paddingBottom: moodResult && showContinueBar ? "72px" : 0 }}>
      {/* ---------------------------------------------------------------- */}
      {/* Nav */}
      {/* ---------------------------------------------------------------- */}
      <header className="panel-a">
        <div className="container-inner flex items-center justify-between py-6">
          <div className="flex items-center gap-2">
            <Clapperboard size={18} style={{ color: "rgb(var(--accent))" }} />
            <span className="tracking-widest text-sm" style={{ fontFamily: "var(--font-body)" }}>MOODS</span>
          </div>
          <button
            onClick={() => setTheme((t) => (t === "night" ? "day" : "night"))}
            className="btn-ghost flex items-center gap-2 px-3 py-1.5 text-xs"
            aria-label="Toggle day / night mode"
          >
            {theme === "night" ? <Sun size={14} /> : <Moon size={14} />}
            {theme === "night" ? "Day" : "Night"}
          </button>
        </div>
      </header>

      {/* ---------------------------------------------------------------- */}
      {/* Scene one — hero, with a slow-drifting strip of program art       */}
      {/* behind the headline (empty state uses generic mood-tagged art,    */}
      {/* swaps to the live program once one has been rolled).              */}
      {/* ---------------------------------------------------------------- */}
      <section className="panel-a hero-wrap">
        <div className="hero-strip" aria-hidden="true">
          <div className="hero-strip-track">
            {[...stripItems, ...stripItems].map((item, i) => (
              <div className="hero-strip-item" key={`${item.id}-${i}`}>
                <img src={item.image_url} alt="" loading="lazy" />
                <span className="hero-strip-caption capitalize">{item.title}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="hero-scrim" aria-hidden="true" />

        <div className="hero-content container-inner py-16 md:py-24 max-w-3xl">
          <Reveal>
            <p className="eyebrow mb-4 text-center md:text-left">Tonight's feature</p>
            <h1
              className="text-4xl md:text-6xl leading-[1.05] mb-8 text-center md:text-left"
              style={{ fontFamily: "var(--font-display)", fontStyle: "italic", fontWeight: 500 }}
            >
              What's showing in your head tonight?
            </h1>
            <p className="opacity-60 mb-10 max-w-xl mx-auto md:mx-0 text-center md:text-left">
              Write a memory, a thought, or just how today felt. We'll read the mood
              and roll a program of movies, shows, books, and songs to match it.
            </p>
          </Reveal>

          <Reveal>
            <form onSubmit={handleAnalyze} className="slate p-4 md:p-5">
              <textarea
                rows={4}
                value={memoryText}
                onChange={(e) => setMemoryText(e.target.value)}
                placeholder="I spent the afternoon reading by the window while it rained..."
              />
              <div className="flex items-center justify-between mt-3">
                <span className="text-xs opacity-40">{memoryText.length} characters</span>
                <button type="submit" disabled={analyzing || !memoryText.trim()} className="btn-roll px-5 py-2 text-sm flex items-center gap-2">
                  {analyzing && <Loader2 size={14} className="animate-spin" />}
                  {analyzing ? "Reading the room..." : "Roll film →"}
                </button>
              </div>
            </form>
          </Reveal>

          <Reveal className="mt-10">
            <p className="text-xs opacity-40 mb-3 tracking-wide text-center md:text-left">Or skip straight to a mood</p>
            <div className="flex flex-wrap justify-center md:justify-start gap-2">
              {MOOD_WORDS.map((m) => (
                <button
                  key={m}
                  onClick={() => handleDirectMood(m)}
                  className={`btn-ghost px-3 py-1.5 text-xs capitalize ${moodResult?.mood === m ? "active" : ""}`}
                >
                  {m}
                </button>
              ))}
            </div>
          </Reveal>

          {error && <p className="mt-6 text-sm text-center md:text-left" style={{ color: "rgb(176 48 48)" }}>{error}</p>}
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Statement panel one                                               */}
      {/* ---------------------------------------------------------------- */}
      <section className="panel panel-b">
        <div className="container-inner py-20 md:py-28 text-center">
          <Reveal variant="reveal-fade">
            <p className="statement text-3xl md:text-5xl max-w-3xl mx-auto">
              This isn't about genres.
            </p>
          </Reveal>
        </div>
      </section>

      <section className="panel panel-a">
        <div className="container-inner py-20 md:py-28 text-center">
          <Reveal variant="reveal-fade">
            <p className="statement text-3xl md:text-5xl max-w-3xl mx-auto">
              It's about how you feel right now — and what fits that feeling.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Story panel — the read, explained in prose beside two stills      */}
      {/* ---------------------------------------------------------------- */}
      <section className="panel panel-b">
        <div className="container-inner py-20 md:py-28 grid md:grid-cols-2 gap-14 items-center">
          <Reveal variant="reveal-scale">
            <div className="story-frame">
              <img className="story-img story-img-a" src="https://picsum.photos/seed/moods-write/600/750" alt="" loading="lazy" />
              <img className="story-img story-img-b" src="https://picsum.photos/seed/moods-read/600/750" alt="" loading="lazy" />
            </div>
          </Reveal>
          <Reveal>
            <p className="eyebrow mb-4">The read</p>
            <h3
              className="text-2xl md:text-3xl leading-tight mb-6"
              style={{ fontFamily: "var(--font-display)", fontStyle: "italic", fontWeight: 500 }}
            >
              Not a genre. A feeling, translated.
            </h3>
            <p className="opacity-70 leading-relaxed mb-4">
              Every memory carries a tone before it carries a plot. We read the shape
              of what you wrote — the pace, the color, the ache or the lift in it —
              before we ever look at what's playing this week.
            </p>
            <p className="opacity-70 leading-relaxed">
              A rolling detector scores emotional drift against a library of moods,
              then hands the read to a language model to explain itself in plain
              words. What comes back is a program built for how tonight actually
              feels, not how a genre filter thinks you should feel.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Editorial index — the four steps, in the order they happen        */}
      {/* ---------------------------------------------------------------- */}
      <section className="panel panel-a">
        <div className="container-inner py-20 md:py-28">
          <Reveal>
            <p className="eyebrow mb-2">How it works</p>
            <h3
              className="text-2xl md:text-3xl mb-10"
              style={{ fontFamily: "var(--font-display)", fontStyle: "italic", fontWeight: 500 }}
            >
              Four steps, in order
            </h3>
          </Reveal>
          <Reveal>
            <ol className="reel-index">
              {STEPS.map((s) => (
                <li key={s.n} className="reel-index-row">
                  <span className="reel-index-n">{s.n}</span>
                  <div className="reel-index-body">
                    <div className="reel-index-title">{s.title}</div>
                    <div className="reel-index-desc">{s.desc}</div>
                  </div>
                  <span className="reel-index-meta">{s.meta}</span>
                </li>
              ))}
            </ol>
          </Reveal>
        </div>
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Scene two — mood reveal */}
      {/* ---------------------------------------------------------------- */}
      {moodResult && (
        <section className="panel panel-b">
          <div className="container-inner py-16 md:py-24 text-center">
            <Reveal>
              <p className="eyebrow mb-4">Now screening</p>
              <h2 className="mood-word text-6xl md:text-8xl capitalize mb-6">{moodResult.mood}</h2>
              <div className="max-w-sm mx-auto confidence-track mb-4">
                <div className="confidence-fill" style={{ width: `${Math.round((moodResult.confidence || 0) * 100)}%` }} />
              </div>
              <p className="text-xs opacity-40 mb-5">{Math.round((moodResult.confidence || 0) * 100)}% confidence</p>
              {moodResult.emotions?.length > 0 && (
                <div className="flex flex-wrap justify-center gap-2 mb-5">
                  {moodResult.emotions.map((em, i) => (
                    <span key={i} className="emotion-chip px-3 py-1">{em}</span>
                  ))}
                </div>
              )}
              {moodResult.analysis && <p className="opacity-60 max-w-xl mx-auto text-sm">{moodResult.analysis}</p>}
            </Reveal>
          </div>
        </section>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Scene three — the program */}
      {/* ---------------------------------------------------------------- */}
      {moodResult && (
        <section className="panel panel-a" ref={programRef}>
          <div className="container-inner py-16 md:py-24">
            <Reveal>
              <p className="eyebrow mb-4">The program</p>
              <div className="flex flex-wrap gap-2 mb-8">
                {TABS.map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`btn-ghost px-4 py-2 text-sm ${activeTab === tab.key ? "active" : ""}`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </Reveal>

            <Reveal>
              {loadingRecs ? (
                <p className="text-sm opacity-50 flex items-center gap-2">
                  <Loader2 size={14} className="animate-spin" /> Setting the reels...
                </p>
              ) : recommendations[activeTab]?.length ? (
                <div className="shelf">
                  {recommendations[activeTab].map((item, i) => (
                    <PosterCard key={item.id} item={item} index={i} />
                  ))}
                </div>
              ) : (
                <p className="text-sm opacity-40">Nothing found for this category yet.</p>
              )}
            </Reveal>
          </div>
        </section>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Full-bleed atmosphere break                                       */}
      {/* ---------------------------------------------------------------- */}
      <section className="bleed-frame">
        <img src="https://picsum.photos/seed/moods-bleed/1600/700" alt="" loading="lazy" />
      </section>

      {/* ---------------------------------------------------------------- */}
      {/* Footer marquee */}
      {/* ---------------------------------------------------------------- */}
      <footer className="panel panel-b">
        <div className="py-10">
          <div className="marquee-wrap py-4 mb-6">
            <div className="marquee-track">
              {[...MOOD_WORDS, ...MOOD_WORDS].map((m, i) => (
                <span key={i} className="text-xl md:text-2xl capitalize">{m}</span>
              ))}
            </div>
          </div>
          <p className="text-center text-xs opacity-30 mb-2" style={{ fontFamily: "var(--font-body)" }}>
            Moods — a mood-read, not a genre pick.
          </p>
          <button
            onClick={() => setShowCredits(true)}
            className="block mx-auto text-xs opacity-40 hover:opacity-70 transition-opacity underline decoration-dotted underline-offset-4"
          >
            Credits
          </button>
        </div>
      </footer>

      {/* ---------------------------------------------------------------- */}
      {/* Sticky continue bar — mirrors a "continue where you left off"     */}
      {/* player, but for the mood that's currently on screen.              */}
      {/* ---------------------------------------------------------------- */}
      {moodResult && showContinueBar && (
        <div className="continue-bar is-visible">
          <div className="continue-bar-inner container-inner">
            <div className="continue-bar-meta">
              <span className="continue-bar-label">Now reading</span>
              <span className="continue-bar-mood capitalize">{moodResult.mood}</span>
            </div>
            <div className="continue-bar-track confidence-track">
              <div
                className="confidence-fill"
                style={{ width: `${Math.round((moodResult.confidence || 0) * 100)}%` }}
              />
            </div>
            <button
              className="btn-roll continue-bar-btn px-4 py-2 text-xs"
              onClick={() => programRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
            >
              View program
            </button>
            <button
              className="continue-bar-close"
              onClick={() => setShowContinueBar(false)}
              aria-label="Dismiss now-reading bar"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Credits modal                                                     */}
      {/* ---------------------------------------------------------------- */}
      {showCredits && (
        <div className="credits-backdrop" onClick={() => setShowCredits(false)}>
          <div className="credits-modal" onClick={(e) => e.stopPropagation()}>
            <button className="credits-close" onClick={() => setShowCredits(false)} aria-label="Close credits">
              ×
            </button>
            <p className="eyebrow mb-3">Credits</p>
            <h4
              className="text-2xl mb-5"
              style={{ fontFamily: "var(--font-display)", fontStyle: "italic", fontWeight: 500 }}
            >
              Moods
            </h4>
            <p className="opacity-70 text-sm leading-relaxed mb-3">
              Mood detection runs on a rolling z-score and Isolation Forest drift
              pipeline, explained afterward in plain language by an LLM.
            </p>
            <p className="opacity-70 text-sm leading-relaxed">
              Built with React and FastAPI. Best experienced at night, with the
              lights down.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}