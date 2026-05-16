"""Prep Analyzer — ingredient analysis and prep timeline logic."""
import re
from collections import defaultdict


# ── Unit normalization ────────────────────────────────────────────────
_UNIT_MAP = {
    'cups': 'cup', 'cup': 'cup',
    'tablespoons': 'tbsp', 'tablespoon': 'tbsp', 'tbsp': 'tbsp',
    'teaspoons': 'tsp', 'teaspoon': 'tsp', 'tsp': 'tsp',
    'pounds': 'lb', 'pound': 'lb', 'lb': 'lb', 'lbs': 'lb',
    'ounces': 'oz', 'ounce': 'oz', 'oz': 'oz',
    'grams': 'g', 'gram': 'g', 'g': 'g',
    'kilograms': 'kg', 'kilogram': 'kg', 'kg': 'kg',
    'milliliters': 'ml', 'milliliter': 'ml', 'ml': 'ml',
    'liters': 'l', 'liter': 'l', 'l': 'l',
    'pints': 'pint', 'pint': 'pint',
    'quarts': 'quart', 'quart': 'quart',
    'gallons': 'gallon', 'gallon': 'gallon',
    'cloves': 'clove', 'clove': 'clove',
    'pinch': 'pinch', 'pinches': 'pinch',
    'dash': 'dash', 'dashes': 'dash',
    'bunch': 'bunch', 'bunches': 'bunch',
    'sprig': 'sprig', 'sprigs': 'sprig',
    'slice': 'slice', 'slices': 'slice',
    'can': 'can', 'cans': 'can',
    'package': 'package', 'packages': 'package',
}

# Common words that are not "core" ingredients
_STOP_WORDS = {
    'fresh', 'dried', 'ground', 'frozen', 'canned', 'chopped', 'minced',
    'diced', 'sliced', 'grated', 'shredded', 'peeled', 'cooked', 'raw',
    'large', 'medium', 'small', 'fine', 'coarse', 'cold', 'hot', 'warm',
    'room', 'temperature', 'divided', 'or', 'more', 'less', 'as', 'needed',
    'taste', 'for', 'serving', 'garnish', 'topping', 'optional', 'about',
    'approximately', 'roughly', 'plus', 'extra', 'additional', 'each',
    'and', 'the', 'a', 'an', 'of',
}

