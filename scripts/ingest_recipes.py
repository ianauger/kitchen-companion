 ```python
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode
import json
import time
import random
import logging
import sys
import argparse
import os

# Dependencies
requirements = """
requests
beautifulsoup4
lxml
"""

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def searxng_search(query):
    url = "http://searxng.doomnaught.com/search?" + urlencode({'q': query, 'format': 'json'})
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('results', [])
    else:
        logging.error("Failed to fetch from SearXNG")
        return []

def extract_recipe(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Try JSON-LD first
        ldjson = soup.find('script', type='application/ld+json').string
        recipe = json.loads(ldjson)
    except AttributeError:
        try:
            recipe = {}
            # Default selectors for common recipe classes
            title_tag = soup.find('title') if soup.find('title') else soup.find('h1', class_='entry-title')
            ingredients_tags = soup.find_all('div', class_='ingredient')
            instructions_tags = soup.find_all('div', class_='instruction')
            
            recipe['title'] = title_tag.text if title_tag else None
            recipe['ingredients'] = ', '.join([ing.text for ing in ingredients_tags])
            recipe['instructions'] = [step.text for step in instructions_tags]
            recipe['prep_time'] = int(soup.find('div', class_='prep-time').text.split()[0]) if soup.find('div', class_='prep-time') else None
            recipe['cooking_time'] = int(soup.find('div', class_='cook-time').text.split()[0]) if soup.find('div', class_='cook-time') else None
            recipe['servings'] = int(soup.find('div', class_='servings').text) if soup.find('div', class_='servings') else None
            recipe['image_url'] = soup.find('img', alt=recipe['title'])['src'] if soup.find('img', alt=recipe['title']) else None
        except Exception as e:
            logging.error(f"Failed to extract from {url}: {e}")
            return None
    return recipe

def post_to_sous_chef(recipe):
    headers = {'Content-Type': 'application/json'}
    response = requests.post("http://sous-chef.doomnaught.com/api/recipes", data=json.dumps(recipe), headers=headers)
    if response.status_code == 201:
        logging.info(f"Posted -> ID {response.json().get('id')}")
    else:
        logging.error(f"Failed to post recipe: {response.status_code} - {response.text}")

def main():
    parser = argparse.ArgumentParser(description="Ingest recipes from specified sites using SearXNG and POST them to Sous Chef API.")
    parser.add_argument('--query', type=str, required=True, help='Search query for recipe discovery.')
    parser.add_argument('--max-recipes', type=int, default=10, help='Maximum number of recipes to process.')
    parser.add_argument('--site', type=str, help='Restrict search to a specific site.')
    parser.add_argument('--dry-run', action='store_true', help='Extract and print without posting.')
    parser.add_argument('--output', type=str, help='Save results to a file.')
    
    args = parser.parse_args()
    
    if not os.path.exists('failures.json'):
        open('failures.json', 'w').close()
    
    results = []
    failures = []
    for i, result in enumerate(searxng_search(args.query)):
        if args.site and args.site not in result['url']:
            continue
        try:
            recipe = extract_recipe(result['url'])
            if recipe:
                logging.info(f"Extracting recipe {i+1}/{args.max_recipes}")
                recipe['tags'] = {'protein': 'chicken', 'cuisine': 'Italian', 'spice_level': 'mild'}  # Example tags, adjust as needed
                if not args.dry_run:
                    post_to_sous_chef(recipe)
                    time.sleep(1)
                results.append(recipe)
            else:
                failures.append(result['url'])
        except Exception as e:
            logging.error(f"Failed to process {result['url']}: {e}")
            failures.append(result['url'])
        
        if (i+1) % 5 == 0 and not args.dry_run:
            time.sleep(6)
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=4)
    
    if failures:
        with open('failures.json', 'w') as f:
            json.dump(failures, f, indent=4)

if __name__ == "__main__":
    main()
```