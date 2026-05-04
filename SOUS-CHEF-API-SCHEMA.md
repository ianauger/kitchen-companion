# Sous Chef API Schema

> **Version:** 1.0 | **Base URL:** `http://sous-chef.doomnaught.com`

## Create Recipe

```
POST /api/recipes
Content-Type: application/json
Rate Limit: 10/min
```

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | ✅ | Recipe name (max 255 chars) |
| `instructions` | string | ✅ | Step-by-step cooking instructions |
| `ingredients` | string | ❌ | Ingredients list (free text) |
| `source_url` | string | ❌ | Original recipe source URL (max 500 chars) |
| `image_url` | string | ❌ | Remote image URL — will be downloaded locally (max 1000 chars) |
| `cooking_time` | integer | ❌ | Cooking time in minutes |
| `prep_time` | integer | ❌ | Preparation time in minutes |
| `servings` | integer | ❌ | Number of servings |
| `difficulty` | string | ❌ | `"easy"`, `"medium"`, or `"hard"` (default: `"medium"`) |
| `tags` | array | ❌ | Array of tag objects (see below) |

### Tags Format

Tags must be an array of **objects**, NOT strings:

```json
"tags": [
  { "name": "Italian", "tag_type": "cuisine" },
  { "name": "chicken", "tag_type": "protein" },
  { "name": "medium", "tag_type": "spice_level" }
]
```

### Valid `tag_type` Values

| tag_type | Use For | Examples |
|----------|---------|----------|
| `cuisine` | Regional/cultural origin | Italian, Mexican, Japanese, Indian, Thai, Greek, American, Mediterranean, Korean, French |
| `protein` | Main protein source | chicken, beef, pork, seafood, tofu, vegetarian, eggs |
| `spice_level` | Heat level | mild, medium, spicy |
| `ingredient` | Key ingredient focus | pasta, rice, mushrooms, spinach |
| `custom` | User-defined / miscellaneous | comfort-food, quick, meal-prep, budget-friendly |

### Example: Minimal Request

```json
{
  "title": "Garlic Butter Shrimp",
  "instructions": "1. Melt butter in a skillet over medium heat.\n2. Add garlic and cook 30 seconds.\n3. Add shrimp and cook 2-3 minutes per side until pink.\n4. Squeeze lemon over top and serve."
}
```

Response: `201 Created`

### Example: Full Request

```json
{
  "title": "Garlic Butter Shrimp",
  "instructions": "1. Melt butter in a skillet over medium heat.\n2. Add garlic and cook 30 seconds.\n3. Add shrimp and cook 2-3 minutes per side until pink.\n4. Squeeze lemon over top and serve.",
  "ingredients": "• 1 lb large shrimp, peeled and deveined\n• 3 Tbsp butter\n• 4 garlic cloves, minced\n• 1 lemon\n• Salt and pepper to taste\n• 2 Tbsp fresh parsley, chopped",
  "source_url": "https://www.example.com/garlic-butter-shrimp",
  "image_url": "https://www.example.com/images/shrimp.jpg",
  "cooking_time": 10,
  "prep_time": 10,
  "servings": 4,
  "difficulty": "easy",
  "tags": [
    { "name": "seafood", "tag_type": "protein" },
    { "name": "Mediterranean", "tag_type": "cuisine" },
    { "name": "mild", "tag_type": "spice_level" }
  ]
}
```

Response: `201 Created` — returns the full recipe object with `id`, `created_at`, etc.

### Errors

| Status | Meaning |
|--------|---------|
| `400` | Missing `title` or `instructions`, or invalid `image_url` |
| `429` | Rate limit exceeded (10/min) — wait and retry |
| `500` | Server error (check logs) |

---

## List Recipes

```
GET /api/recipes?page=1&per_page=20&search=chicken&tag=Italian&difficulty=easy
```

### Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Results per page (max 100) |
| `search` | string | — | Full-text search across title, ingredients, instructions |
| `tag` | string | — | Filter by tag name |
| `tag_type` | string | — | Filter by tag type |
| `difficulty` | string | — | Filter: `easy`, `medium`, `hard` |
| `max_prep_time` | integer | — | Max prep time in minutes |
| `max_cooking_time` | integer | — | Max cook time in minutes |
| `max_total_time` | integer | — | Max total (prep + cook) in minutes |

### Response

```json
{
  "recipes": [ ... ],
  "pagination": {
    "current_page": 1,
    "per_page": 20,
    "total": 42,
    "pages": 3,
    "has_prev": false,
    "has_next": true
  }
}
```

---

## Get Single Recipe

```
GET /api/recipes/:id
```

Returns the full recipe object with all fields, tags, and notes.

---

## Get Tags

```
GET /api/tags
```

Returns all known tags as an array of `{ id, name, tag_type }`.

---

## Ingestion Checklist for Subagents

When adding recipes to the database:

1. **Tags are objects, not strings.** Always use `{"name": "...", "tag_type": "..."}` format
2. **Respect rate limits.** Space out requests if adding many recipes (>10, add a short delay between batches)
3. **Fetch from real recipe sites** (budgetbytes.com, loveandlemons.com, recipetineats.com) and extract actual ingredients/instructions
4. **Set prep_time and cooking_time as integers** (not strings)
5. **Use newline-separated instructions** with step numbers: `"1. Do X.\n2. Do Y."`
6. **Use diversity:** vary cuisines, proteins, spice levels, and difficulty across the batch
7. **Validate after ingestion:** hit `GET /api/recipes?per_page=25` to confirm everything landed
