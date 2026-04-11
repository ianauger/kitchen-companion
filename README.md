# Kitchen Companion

A digital cookbook application for storing, organizing, and discovering recipes with a beautiful Tailwind CSS interface.

## Features

- **Recipe Storage**: Store recipes with cooking instructions, times, servings, and difficulty
- **Automatic Image Handling**: Provide an image URL and have it automatically downloaded and stored locally
- **Smart Tagging**: Organize by cuisine, protein, spice level, ingredients, or custom tags
- **Search & Filter**: Find recipes by name and filter by tags
- **Random Discovery**: Home page shows 6 random recipes for inspiration
- **Modern UI**: Clean Tailwind CSS interface with sidebar navigation
- **Full REST API**: Complete CRUD operations via API endpoints

## Project Structure

```
kitchen-companion-app/
├── app.py                 # Application entry point
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── README.md              # This file
├── app/
│   ├── __init__.py        # Flask app factory
│   ├── models.py          # SQLAlchemy models (Recipe, Tag)
│   ├── routes.py          # Route handlers (main + API)
│   ├── image_utils.py     # Image download/handling utilities
│   ├── templates/
│   │   ├── layout.html    # Base template with sidebar
│   │   ├── home.html      # Home page (random 6 recipes)
│   │   ├── search.html    # Search and filter page
│   │   ├── api_docs.html  # API documentation page
│   │   ├── features.html  # Features overview page
│   │   └── index.html     # Legacy template
│   └── static/
│       ├── css/
│       │   └── style.css  # Legacy stylesheet
│       ├── js/
│       │   └── main.js    # Frontend JavaScript
│       └── uploads/
│           └── recipes/   # Downloaded recipe images
└── migrations/            # Database migrations (future use)
```

## Pages

| Route | Description |
|-------|-------------|
| `/` | Home page with 6 random recipes displayed in a grid |
| `/search` | Search recipes by name and filter by tags |
| `/api-docs` | API reference documentation |
| `/features` | Feature overview and capabilities |

## Database Schema

### Recipes Table
| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Primary key |
| title | String(255) | Recipe name (required) |
| source_url | String(500) | Original source URL |
| image_url | String(1000) | Remote image URL |
| image_path | String(500) | Local path to downloaded image |
| instructions | Text | Cooking instructions (required) |
| cooking_time | Integer | Cooking time in minutes |
| prep_time | Integer | Preparation time in minutes |
| servings | Integer | Number of servings |
| difficulty | String(20) | easy/medium/hard |
| created_at | DateTime | Creation timestamp |
| updated_at | DateTime | Last update timestamp |

### Tags Table
| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Primary key |
| name | String(100) | Tag name |
| tag_type | String(50) | Category (cuisine/protein/spice_level/ingredient/custom) |

### Recipe_Tags (Association Table)
Many-to-many relationship between recipes and tags.

## API Endpoints

### Pages

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Home page (random 6 recipes) |
| GET | `/search` | Search page with tag filters |
| GET | `/api-docs` | API documentation page |
| GET | `/features` | Features overview page |

### Recipes API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/recipes` | List all recipes (with optional filters) |
| POST | `/api/recipes` | Create a new recipe (with optional image_url) |
| GET | `/api/recipes/<id>` | Get a specific recipe |
| PUT | `/api/recipes/<id>` | Update a recipe |
| DELETE | `/api/recipes/<id>` | Delete a recipe (also deletes local image) |
| GET | `/api/recipes/random` | Get random selection of recipes |

### Query Parameters for GET /api/recipes

| Parameter | Description |
|-----------|-------------|
| `tag` | Filter by tag name |
| `tag_type` | Filter by tag type (cuisine, protein, spice_level, ingredient, custom) |
| `difficulty` | Filter by difficulty (easy, medium, hard) |
| `search` | Search by recipe title (case-insensitive partial match) |

### Query Parameters for GET /api/recipes/random

| Parameter | Description |
|-----------|-------------|
| `count` | Number of recipes to return (default: 6, max: 20) |

### Tags API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tags` | List all tags (with optional filter by type) |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check endpoint |

## Image Handling

When creating or updating a recipe, you can provide an `image_url`:

```json
{
  "title": "My Recipe",
  "instructions": "...",
  "image_url": "https://example.com/recipe-photo.jpg"
}
```

The image will be:
1. Downloaded automatically
2. Saved to `app/static/uploads/recipes/`
3. The local path stored in `image_path`

Local images are:
- Accessible via `url_for('static', filename=recipe.image_path)`
- Deleted when the recipe is deleted
- Replaced when a new `image_url` is provided on update

## Setup & Installation

### Prerequisites
- Python 3.8+
- pip (Python package manager)

### Installation

1. **Create a virtual environment:**
   ```bash
   cd projects/kitchen-companion-app
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # or: venv\Scripts\activate  # On Windows
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

4. **Run the application:**
   ```bash
   python app.py
   ```

   The server will start at `http://localhost:5001`

## Example API Usage

### Create a Recipe with Image

```bash
curl -X POST http://localhost:5001/api/recipes \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Spicy Thai Basil Chicken",
    "instructions": "1. Heat oil in a wok...\n2. Add garlic and chili...",
    "image_url": "https://example.com/thai-basil-chicken.jpg",
    "cooking_time": 20,
    "prep_time": 10,
    "servings": 4,
    "difficulty": "medium",
    "tags": [
      {"name": "Thai", "tag_type": "cuisine"},
      {"name": "chicken", "tag_type": "protein"},
      {"name": "spicy", "tag_type": "spice_level"}
    ]
  }'
```

### Get All Recipes

```bash
curl http://localhost:5001/api/recipes
```

### Search Recipes

```bash
curl "http://localhost:5001/api/recipes?search=thai"
```

### Filter by Tags

```bash
curl "http://localhost:5001/api/recipes?tag_type=cuisine&tag=Thai"
```

### Get Random Recipes

```bash
curl "http://localhost:5001/api/recipes/random?count=6"
```

### Update a Recipe with New Image

```bash
curl -X PUT http://localhost:5001/api/recipes/1 \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/new-photo.jpg"
  }'
```

### Delete a Recipe

```bash
curl -X DELETE http://localhost:5001/api/recipes/1
```

## Verifying Image Ingestion

1. **Create a recipe with an image URL:**
   ```bash
   curl -X POST http://localhost:5001/api/recipes \
     -H "Content-Type: application/json" \
     -d '{"title": "Test", "instructions": "Test", "image_url": "https://picsum.photos/400/300"}'
   ```

2. **Check the response** for the `image_path` field:
   ```json
   {
     "id": 1,
     "title": "Test",
     "image_path": "uploads/recipes/recipe_1_xxx.jpg",
     ...
   }
   ```

3. **Verify the file exists:**
   ```bash
   ls app/static/uploads/recipes/
   ```

4. **Access via the home page** - Visit `http://localhost:5001/` to see recipes with their images displayed.

## Development Notes

- The database is automatically created on first run (SQLite)
- The upload directory `app/static/uploads/recipes/` is created automatically
- Tag types: `cuisine`, `protein`, `spice_level`, `ingredient`, `custom`
- Difficulty levels: `easy`, `medium`, `hard`
- All timestamps are UTC
- Images use Tailwind CSS for responsive display

## License

MIT License