# Ingredient category assignment via keyword matching
_INGREDIENT_CATEGORIES = [
    # Produce
    (['lettuce', 'spinach', 'kale', 'arugula', 'cabbage', 'broccoli', 'cauliflower',
      'carrot', 'celery', 'cucumber', 'zucchini', 'bell pepper', 'pepper', 'tomato',
      'onion', 'garlic', 'ginger', 'potato', 'sweet potato', 'avocado', 'mushroom',
      'corn', 'green bean', 'peas', 'asparagus', 'brussels sprout', 'radish',
      'beet', 'leek', 'scallion', 'green onion', 'shallot', 'squash', 'eggplant',
      'pumpkin', 'parsnip', 'turnip', 'artichoke', 'okra',
      'apple', 'banana', 'orange', 'lemon', 'lime', 'grape', 'berry',
      'strawberry', 'blueberry', 'raspberry', 'blackberry', 'mango', 'pineapple',
      'peach', 'pear', 'plum', 'cherry', 'watermelon', 'cantaloupe', 'melon',
      'kiwi', 'pomegranate', 'coconut',
      'basil', 'cilantro', 'parsley', 'mint', 'rosemary', 'thyme', 'dill',
      'sage', 'oregano', 'chive', 'salad', 'greens', 'herb',
      'fruit', 'vegetable', 'produce'], 'Produce'),

    # Meat
    (['chicken', 'beef', 'pork', 'lamb', 'turkey', 'duck', 'bacon', 'sausage',
      'ham', 'steak', 'veal', 'venison', 'bison', 'prosciutto', 'salami',
      'pepperoni', 'ground beef', 'ground pork', 'ground turkey', 'ground chicken',
      'meat', 'roast', 'chop', 'fillet', 'loin', 'rib', 'wing', 'drumstick',
      'thigh', 'breast', 'brisket'], 'Meat'),

    # Seafood
    (['fish', 'salmon', 'tuna', 'cod', 'tilapia', 'halibut', 'trout', 'sardine',
      'anchovy', 'mahi', 'sea bass', 'snapper', 'catfish', 'swordfish',
      'shrimp', 'prawn', 'crab', 'lobster', 'mussel', 'clam', 'oyster',
      'scallop', 'calamari', 'squid', 'octopus', 'roe', 'caviar',
      'seafood'], 'Seafood'),

    # Dairy
    (['milk', 'cream', 'butter', 'cheese', 'yogurt', 'sour cream', 'cream cheese',
      'mascarpone', 'ricotta', 'mozzarella', 'cheddar', 'parmesan', 'feta',
      'brie', 'gouda', 'swiss', 'provolone', 'colby', 'monterey jack',
      'blue cheese', 'goat cheese', 'paneer', 'quark', 'buttermilk',
      'half and half', 'half-and-half', 'whipping cream', 'heavy cream',
      'ice cream', 'egg', 'eggs', 'egg substitute', 'margarine',
      'dairy', 'whey'], 'Dairy'),

    # Pantry
    (['pasta', 'spaghetti', 'penne', 'fusilli', 'linguine', 'fettuccine',
      'macaroni', 'lasagna', 'ravioli', 'tortellini', 'gnocchi', 'noodle',
      'ramen', 'udon', 'soba', 'rice noodle', 'rice paper',
      'rice', 'quinoa', 'couscous', 'barley', 'farro', 'oats', 'oatmeal',
      'grits', 'polenta', 'cornmeal', 'cereal', 'granola', 'muesli',
      'flour', 'breadcrumb', 'panko', 'grain', 'wheat', 'bulgur',
      'millet', 'amaranth', 'buckwheat', 'semolina',
      'bread', 'roll', 'bagel', 'croissant', 'brioche', 'baguette',
      'ciabatta', 'sourdough', 'rye', 'pita', 'naan', 'tortilla',
      'wrap', 'bun', 'muffin', 'cracker',
      'canned tomato', 'canned bean', 'canned soup', 'canned corn',
      'canned pea', 'tomato paste', 'tomato sauce', 'coconut milk',
      'broth', 'stock', 'bean', 'chickpea', 'lentil', 'kidney bean',
      'black bean', 'pinto bean', 'cannellini', 'navy bean', 'lima bean',
      'baked bean', 'refried bean',
      'olive oil', 'vegetable oil', 'canola oil', 'sesame oil', 'peanut oil',
      'avocado oil', 'coconut oil', 'cooking spray',
      'vinegar', 'balsamic', 'apple cider vinegar', 'rice vinegar',
      'wine vinegar', 'soy sauce', 'tamari', 'fish sauce', 'oyster sauce',
      'hoisin', 'worcestershire',
      'ketchup', 'mustard', 'mayonnaise', 'mayo', 'relish', 'hot sauce',
      'sriracha', 'honey', 'maple syrup', 'agave', 'molasses', 'corn syrup',
      'jam', 'jelly', 'preserves', 'pesto', 'tahini', 'miso',
      'gochujang', 'harissa', 'sambal', 'salsa', 'pickle', 'chutney',
      'olive', 'caper', 'condiment', 'sauce', 'dressing',
      'cooking wine', 'mirin', 'sake', 'sherry',
      'sugar', 'brown sugar', 'powdered sugar', 'confectioners sugar',
      'baking powder', 'baking soda', 'yeast', 'cornstarch',
      'chocolate', 'cocoa', 'vanilla', 'gelatin',
      'nut', 'almond', 'walnut', 'pecan', 'cashew', 'peanut',
      'pine nut', 'pistachio', 'macadamia', 'hazelnut',
      'raisin', 'cranberry', 'dried fruit', 'date',
      'tofu', 'tempeh', 'seaweed', 'nori'], 'Pantry'),

    # Spices
    (['salt', 'pepper', 'cumin', 'coriander', 'turmeric', 'paprika',
      'chili powder', 'cinnamon', 'nutmeg', 'clove', 'cardamom',
      'allspice', 'ginger powder', 'garlic powder', 'onion powder',
      'bay leaf', 'mustard seed', 'fennel seed', 'fenugreek',
      'star anise', 'saffron', 'vanilla extract', 'vanilla bean',
      'almond extract', 'seasoning', 'spice', 'spice blend',
      'garam masala', 'curry powder', 'five spice', 'za\'atar', 'sumac',
      'red pepper flake', 'crushed red pepper', 'cayenne',
      'smoked paprika', 'herbes de provence', 'italian seasoning',
      'old bay', 'taco seasoning', 'pumpkin pie spice'], 'Spices'),
]


