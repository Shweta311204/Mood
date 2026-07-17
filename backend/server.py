from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import re
import json
import random
import requests
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

# Load environment variables
load_dotenv()

app = FastAPI(title="Moods - AI-Powered Mood-Based Recommendation API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(MONGO_URL)
db = client.moods_db

# ---------------------------------------------------------------------------
# API keys / config
# ---------------------------------------------------------------------------
# PLACEHOLDER: get a free key at https://www.themoviedb.org/settings/api
TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '')

# Google Books works keyless on a public quota, so no placeholder is required.
# PLACEHOLDER (optional): https://console.cloud.google.com/apis/credentials
GOOGLE_BOOKS_API_KEY = os.environ.get('GOOGLE_BOOKS_API_KEY', '')

# Songs use the iTunes Search API, which is free and requires no API key at all.

# Mood analysis is local/rule-based by default (free, no key, no network call).
# PLACEHOLDER (optional, for smarter analysis): an OpenAI key.
# If set, we call the OpenAI REST API directly with `requests` (no extra SDK).
# Get one at https://platform.openai.com/api-keys
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

VALID_MOODS = [
    "happy", "sad", "excited", "romantic", "nostalgic", "adventurous",
    "relaxed", "anxious", "angry", "hopeful", "melancholic", "energetic",
    "peaceful", "confused", "inspired",
]

# Pydantic models
class MoodAnalysisRequest(BaseModel):
    memory_text: str
    user_id: Optional[str] = None

class RecommendationRequest(BaseModel):
    mood: str
    content_types: List[str] = ["movies", "books", "dramas", "songs"]
    languages: List[str] = ["en"]
    user_id: Optional[str] = None
    page: int = 1

class MoodAnalysisResponse(BaseModel):
    mood: str
    confidence: float
    emotions: List[str]
    analysis: str

class ContentItem(BaseModel):
    id: str
    title: str
    description: str
    rating: Optional[float] = None
    year: Optional[int] = None
    genre: List[str] = []
    language: str = "en"
    image_url: Optional[str] = None
    content_type: str
    url: Optional[str] = None  # e.g. song preview / external link

class RecommendationResponse(BaseModel):
    mood: str
    recommendations: List[ContentItem]
    total_count: int
    page: int = 1
    has_more: bool = True

# ---------------------------------------------------------------------------
# Mood analysis
# ---------------------------------------------------------------------------
# A small, hand-built emotion lexicon. Each mood maps to keywords/phrases that
# tend to co-occur with it. This runs locally, for free, with no API key.
MOOD_LEXICON: Dict[str, List[str]] = {
    "happy": ["happy", "joy", "joyful", "smile", "smiling", "laugh", "laughing",
              "delighted", "cheerful", "glad", "fun", "great day", "wonderful"],
    "sad": ["sad", "cry", "crying", "tears", "heartbroken", "down", "unhappy",
            "grief", "loss", "lonely", "hurt", "miserable", "sorrow"],
    "excited": ["excited", "thrilled", "can't wait", "pumped", "stoked",
                "hyped", "amazing news", "electric", "buzzing"],
    "romantic": ["love", "romance", "romantic", "crush", "date night",
                 "kiss", "sweetheart", "affection", "valentine", "beloved"],
    "nostalgic": ["nostalgic", "remember when", "used to", "childhood",
                  "back then", "old days", "memories", "reminisce", "throwback"],
    "adventurous": ["adventure", "explore", "exploring", "journey", "travel",
                    "hiking", "road trip", "wild", "expedition", "daring"],
    "relaxed": ["relaxed", "chill", "calm", "unwind", "lazy afternoon",
                "cozy", "comfortable", "at ease", "slow morning"],
    "anxious": ["anxious", "worried", "nervous", "stressed", "overwhelmed",
                "panic", "on edge", "uneasy", "dread"],
    "angry": ["angry", "furious", "frustrated", "annoyed", "rage",
              "irritated", "pissed", "mad"],
    "hopeful": ["hopeful", "hope", "optimistic", "looking forward",
                "believe things", "better days", "faith", "positive outlook"],
    "melancholic": ["melancholic", "melancholy", "bittersweet", "wistful",
                    "empty", "hollow", "quiet sadness", "longing"],
    "energetic": ["energetic", "energized", "pumped up", "workout",
                  "unstoppable", "adrenaline", "buzzing with energy", "hyperactive"],
    "peaceful": ["peaceful", "peace", "tranquil", "serene", "still",
                 "quiet moment", "gentle rain", "grateful", "content"],
    "confused": ["confused", "unsure", "don't know", "lost", "conflicted",
                 "torn", "uncertain", "mixed feelings", "puzzled"],
    "inspired": ["inspired", "motivated", "creative spark", "driven",
                 "determined", "empowered", "ambitious", "inspiring"],
}


