# Moods - AI-Powered Mood-Based Recommendation Platform

An intelligent web application that reads the mood in your writing and recommends movies, TV shows, books, and songs to match it — a mood-read, not a genre pick.

## Features

- **Mood Analysis**: Reads emotion from free-text input using a local, free, keyless keyword engine (optionally OpenAI, if you add a key).
- **Cross-Media Recommendations**: Movies, TV shows, books, and songs, all mapped by mood rather than static genre.
- **Interactive Mood Selection**: Skip the text box and pick straight from 15 mood categories.
- **Dark / Night Modes**: Two themes, with the whole UI's accent color grading to match your detected mood.
- **Real-time Processing**: Instant mood analysis and content suggestions.

## Tech Stack

- **Frontend**: React 19, Tailwind CSS, Axios, lucide-react
- **Backend**: Python, FastAPI, Pydantic, Uvicorn
- **Database**: MongoDB with Motor (async driver)
- **Mood engine**: Local keyword-based analyzer (free, no key) — optional OpenAI upgrade
- **External APIs**: TMDB (movies/shows), Google Books (books), iTunes Search API (songs)
- **Deployment**: Docker, Cloud hosting

## Quick Start

### Prerequisites

- Node.js (v18 or higher)
- Python 3.8+
- MongoDB (local or cloud instance)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/moods.my.git
   cd moods.my
   ```

2. **Set up the backend**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys (see below — most are optional)
   ```

4. **Set up the frontend**
   ```bash
   cd frontend
   npm install
   ```

### Environment Variables

See `backend/.env.example` for the full, commented list. In short:

```env
MONGO_URL=mongodb://localhost:27017

# Optional — without it, movies/shows return one placeholder card each
TMDB_API_KEY=

# Optional — Google Books works keyless by default
GOOGLE_BOOKS_API_KEY=

# Optional — leave blank to use the free local mood engine
OPENAI_API_KEY=

# Songs (iTunes Search API) need no configuration at all
```

### Running the Application

1. **Start the backend server**
   ```bash
   cd backend
   python server.py
   # Server will run on http://localhost:8001
   ```

2. **Start the frontend development server**
   ```bash
   cd frontend
   npm start
   # App will open at http://localhost:3000
   ```

## Usage

1. **Describe your mood** — write a memory, thought, or how today felt, and roll the film.
2. **Get recommendations** — browse movies, shows, books, and songs matched to the detected mood.
3. **Or pick a mood directly** — skip text analysis entirely.

## Mood Categories

Happy, Sad, Excited, Romantic, Nostalgic, Adventurous, Relaxed, Anxious, Angry, Hopeful, Melancholic, Energetic, Peaceful, Confused, Inspired.

## Project Structure

```
Moods/
├── backend/
│   ├── server.py              # FastAPI application
│   ├── requirements.txt       # Python dependencies
│   └── .env.example           # Environment variable placeholders
├── frontend/
│   ├── src/
│   │   ├── App.js             # Main React component
│   │   ├── App.css / index.css
│   │   └── index.js
│   ├── public/
│   └── package.json
├── tests/
├── backend_test.py
└── test_result.md
```

## API Endpoints

### POST `/api/analyze-mood`
```json
{ "memory_text": "I spent a peaceful afternoon reading by the window", "user_id": "optional" }
```
Response:
```json
{ "mood": "peaceful", "confidence": 0.85, "emotions": ["calm", "content"], "analysis": "..." }
```

### POST `/api/recommendations`
```json
{ "mood": "peaceful", "content_types": ["movies", "books", "dramas", "songs"], "languages": ["en"], "user_id": "optional" }
```

### GET `/api/health`
Reports which content APIs are configured and which mood engine is active.

## Acknowledgments

- TMDB for movie and TV show data
- Google Books for book information
- iTunes Search API for songs
- Tailwind CSS for styling