def _extract_core_ingredient(line):
    """Extract the core ingredient name from an ingredient line.

    Strips quantities, units, and stop words to leave just the key
    ingredient name(s).

    Examples:
        "2 cups all-purpose flour" → "flour"
        "3 cloves garlic, minced" → "garlic"
        "1 lb chicken breasts" → "chicken breasts"
    """
    if not line:
        return ''
    line = line.strip().lower()

    # Remove parenthetical notes like "(about 2 cups)"
    line = re.sub(r'\([^)]*\)', '', line)

    # Remove leading quantity (fractional like "1/2" or "1 1/2" or "1.5")
    line = re.sub(r'^\d+\s*\d*/\d*\s*', '', line)
    line = re.sub(r'^\d+\.?\d*\s*', '', line)

    # Strip trailing comma/period
    line = line.strip(' ,.-')

    # Remove known units at the start
    for unit_full in sorted(_UNIT_MAP.keys(), key=len, reverse=True):
        line = re.sub(rf'^{unit_full}\s+', '', line, count=1)

    # Split and filter out stop words
    words = line.split()
    meaningful = [w.strip(' ,.-') for w in words
                  if w.strip(' ,.-') and w.strip(' ,.-') not in _STOP_WORDS]

    return ' '.join(meaningful)


def _categorize_ingredient(core_name):
    """Categorize a core ingredient name into a category group."""
    if not core_name:
        return 'Other'
    name_lower = core_name.lower()
    for keywords, category in _INGREDIENT_CATEGORIES:
        for kw in keywords:
            if kw in name_lower:
                return category
    return 'Other'


def _classify_prep_step(step_text):
    """Classify a prep/cooking step into a category.

    Returns one of: mise_en_place, cooking, passive, assembly
    """
    if not step_text:
        return 'mise_en_place'
    text = step_text.lower().strip()

    # Passive indicators
    passive_keywords = [
        'simmer', 'bake', 'roast', 'braise', 'stew', 'rest', 'cool',
        'chill', 'refrigerate', 'freeze', 'marinate', 'rise', 'proof',
        'soak', 'steep', 'melt', 'reduce', 'slow cook', 'crockpot',
        'while', 'until tender', 'until golden', 'until bubbly',
        'let it sit', 'let stand', 'set aside', 'meanwhile',
    ]
    for kw in passive_keywords:
        if kw in text:
            return 'passive'

    # Assembly indicators
    assembly_keywords = [
        'serve', 'garnish', 'plate', 'top with', 'sprinkle with',
        'drizzle', 'dust', 'arrange', 'ladle', 'portion', 'divide',
        'dollop', 'scatter', 'finish', 'present',
    ]
    for kw in assembly_keywords:
        if kw in text:
            return 'assembly'

    # Cooking indicators
    cooking_keywords = [
        'cook', 'fry', 'sauté', 'saute', 'sear', 'grill', 'broil',
        'boil', 'steam', 'poach', 'blanch', 'stir-fry', 'stir fry',
        'brown', 'toast', 'flip', 'turn', 'whisk', 'stirring',
        'add', 'pour', 'transfer', 'remove', 'drain', 'strain',
        'fold', 'mix', 'beat', 'blend', 'process', 'knead',
        'roll out', 'shape', 'form', 'stuff', 'fill', 'layer',
        'heat', 'preheat', 'warm', 'season', 'taste and adjust',
    ]
    for kw in cooking_keywords:
        if kw in text:
            return 'cooking'

    # Prep/mise en place indicators
    prep_keywords = [
        'chop', 'dice', 'mince', 'slice', 'grate', 'shred', 'peel',
        'cut', 'trim', 'wash', 'rinse', 'pat dry', 'measure',
        'weigh', 'sift', 'whisk together', 'combine in bowl',
        'prepare', 'prep', 'zest', 'juice', 'crush', 'smash',
        'separate', 'deseed', 'core', 'stem', 'husk',
    ]
    for kw in prep_keywords:
        if kw in text:
            return 'mise_en_place'

    # Default to mise en place
    return 'mise_en_place'