def analyze_mood_local(memory_text: str) -> Dict[str, Any]:
    """Free, keyless, keyword-based mood detector. Always available."""
    text = memory_text.lower()
    scores: Dict[str, int] = {mood: 0 for mood in VALID_MOODS}
    matched_words: List[str] = []

    for mood, keywords in MOOD_LEXICON.items():
        for kw in keywords:
            if kw in text:
                scores[mood] += 1
                matched_words.append(kw)

    best_mood = max(scores, key=scores.get)
    top_score = scores[best_mood]

    if top_score == 0:
        return {
            "mood": "peaceful",
            "confidence": 0.4,
            "emotions": ["neutral"],
            "analysis": "No strong emotional keywords were detected, so a "
                        "gentle, neutral mood was assumed.",
        }

    confidence = min(0.5 + 0.12 * top_score, 0.95)
    emotions = list(dict.fromkeys(matched_words))[:5]

    return {
        "mood": best_mood,
        "confidence": round(confidence, 2),
        "emotions": emotions,
        "analysis": f"The text's language matched patterns most associated "
                    f"with feeling {best_mood} (matched words: "
                    f"{', '.join(emotions)}).",
    }


def analyze_mood_openai(memory_text: str) -> Optional[Dict[str, Any]]:
    """Optional smarter path if OPENAI_API_KEY is configured. Falls back to
    None (caller should use the local analyzer) on any failure."""
    if not OPENAI_API_KEY:
        return None

    system_message = (
        "You are an expert emotion analyst. Return ONLY compact JSON in "
        'exactly this shape: {"mood": "<one of: ' + ", ".join(VALID_MOODS) +
        '>", "confidence": 0.0-1.0, "emotions": ["..."], "analysis": "..."}'
    )

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": f"Analyze this text: {memory_text}"},
                ],
                "temperature": 0.3,
            },
            timeout=20,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```json|```$", "", content).strip()
        result = json.loads(content)
        if result.get("mood") not in VALID_MOODS:
            return None
        return result
    except Exception as e:
        print(f"OpenAI mood analysis error, falling back to local engine: {e}")
        return None


async def analyze_mood(memory_text: str) -> Dict[str, Any]:
    result = analyze_mood_openai(memory_text)
    if result is None:
        result = analyze_mood_local(memory_text)
    return result

# ---------------------------------------------------------------------------
# External content APIs
# ---------------------------------------------------------------------------
MOOD_TO_MOVIE_GENRES = {
    "happy": "35,10751", "sad": "18", "excited": "28,12", "romantic": "10749",
    "nostalgic": "18,36", "adventurous": "12,28", "relaxed": "35,10770",
    "anxious": "53,27", "angry": "28,80", "hopeful": "18,10751",
    "melancholic": "18", "energetic": "28,878", "peaceful": "99,10751",
    "confused": "9648", "inspired": "18,36",
}

MOOD_TO_TV_GENRES = {
    "happy": "35,10751", "sad": "18", "excited": "10759,80", "romantic": "10749",
    "nostalgic": "18,36", "adventurous": "10759", "relaxed": "35",
    "anxious": "9648,80", "angry": "80,18", "hopeful": "18",
    "melancholic": "18", "energetic": "10759", "peaceful": "99",
    "confused": "9648", "inspired": "99,18",
}

