#!/usr/bin/env python3
"""
Recipe Ingestion Pipeline — SearXNG-powered discovery + Sous Chef API injection.
Dependencies: pip install requests beautifulsoup4 lxml
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode, urlparse
import json
import time
import re
import logging
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SEARXNG_BASE = "http://searxng.doomnaught.com"
SOUS_CHEF_URL = "http://sous-chef.doomnaught.com/api/recipes"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 2
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Sites we know how to parse well
TRUSTED_SITES = [
    "budgetbytes.com", "loveandlemons.com", "recipetineats.com",
    "minimalistbaker.com", "cookieandkate.com", "spendwithpennies.com",
    "damndelicious.net", "gimmesomeoven.com", "skinnytaste.com",
]

# ---------------------------------------------------------------------------
# SearXNG search
# ---------------------------------------------------------------------------
def searxng_search(query: str, site: str | None = None, max_results: int = 50) -> list[dict]:
    """Query SearXNG JSON API and return deduplicated result list."""
    q = f"{query} site:{site}" if site else query
    url = f"{SEARXNG_BASE}/search?{urlencode({'q': q, 'format': 'json'})}"
    
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            log.info(f"Found {len(results)} results for: {q}")
            return results
        except Exception as e:
            log.warning(f"SearXNG attempt {attempt+1} failed: {e}")
            time.sleep(2 ** attempt)
    return []


# ---------------------------------------------------------------------------
# Recipe extraction
# ---------------------------------------------------------------------------
def _parse_ld_json(soup: BeautifulSoup) -> dict | None:
    """Try to extract recipe from JSON-LD schema.org/Recipe."""
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            # Handle @graph wrapping
            items = data.get("@graph", [data])
            if isinstance(items, dict):
                items = [items]
            for item in items:
                if item.get("@type") in ("Recipe", ["Recipe"]):
                    return _normalize_ld_json(item)
        except (json.JSONDecodeError, AttributeError):
            continue
    return None


def _normalize_ld_json(recipe: dict) -> dict:
    """Convert ld+json recipe into our normalized dict."""
    # Ingredients
    ingredients = recipe.get("recipeIngredient", [])
    if isinstance(ingredients, list):
        ingredients_str = "\n".join(f"• {i}" for i in ingredients)
    else:
        ingredients_str = str(ingredients)

    # Instructions
    instructions = recipe.get("recipeInstructions", [])
    if isinstance(instructions, list):
        if all(isinstance(s, dict) for s in instructions):
            steps = [s.get("text", "") for s in instructions]
        else:
            steps = [str(s) for s in instructions]
        instructions_str = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
    else:
        instructions_str = str(instructions)

    # Times — normalize ISO 8601 durations like "PT30M"
    def _iso_minutes(val):
        if isinstance(val, str):
            m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", val)
            if m:
                return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    return {
        "title": recipe.get("name", ""),
        "ingredients": ingredients_str,
        "instructions": instructions_str,
        "prep_time": _iso_minutes(recipe.get("prepTime", 0)),
        "cooking_time": _iso_minutes(recipe.get("cookTime", 0)),
        "servings": int(recipe.get("recipeYield", 0) if isinstance(recipe.get("recipeYield"), (int, str)) else 0) or None,
        "image_url": recipe.get("image", [None])[0] if isinstance(recipe.get("image"), list) else recipe.get("image"),
        "source_url": recipe.get("mainEntityOfPage", {}).get("@id") or recipe.get("url"),
        "difficulty": None,
    }


def _parse_html_fallback(soup: BeautifulSoup, url: str) -> dict | None:
    """Fallback: scrape visible HTML using common recipe class patterns."""
    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    # Ingredients
    ingredients = []
    for cls in ("wprm-recipe-ingredient", "ingredient", "recipe-ingredient"):
        for el in soup.find_all(class_=re.compile(cls)):
            text = el.get_text(" ", strip=True)
            if text:
                ingredients.append(f"• {text}")
    if not ingredients:
        # Try list items inside an "ingredients" heading
        for heading in soup.find_all(["h2", "h3", "h4", "strong"]):
            if "ingredient" in heading.get_text().lower():
                ul = heading.find_next("ul")
                if ul:
                    ingredients = ["• " + li.get_text(" ", strip=True) for li in ul.find_all("li")]
                break
    ingredients_str = "\n".join(ingredients) if ingredients else None

    # Instructions
    instructions = []
    for cls in ("wprm-recipe-instruction", "instruction", "recipe-instruction"):
        for el in soup.find_all(class_=re.compile(cls)):
            text = el.get_text(" ", strip=True)
            if text:
                instructions.append(text)
    if not instructions:
        for heading in soup.find_all(["h2", "h3", "h4", "strong"]):
            if "instruction" in heading.get_text().lower() or "direction" in heading.get_text().lower() or "method" in heading.get_text().lower():
                ol = heading.find_next("ol")
                if ol:
                    instructions = [li.get_text(" ", strip=True) for li in ol.find_all("li")]
                break
    instructions_str = "\n".join(f"{i+1}. {s}" for i, s in enumerate(instructions)) if instructions else None

    # Prep / cook time
    def _find_time(label: str) -> int | None:
        for el in soup.find_all(["span", "div", "p", "time"], string=re.compile(label, re.I)):
            parent = el.parent
            text = parent.get_text()
            nums = re.findall(r"(\d+)", text)
            if nums:
                return int(nums[0])
        return None

    prep = _find_time("prep") or _find_time("Prep")
    cook = _find_time("cook") or _find_time("Cook")
    servings_tag = soup.find("span", class_=re.compile("servings|yield|serves", re.I))
    servings = int(re.findall(r"\d+", servings_tag.get_text())[0]) if servings_tag and re.findall(r"\d+", servings_tag.get_text()) else None
    img = soup.find("img", class_=re.compile("wp-image|featured|hero|recipe", re.I))
    image_url = img.get("src") or img.get("data-src") if img else None

    return {
        "title": title,
        "ingredients": ingredients_str,
        "instructions": instructions_str,
        "prep_time": prep,
        "cooking_time": cook,
        "servings": servings,
        "image_url": image_url,
        "source_url": url,
        "difficulty": None,
    }


def extract_recipe(url: str) -> dict | None:
    """Fetch and extract recipe from a URL. Returns normalized dict or None."""
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code in (403, 404, 410, 451):
                log.warning(f"Skipping {url} (HTTP {resp.status_code})")
                return None
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            # Try structured data first
            recipe = _parse_ld_json(soup)
            if recipe and recipe.get("title") and recipe.get("instructions"):
                recipe["source_url"] = recipe.get("source_url") or url
                return recipe

            # Fall back to HTML scraping
            recipe = _parse_html_fallback(soup, url)
            if recipe and recipe.get("instructions"):
                return recipe

            log.warning(f"Could not extract recipe from {url}")
            return None

        except requests.RequestException as e:
            log.warning(f"Fetch attempt {attempt+1} for {url}: {e}")
            time.sleep(2 ** attempt)

    return None


# ---------------------------------------------------------------------------
# Tag detection
# ---------------------------------------------------------------------------
PROTEIN_MAP = {
    "chicken": "chicken", "turkey": "poultry", "beef": "beef", "pork": "pork",
    "shrimp": "seafood", "salmon": "seafood", "tuna": "seafood", "cod": "seafood",
    "tofu": "tofu", "tempeh": "soy", "lentil": "vegetarian", "chickpea": "vegetarian",
    "bean": "vegetarian", "egg": "eggs", "sausage": "pork", "bacon": "pork",
    "lamb": "lamb", "turkey": "poultry", "duck": "poultry",
}
CUISINE_MAP = {
    "italian": "Italian", "pasta": "Italian", "risotto": "Italian",
    "mexican": "Mexican", "taco": "Mexican", "burrito": "Mexican", "enchilada": "Mexican",
    "indian": "Indian", "curry": "Indian", "tikka": "Indian", "masala": "Indian",
    "chinese": "Chinese", "stir fry": "Chinese", "kung pao": "Chinese",
    "japanese": "Japanese", "sushi": "Japanese", "ramen": "Japanese", "teriyaki": "Japanese",
    "thai": "Thai", "pad thai": "Thai", "greek": "Greek", "mediterranean": "Mediterranean",
    "french": "French", "korean": "Korean", "vietnamese": "Vietnamese",
    "american": "American", "bbq": "American", "southern": "American",
}
SPICE_TERMS_MILD = {"mild", "gentle", "not spicy"}
SPICE_TERMS_HOT = {"spicy", "hot", "fiery", "chili", "jalapeño", "habanero", "sriracha", "cayenne", "red pepper flake", "thai chili"}


def detect_tags(recipe: dict) -> list[dict]:
    """Auto-detect tags from recipe content."""
    text = f"{recipe.get('title','')} {recipe.get('ingredients','')} {recipe.get('instructions','')}".lower()
    tags = []

    # Protein
    for keyword, protein in PROTEIN_MAP.items():
        if keyword in text:
            if not any(t["name"] == protein and t["tag_type"] == "protein" for t in tags):
                tags.append({"name": protein, "tag_type": "protein"})

    # Cuisine
    for keyword, cuisine in CUISINE_MAP.items():
        if keyword in text:
            if not any(t["name"] == cuisine and t["tag_type"] == "cuisine" for t in tags):
                tags.append({"name": cuisine, "tag_type": "cuisine"})

    # Spice level
    if any(s in text for s in SPICE_TERMS_HOT):
        tags.append({"name": "spicy", "tag_type": "spice_level"})
    elif any(tags for tags_list in [t["name"] for t in tags] if any(t in SPICE_TERMS_MILD for t in [tags_list])):
        tags.append({"name": "mild", "tag_type": "spice_level"})
    else:
        tags.append({"name": "medium", "tag_type": "spice_level"})  # default

    # Difficulty heuristic: fast prep + few ingredients = easy
    prep = recipe.get("prep_time") or 0
    cook = recipe.get("cooking_time") or 0
    total = prep + cook
    if total <= 20:
        recipe["difficulty"] = "easy"
    elif total >= 60:
        recipe["difficulty"] = "hard"
    else:
        recipe["difficulty"] = "medium"

    return tags


# ---------------------------------------------------------------------------
# Sous Chef API
# ---------------------------------------------------------------------------
def post_recipe(recipe: dict, dry_run: bool = False) -> int | None:
    """Post a recipe to Sous Chef. Returns the new recipe ID or None."""
    payload = {
        "title": recipe["title"],
        "ingredients": recipe.get("ingredients", ""),
        "instructions": recipe.get("instructions", ""),
        "source_url": recipe.get("source_url", ""),
        "image_url": recipe.get("image_url", ""),
        "prep_time": recipe.get("prep_time") or 0,
        "cooking_time": recipe.get("cooking_time") or 0,
        "servings": recipe.get("servings"),
        "difficulty": recipe.get("difficulty", "medium"),
        "tags": recipe.get("tags", []),
    }

    if dry_run:
        log.info(f"[DRY RUN] Would post: {payload['title']}")
        return None

    try:
        resp = requests.post(
            SOUS_CHEF_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 201:
            rid = resp.json().get("id")
            log.info(f"Posted -> ID {rid}  {payload['title']}")
            return rid
        else:
            log.error(f"POST failed ({resp.status_code}): {resp.text[:200]}")
            return None
    except requests.RequestException as e:
        log.error(f"POST error: {e}")
        return None


def validate_ingestion() -> int:
    """Hit the list endpoint and return number of recipes found."""
    try:
        resp = requests.get(f"{SOUS_CHEF_URL}?per_page=5", timeout=REQUEST_TIMEOUT)
        data = resp.json()
        total = data.get("pagination", {}).get("total", 0)
        log.info(f"Validation: {total} total recipes in database")
        return total
    except Exception as e:
        log.error(f"Validation failed: {e}")
        return -1


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run(args):
    """Execute the full ingestion pipeline."""
    # 1. Discover
    results = searxng_search(args.query, site=args.site, max_results=args.max_recipes * 3)
    if not results:
        log.error("No search results found. Exiting.")
        return

    ingested = []
    failed = []
    posted_count = 0

    # Filter to trusted sites if not restricted
    urls = []
    for r in results:
        url = r.get("url", "")
        if not url:
            continue
        domain = urlparse(url).netloc.lower()
        # Skip non-recipe domains
        if any(x in domain for x in ("youtube.com", "instagram.com", "facebook.com", "pinterest.com", "tiktok.com")):
            continue
        urls.append(url)

    urls = urls[:args.max_recipes * 2]  # Over-fetch a bit for resilience

    for i, url in enumerate(urls):
        if posted_count >= args.max_recipes:
            break

        # Rate limiting
        if posted_count > 0 and posted_count % 5 == 0:
            log.info("Rate-limit pause (6s)...")
            time.sleep(6)
        elif posted_count > 0:
            time.sleep(1)

        log.info(f"Extracting recipe {posted_count+1}/{args.max_recipes}")
        recipe = extract_recipe(url)

        if recipe is None:
            log.warning(f"  Failed to extract: {url}")
            failed.append({"url": url, "reason": "extraction_failed"})
            continue

        # Detect tags
        recipe["tags"] = detect_tags(recipe)
        
        # Post
        rid = post_recipe(recipe, dry_run=args.dry_run)
        if rid or args.dry_run:
            result = {k: recipe.get(k) for k in ("title", "source_url", "cooking_time", "difficulty", "tags")}
            result["id"] = rid
            ingested.append(result)
            posted_count += 1
        else:
            failed.append({"url": url, "title": recipe.get("title"), "reason": "post_failed"})

    # Save results
    output = {
        "timestamp": datetime.utcnow().isoformat(),
        "query": args.query,
        "site_filter": args.site,
        "ingested": len(ingested),
        "failed": len(failed),
        "recipes": ingested,
        "failures": failed,
    }

    out_path = args.output or "last_ingestion.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    log.info(f"Results saved to {out_path}")

    if failed:
        with open("ingestion_failures.json", "w") as f:
            json.dump(failed, f, indent=2, default=str)
        log.info(f"Failures saved to ingestion_failures.json")

    # Validate
    total = validate_ingestion()
    log.info(f"Done. {len(ingested)} ingested, {len(failed)} failed. Database now has {total} recipes.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="SearXNG-powered recipe ingestion for Sous Chef",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""Examples:
  %(prog)s --query "easy chicken dinner" --max-recipes 5
  %(prog)s --query "vegetarian pasta" --site budgetbytes.com --max-recipes 3
  %(prog)s --query "healthy soup" --dry-run --output preview.json
  %(prog)s --query "instant pot meals" --site recipetineats.com --max-recipes 10""",
    )
    parser.add_argument("--query", "-q", required=True, help="Search query for recipe discovery")
    parser.add_argument("--max-recipes", "-n", type=int, default=10, help="Max recipes to ingest (default: 10)")
    parser.add_argument("--site", "-s", help="Restrict to a specific domain (e.g. budgetbytes.com)")
    parser.add_argument("--dry-run", action="store_true", help="Extract and print without posting to API")
    parser.add_argument("--output", "-o", help="Output JSON path (default: last_ingestion.json)")

    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