class PrepAnalyzer:
    """Analyzes multiple recipes to generate combined prep workflows."""

    def __init__(self, recipes):
        """Initialize with a list of recipe objects.

        Args:
            recipes: List of Recipe model instances (must have
                     ingredients and instructions text fields).
        """
        self.recipes = recipes

    def detect_shared_ingredients(self):
        """Detect shared ingredients across recipes.

        Returns:
            Dict mapping normalized core ingredient names to a list of
            (recipe_id, recipe_title, original_line) tuples.
        """
        shared = defaultdict(list)
        for recipe in self.recipes:
            if not recipe.ingredients:
                continue
            for line in recipe.ingredients.split('\n'):
                line = line.strip()
                if not line:
                    continue
                core = _extract_core_ingredient(line)
                if core:
                    shared[core].append({
                        'recipe_id': recipe.id,
                        'recipe_title': recipe.title,
                        'original_line': line,
                    })

        # Only return ingredients that appear in >1 recipe
        return {k: v for k, v in shared.items() if len(v) > 1}

    def get_combined_ingredients(self):
        """Get a combined, deduplicated ingredient list grouped by category.

        Returns:
            Dict with keys 'categories' (list of {category, items} objects)
            and 'shared' (the shared ingredients dict).
        """
        all_ingredients = defaultdict(list)
        seen = {}  # normalized core → (category, list of recipes)

        for recipe in self.recipes:
            if not recipe.ingredients:
                continue
            for line in recipe.ingredients.split('\n'):
                line = line.strip()
                if not line:
                    continue
                core = _extract_core_ingredient(line)
                category = _categorize_ingredient(core)

                if core in seen:
                    seen[core]['recipes'].append({
                        'recipe_id': recipe.id,
                        'recipe_title': recipe.title,
                    })
                else:
                    seen[core] = {
                        'category': category,
                        'core': core,
                        'ingredient': line,
                        'recipes': [{
                            'recipe_id': recipe.id,
                            'recipe_title': recipe.title,
                        }],
                    }

        # Group by category
        for core, entry in seen.items():
            category = entry['category']
            all_ingredients[category].append(entry)

        # Build ordered category list
        category_order = ['Produce', 'Meat', 'Seafood', 'Dairy',
                          'Pantry', 'Spices', 'Other']
        categories_list = []
        for cat in category_order:
            if cat in all_ingredients:
                items = all_ingredients[cat]
                # Sort by how many recipes share the ingredient (shared first)
                items.sort(key=lambda x: -len(x['recipes']))
                categories_list.append({
                    'category': cat,
                    'items': items,
                })

        # Catch any categories not in the order list
        for cat in sorted(all_ingredients.keys()):
            if cat not in category_order:
                items = all_ingredients[cat]
                items.sort(key=lambda x: -len(x['recipes']))
                categories_list.append({
                    'category': cat,
                    'items': items,
                })

        shared = self.detect_shared_ingredients()

        return {
            'categories': categories_list,
            'shared': shared,
        }

    def generate_timeline(self):
        """Generate a suggested prep timeline.

        Heuristic order:
        1. Mise en place (chopping, measuring) — do prep that's needed for
           multiple recipes first.
        2. Start longest-cooking items (passive tasks with longest duration).
        3. Fill active cooking windows.
        4. Assembly and plating last.

        Returns:
            Dict: {
                'total_time': estimated total time in minutes,
                'tasks': [ordered task dicts],
                'parallel_windows': [{'at_task': '...', 'description': '...'}],
            }
        """
        tasks = []
        order = 0

        for recipe in self.recipes:
            if not recipe.instructions:
                continue

            steps = [s.strip() for s in recipe.instructions.split('\n')
                     if s.strip()]
            for i, step in enumerate(steps):
                category = _classify_prep_step(step)
                task = {
                    'description': step,
                    'category': category,
                    'recipe_id': recipe.id,
                    'recipe_title': recipe.title,
                    'sort_order': order,
                    'estimated_minutes': _estimate_step_time(step, category),
                    'is_parallel': category == 'passive',
                    'step_index': i,
                }
                tasks.append(task)
                order += 1

        # ── Sort: mise → passive (longest first) → cooking → assembly ──
        cat_priority = {
            'mise_en_place': 0,
            'passive': 1,
            'cooking': 2,
            'assembly': 3,
        }

        tasks.sort(key=lambda t: (
            cat_priority.get(t['category'], 9),
            -(t['estimated_minutes'] or 0) if t['category'] == 'passive' else (t['estimated_minutes'] or 0),
        ))

        # Re-index sort_order
        for idx, t in enumerate(tasks):
            t['sort_order'] = idx

        # Calculate total time: sum of non-parallel task times
        # + the longest parallel task
        parallel_times = []
        active_total = 0
        for t in tasks:
            if t.get('estimated_minutes'):
                if t['is_parallel']:
                    parallel_times.append(t['estimated_minutes'])
                else:
                    active_total += t['estimated_minutes']

        longest_parallel = max(parallel_times) if parallel_times else 0
        total_time = active_total + longest_parallel

        # Generate parallel window suggestions
        parallel_windows = []
        for t in tasks:
            if t['is_parallel'] and t.get('estimated_minutes'):
                parallel_windows.append({
                    'task_description': t['description'],
                    'duration': t['estimated_minutes'],
                    'hint': f'"{t["description"][:50]}..." can happen while doing active tasks',
                })

        return {
            'total_time': total_time if total_time > 0 else None,
            'tasks': tasks,
            'parallel_windows': parallel_windows,
        }