MOOD_TO_BOOK_SEARCH = {
    "happy": ["comedy uplifting fiction", "feel good novel", "humor and joy"],
    "sad": ["drama emotional grief", "heartbreak literary fiction", "loss and healing memoir"],
    "excited": ["adventure thriller fast paced", "action packed fiction", "gripping page turner"],
    "romantic": ["romance love story", "slow burn romance novel", "love letters fiction"],
    "nostalgic": ["historical memoir coming of age", "childhood memoir", "throwback classic fiction"],
    "adventurous": ["adventure travel exploration", "expedition true story", "wilderness survival"],
    "relaxed": ["poetry meditation gentle fiction", "cozy slow fiction", "calm nature writing"],
    "anxious": ["mystery psychological suspense", "psychological thriller", "unease literary fiction"],
    "angry": ["revenge justice gritty fiction", "rebellion dystopian novel", "gritty crime fiction"],
    "hopeful": ["hope resilience uplifting memoir", "against the odds true story", "optimism self help"],
    "melancholic": ["bittersweet literary fiction", "quiet sadness novel", "wistful literary memoir"],
    "energetic": ["action adventure fast paced", "high stakes thriller", "kinetic fast fiction"],
    "peaceful": ["nature mindfulness calm essays", "quiet contemplative essays", "gentle mindfulness"],
    "confused": ["philosophy self discovery", "identity literary fiction", "existential fiction"],
    "inspired": ["motivational biography creativity", "creative nonfiction inspiring", "artist biography"],
}

MOOD_TO_SONG_SEARCH = {
    "happy": ["feel good upbeat pop", "sunny happy songs", "joyful pop hits"],
    "sad": ["sad acoustic ballad", "heartbreak slow songs", "melancholy piano ballad"],
    "excited": ["high energy dance pop", "hype dance anthem", "adrenaline pop"],
    "romantic": ["romantic love songs", "slow love ballad", "romantic duet"],
    "nostalgic": ["throwback classic hits", "retro classic pop", "old school nostalgia"],
    "adventurous": ["epic adventure soundtrack", "cinematic epic score", "bold orchestral anthem"],
    "relaxed": ["chill lofi relaxing", "calm acoustic chill", "laid back easy listening"],
    "anxious": ["calming ambient", "soothing instrumental", "gentle ambient calm"],
    "angry": ["rock intense rage", "hard rock aggressive", "punk rage anthem"],
    "hopeful": ["uplifting inspiring anthem", "hopeful pop anthem", "optimistic anthem"],
    "melancholic": ["melancholic indie", "wistful indie folk", "somber indie ballad"],
    "energetic": ["energetic workout", "upbeat workout pop", "high tempo energy"],
    "peaceful": ["peaceful acoustic instrumental", "serene piano instrumental", "calm acoustic folk"],
    "confused": ["dreamy ambient", "hazy dream pop", "introspective ambient"],
    "inspired": ["motivational anthem", "empowering pop anthem", "driven inspiring rock"],
}

PAGE_SIZE = 12

DEMO_MOVIE = ContentItem(
    id="demo_movie_1", title="Add a TMDB key to see real movies",
    description="Placeholder result — set TMDB_API_KEY in backend/.env to fetch "
                 "real, mood-matched movies from TMDB.",
    rating=None, year=None, genre=["Placeholder"], language="en",
    image_url="https://images.unsplash.com/photo-1489599162158-1f92b42d39d6?w=300&h=450&fit=crop",
    content_type="movie",
)

DEMO_DRAMA = ContentItem(
    id="demo_drama_1", title="Add a TMDB key to see real shows",
    description="Placeholder result — set TMDB_API_KEY in backend/.env to fetch "
                 "real, mood-matched TV shows from TMDB.",
    rating=None, year=None, genre=["Placeholder"], language="en",
    image_url="https://images.unsplash.com/photo-1522869635100-9f4c5e86aa37?w=300&h=450&fit=crop",
    content_type="drama",
)