def _estimate_step_time(step_text, category):
    """Estimate time for a step in minutes. Very rough heuristic.

    Args:
        step_text: The step description text.
        category: The classified category.

    Returns:
        Estimated minutes (int) or None if unknown.
    """
    if not step_text:
        return None
    text = step_text.lower()

    # Try to extract explicit times
    time_patterns = [
        (r'(\d+)\s*(?:to|-)\s*(\d+)\s*min', lambda m: (int(m[1]) + int(m[2])) // 2),
        (r'about\s+(\d+)\s*min', lambda m: int(m[1])),
        (r'(\d+)\s*min', lambda m: int(m[1])),
        (r'(\d+)\s*hour', lambda m: int(m[1]) * 60),
        (r'(\d+)\s*(?:to|-)\s*(\d+)\s*hour', lambda m: ((int(m[1]) + int(m[2])) * 60) // 2),
    ]
    for pattern, extractor in time_patterns:
        m = re.search(pattern, text)
        if m:
            return extractor(m)

    # Category-based defaults
    if category == 'passive':
        # Look for cooking method hints
        if 'roast' in text:
            return 30
        if 'bake' in text:
            return 25
        if 'simmer' in text:
            return 15
        if 'braise' in text:
            return 45
        if 'slow cook' in text:
            return 120
        if 'marinate' in text:
            return 15
        if 'chill' in text or 'refrigerate' in text:
            return 30
        if 'rest' in text:
            return 10
        if 'rise' in text or 'proof' in text:
            return 45
        if 'melt' in text:
            return 5
        return 15

    if category == 'cooking':
        if 'boil' in text:
            return 10
        if 'sauté' in text or 'saute' in text or 'fry' in text:
            return 8
        if 'sear' in text:
            return 5
        if 'grill' in text:
            return 10
        if 'steam' in text:
            return 8
        return 10

    if category == 'mise_en_place':
        if 'chop' in text or 'dice' in text:
            return 5
        if 'mince' in text:
            return 3
        if 'grate' in text or 'shred' in text:
            return 3
        if 'peel' in text:
            return 3
        if 'measure' in text or 'sift' in text:
            return 3
        return 5

    if category == 'assembly':
        return 5

    return None