async def fetch_movies_by_mood(mood: str, language: str = "en", page: int = 1) -> List[ContentItem]:
    if not TMDB_API_KEY:
        return [DEMO_MOVIE]

    genre_ids = MOOD_TO_MOVIE_GENRES.get(mood, "18")
    try:
        response = requests.get(
            "https://api.themoviedb.org/3/discover/movie",
            params={"api_key": TMDB_API_KEY, "with_genres": genre_ids,
                    "language": language, "sort_by": "popularity.desc",
                    "vote_count.gte": 50, "page": max(1, min(page, 500))},
            timeout=10,
        )
        data = response.json()
        results = data.get("results", [])
        random.Random(f"{mood}-movie-{page}").shuffle(results)
        movies = []
        for item in results[:PAGE_SIZE]:
            overview = item.get("overview", "")
            movies.append(ContentItem(
                id=str(item["id"]), title=item["title"],
                description=(overview[:200] + "...") if len(overview) > 200 else overview,
                rating=item.get("vote_average"),
                year=int(item["release_date"][:4]) if item.get("release_date") else None,
                genre=[], language=language,
                image_url=f"https://image.tmdb.org/t/p/w300{item['poster_path']}" if item.get("poster_path") else None,
                content_type="movie",
                url=f"https://www.themoviedb.org/movie/{item['id']}",
            ))
        return movies or [DEMO_MOVIE]
    except Exception as e:
        print(f"TMDB movie API error: {e}")
        return [DEMO_MOVIE]


async def fetch_dramas_by_mood(mood: str, language: str = "en", page: int = 1) -> List[ContentItem]:
    if not TMDB_API_KEY:
        return [DEMO_DRAMA]

    genre_ids = MOOD_TO_TV_GENRES.get(mood, "18")
    try:
        response = requests.get(
            "https://api.themoviedb.org/3/discover/tv",
            params={"api_key": TMDB_API_KEY, "with_genres": genre_ids,
                    "language": language, "sort_by": "popularity.desc",
                    "vote_count.gte": 50, "page": max(1, min(page, 500))},
            timeout=10,
        )
        data = response.json()
        results = data.get("results", [])
        random.Random(f"{mood}-drama-{page}").shuffle(results)
        dramas = []
        for item in results[:PAGE_SIZE]:
            overview = item.get("overview", "")
            dramas.append(ContentItem(
                id=str(item["id"]), title=item["name"],
                description=(overview[:200] + "...") if len(overview) > 200 else overview,
                rating=item.get("vote_average"),
                year=int(item["first_air_date"][:4]) if item.get("first_air_date") else None,
                genre=[], language=language,
                image_url=f"https://image.tmdb.org/t/p/w300{item['poster_path']}" if item.get("poster_path") else None,
                content_type="drama",
                url=f"https://www.themoviedb.org/tv/{item['id']}",
            ))
        return dramas or [DEMO_DRAMA]
    except Exception as e:
        print(f"TMDB TV API error: {e}")
        return [DEMO_DRAMA]


async def fetch_books_by_mood(mood: str, language: str = "en", page: int = 1) -> List[ContentItem]:
    variants = MOOD_TO_BOOK_SEARCH.get(mood, ["fiction"])
    search_term = variants[(page - 1) % len(variants)]
    try:
        params = {"q": search_term, "maxResults": PAGE_SIZE, "orderBy": "relevance",
                  "startIndex": (page - 1) * PAGE_SIZE,
                  "langRestrict": language}
        # Google Books works keyless on the public quota; only attach a key
        # if the user configured one (raises their rate limit).
        if GOOGLE_BOOKS_API_KEY:
            params["key"] = GOOGLE_BOOKS_API_KEY

        response = requests.get("https://www.googleapis.com/books/v1/volumes",
                                 params=params, timeout=10)
        data = response.json()
        books = []
        for item in data.get("items", []):
            info = item.get("volumeInfo", {})
            description = info.get("description", "No description available")
            books.append(ContentItem(
                id=item["id"], title=info.get("title", "Unknown Title"),
                description=(description[:200] + "...") if len(description) > 200 else description,
                rating=info.get("averageRating"),
                year=int(info["publishedDate"][:4]) if info.get("publishedDate") else None,
                genre=info.get("categories", []), language=language,
                image_url=info.get("imageLinks", {}).get("thumbnail"),
                content_type="book",
                url=info.get("infoLink"),
            ))
        return books
    except Exception as e:
        print(f"Google Books API error: {e}")
        return []


async def fetch_songs_by_mood(mood: str, language: str = "en", page: int = 1) -> List[ContentItem]:
    """Uses the iTunes Search API — free, keyless, no rate-limit headaches.
    Rotates the search phrasing per page and samples deterministically so
    each page shows a fresh, stable set of tracks."""
    variants = MOOD_TO_SONG_SEARCH.get(mood, ["music"])
    search_term = variants[(page - 1) % len(variants)]
    try:
        response = requests.get(
            "https://itunes.apple.com/search",
            params={"term": search_term, "media": "music", "entity": "song",
                    "limit": 50, "country": "US"},
            timeout=10,
        )
        data = response.json()
        pool = data.get("results", [])
        random.Random(f"{mood}-song-{page}").shuffle(pool)
        sample = pool[:PAGE_SIZE]
        songs = []
        for item in sample:
            release_date = item.get("releaseDate", "")
            songs.append(ContentItem(
                id=str(item.get("trackId")), title=item.get("trackName", "Unknown Title"),
                description=f"{item.get('artistName', 'Unknown Artist')} — {item.get('collectionName', '')}".strip(" —"),
                rating=None,
                year=int(release_date[:4]) if release_date else None,
                genre=[item["primaryGenreName"]] if item.get("primaryGenreName") else [],
                language=language,
                image_url=item.get("artworkUrl100", "").replace("100x100", "300x300") or None,
                content_type="song",
                url=item.get("trackViewUrl") or item.get("previewUrl"),
            ))
        return songs
    except Exception as e:
        print(f"iTunes Search API error: {e}")
        return []

# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"message": "Moods - AI-Powered Mood-Based Recommendation API",
            "status": "running", "version": "3.0"}


@app.post("/api/analyze-mood", response_model=MoodAnalysisResponse)
async def analyze_mood_endpoint(request: MoodAnalysisRequest):
    """Analyze mood from memory text (local keyword engine, or OpenAI if configured)."""
    try:
        result = await analyze_mood(request.memory_text)

        if request.user_id:
            await db.mood_analyses.insert_one({
                "user_id": request.user_id,
                "memory_text": request.memory_text,
                "mood_result": result,
                "timestamp": datetime.utcnow(),
            })

        return MoodAnalysisResponse(
            mood=result["mood"], confidence=result["confidence"],
            emotions=result["emotions"], analysis=result["analysis"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mood analysis failed: {str(e)}")


@app.post("/api/recommendations", response_model=RecommendationResponse)
async def get_recommendations(request: RecommendationRequest):
    """Get movie / book / drama / song recommendations based on mood.
    Supports pagination via `page` (1-indexed) — call again with an
    incremented page to load more of the same category."""
    try:
        all_recommendations: List[ContentItem] = []
        page = max(1, request.page)

        for content_type in request.content_types:
            for language in request.languages:
                lang_code = language[:2]
                if content_type == "movies":
                    all_recommendations.extend(await fetch_movies_by_mood(request.mood, lang_code, page))
                elif content_type == "books":
                    all_recommendations.extend(await fetch_books_by_mood(request.mood, lang_code, page))
                elif content_type == "dramas":
                    all_recommendations.extend(await fetch_dramas_by_mood(request.mood, lang_code, page))
                elif content_type == "songs":
                    all_recommendations.extend(await fetch_songs_by_mood(request.mood, lang_code, page))

        if request.user_id:
            await db.recommendations.insert_one({
                "user_id": request.user_id, "mood": request.mood,
                "content_types": request.content_types, "languages": request.languages,
                "page": page,
                "recommendations": [rec.dict() for rec in all_recommendations],
                "timestamp": datetime.utcnow(),
            })

        return RecommendationResponse(
            mood=request.mood, recommendations=all_recommendations,
            total_count=len(all_recommendations), page=page,
            has_more=len(all_recommendations) > 0,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {str(e)}")


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy", "app": "Moods", "version": "3.0",
        "mood_engine": "openai" if OPENAI_API_KEY else "local-keyword (free, no key)",
        "apis_configured": {
            "tmdb": bool(TMDB_API_KEY),
            "google_books": "always available (keyless public quota)",
            "songs_itunes": "always available (keyless)",
            "openai_mood_analysis": bool(OPENAI_API_KEY),
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)