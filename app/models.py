"""Database models for Kitchen Companion."""
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint
from app import db


def _utcnow():
    return datetime.now(timezone.utc)


# Association table for many-to-many relationship between recipes and tags
recipe_tags = db.Table(
    'recipe_tags',
    db.Column('recipe_id', db.Integer, db.ForeignKey('recipes.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)


class Recipe(db.Model):
    """Recipe model representing a cooking recipe.
    
    Attributes:
        id: Unique identifier
        title: Recipe name
        source_url: Original source URL (optional)
        image_url: URL of the recipe cover image (optional, remote)
        image_path: Local filesystem path to the downloaded cover image (optional)
        ingredients: Recipe ingredients (text format)
        instructions: Step-by-step cooking instructions
        cooking_time: Cooking time in minutes (optional)
        prep_time: Preparation time in minutes (optional)
        servings: Number of servings (optional)
        difficulty: Difficulty level (easy, medium, hard)
        created_at: Creation timestamp
        updated_at: Last update timestamp
        tags: Related tags (many-to-many relationship)
        notes: Related notes (one-to-many relationship)
    """
    __tablename__ = 'recipes'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    source_url = db.Column(db.String(500), nullable=True)
    image_url = db.Column(db.String(1000), nullable=True)
    image_path = db.Column(db.String(500), nullable=True)
    ingredients = db.Column(db.Text, nullable=True)
    instructions = db.Column(db.Text, nullable=False)
    cooking_time = db.Column(db.Integer, nullable=True, index=True)  # minutes
    prep_time = db.Column(db.Integer, nullable=True, index=True)  # minutes
    servings = db.Column(db.Integer, nullable=True)
    difficulty = db.Column(db.String(20), default='medium', index=True)  # easy, medium, hard
    created_at = db.Column(db.DateTime, default=_utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)
    
    # Many-to-many relationship with tags
    tags = db.relationship(
        'Tag',
        secondary=recipe_tags,
        backref=db.backref('recipes', lazy='dynamic'),
        lazy='select'
    )
    
    # One-to-many relationship with notes
    notes = db.relationship(
        'Note',
        backref=db.backref('recipe', lazy='select'),
        lazy='select',
        cascade='all, delete-orphan',
        order_by='Note.created_at.desc()'
    )

    # One-to-many relationship with meal plans
    meal_plans = db.relationship(
        'MealPlan',
        back_populates='recipe',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    
    @property
    def total_time(self):
        """Calculate total time (cooking + prep) for filtering."""
        total = 0
        if self.cooking_time:
            total += self.cooking_time
        if self.prep_time:
            total += self.prep_time
        return total if total > 0 else None
    
    def to_dict(self):
        """Convert recipe to dictionary representation."""
        return {
            'id': self.id,
            'title': self.title,
            'source_url': self.source_url,
            'image_url': self.image_url,
            'image_path': self.image_path,
            'ingredients': self.ingredients,
            'instructions': self.instructions,
            'cooking_time': self.cooking_time,
            'prep_time': self.prep_time,
            'servings': self.servings,
            'difficulty': self.difficulty,
            'total_time': self.total_time,
            'tags': [tag.to_dict() for tag in self.tags],
            'notes': [note.to_dict() for note in self.notes],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Recipe {self.title}>'


class Tag(db.Model):
    """Tag model for categorizing recipes.
    
    Supports various tag types:
    - cuisine: Italian, Chinese, Indian, etc.
    - protein: chicken, beef, tofu, etc.
    - spice_level: mild, medium, hot
    - ingredient: specific ingredient tags
    - custom: user-defined tags
    
    Attributes:
        id: Unique identifier
        name: Tag display name
        tag_type: Category of tag (cuisine, protein, spice_level, ingredient, custom)
    """
    __tablename__ = 'tags'
    
    # Valid tag types - centralized definition
    VALID_TYPES = ['cuisine', 'protein', 'spice_level', 'ingredient', 'custom']
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    tag_type = db.Column(db.String(50), nullable=False, default='custom', index=True)
    
    # Database-level constraint to enforce valid tag types and name length
    __table_args__ = (
        CheckConstraint(
            "tag_type IN ('cuisine', 'protein', 'spice_level', 'ingredient', 'custom')",
            name='ck_tag_type_valid'
        ),
        CheckConstraint(
            "LENGTH(name) <= 100",
            name='ck_tag_name_length'
        ),
        db.UniqueConstraint('name', 'tag_type', name='uix_tag_name_type'),
    )
    
    @classmethod
    def get_or_create(cls, name, tag_type='custom'):
        """Get existing tag or create a new one.
        
        Centralizes tag creation logic to ensure consistent handling.
        Validates tag_type against VALID_TYPES before creation.
        
        Args:
            name: Tag name (case-insensitive lookup)
            tag_type: Tag category (must be in VALID_TYPES)
            
        Returns:
            Tuple of (Tag instance, bool created) - created is True if new tag was created
            
        Raises:
            ValueError: If tag_type is not in VALID_TYPES
        """
        # Validate tag_type
        if tag_type not in cls.VALID_TYPES:
            raise ValueError(
                f"Invalid tag_type '{tag_type}'. Must be one of: {', '.join(cls.VALID_TYPES)}"
            )
        
        # Normalize name for consistent lookup
        normalized_name = name.strip() if name else name
        
        # Try to find existing tag (case-insensitive)
        existing = cls.query.filter(
            db.func.lower(cls.name) == db.func.lower(normalized_name),
            cls.tag_type == tag_type
        ).first()
        
        if existing:
            return existing, False
        
        # TODO: wrap insert in try/except IntegrityError + re-query to handle concurrent
        # requests that both reach this point simultaneously (race condition).
        new_tag = cls(name=normalized_name, tag_type=tag_type)
        db.session.add(new_tag)
        db.session.flush()  # Flush to get ID without committing
        
        return new_tag, True
    
    def to_dict(self):
        """Convert tag to dictionary representation."""
        return {
            'id': self.id,
            'name': self.name,
            'tag_type': self.tag_type
        }
    
    def __repr__(self):
        return f'<Tag {self.name} ({self.tag_type})>'


class Note(db.Model):
    """Note model for adding notes to recipes.
    
    Attributes:
        id: Unique identifier
        recipe_id: Foreign key to the associated recipe
        content: Note content (text)
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = 'notes'
    
    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)
    
    # Database-level constraint to enforce content length
    __table_args__ = (
        CheckConstraint(
            "LENGTH(content) <= 2000",
            name='ck_note_content_length'
        ),
    )
    
    def to_dict(self):
        """Convert note to dictionary representation."""
        return {
            'id': self.id,
            'recipe_id': self.recipe_id,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<Note {self.id} for Recipe {self.recipe_id}>'


# ── Prep Session Models ────────────────────────────────────────────────

class PrepSession(db.Model):
    """A prep session groups multiple recipes for coordinated cooking.

    Attributes:
        id: Unique identifier
        name: Optional display name (e.g. "Sunday Dinner")
        created_at, updated_at: Timestamps
        recipes: List of PrepSessionRecipe associations
        tasks: List of generated PrepTask records
    """
    __tablename__ = 'prep_sessions'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    recipes = db.relationship(
        'PrepSessionRecipe', backref='session', lazy='joined',
        cascade='all, delete-orphan',
        order_by='PrepSessionRecipe.sort_order'
    )
    tasks = db.relationship(
        'PrepTask', backref='session', lazy='select',
        cascade='all, delete-orphan',
        order_by='PrepTask.sort_order'
    )

    def to_dict(self, include_analysis=False):
        d = {
            'id': self.id,
            'name': self.name,
            'recipe_count': len(self.recipes) if self.recipes else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'recipes': [r.to_dict() for r in self.recipes] if self.recipes else [],
        }
        if include_analysis:
            d['tasks'] = [t.to_dict() for t in self.tasks] if self.tasks else []
            # Count completed tasks
            if self.tasks:
                d['tasks_completed'] = sum(1 for t in self.tasks if t.completed)
                d['tasks_total'] = len(self.tasks)
        return d

    def __repr__(self):
        return f'<PrepSession {self.name or self.id}>'


class PrepSessionRecipe(db.Model):
    """Association between a prep session and a recipe, with ordering.

    Attributes:
        id: Unique identifier
        session_id: FK to PrepSession
        recipe_id: FK to Recipe
        sort_order: Cooking order within the session
        servings_multiplier: Scale factor for servings
    """
    __tablename__ = 'prep_session_recipes'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey('prep_sessions.id'), nullable=False
    )
    recipe_id = db.Column(
        db.Integer, db.ForeignKey('recipes.id'), nullable=False
    )
    sort_order = db.Column(db.Integer, default=0)
    servings_multiplier = db.Column(db.Float, default=1.0)

    recipe = db.relationship('Recipe', lazy='joined')

    __table_args__ = (
        db.UniqueConstraint('session_id', 'recipe_id',
                            name='uix_session_recipe'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'recipe_id': self.recipe_id,
            'recipe_title': self.recipe.title if self.recipe else None,
            'sort_order': self.sort_order,
            'servings_multiplier': self.servings_multiplier,
        }

    def __repr__(self):
        return f'<PrepSessionRecipe session={self.session_id} recipe={self.recipe_id}>'


class PrepTask(db.Model):
    """A prep task generated by analysis for a prep session.

    Attributes:
        id: Unique identifier
        session_id: FK to PrepSession
        description: What to do
        category: mise, cook, assemble, garnish
        recipe_id: Optional FK to source recipe
        estimated_minutes: Time estimate
        sort_order: Ordering within the session
        is_parallel: Can be done during passive tasks
        completed: Whether the task has been checked off
        depends_on: FK to another PrepTask that must be done first
        created_at: Timestamp
    """
    __tablename__ = 'prep_tasks'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey('prep_sessions.id'), nullable=False
    )
    description = db.Column(db.String(500), nullable=False)
    category = db.Column(
        db.String(50), nullable=False, default='mise'
    )  # mise, cook, assemble, garnish
    recipe_id = db.Column(
        db.Integer, db.ForeignKey('recipes.id'), nullable=True
    )
    estimated_minutes = db.Column(db.Integer, nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    is_parallel = db.Column(db.Boolean, default=False)
    completed = db.Column(db.Boolean, default=False)
    depends_on = db.Column(
        db.Integer, db.ForeignKey('prep_tasks.id'), nullable=True
    )
    created_at = db.Column(db.DateTime, default=_utcnow)

    # Optional backref to recipe
    recipe = db.relationship('Recipe', lazy='joined')

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'description': self.description,
            'category': self.category,
            'recipe_id': self.recipe_id,
            'recipe_title': self.recipe.title if self.recipe else None,
            'estimated_minutes': self.estimated_minutes,
            'sort_order': self.sort_order,
            'is_parallel': self.is_parallel,
            'completed': self.completed,
            'depends_on': self.depends_on,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<PrepTask {self.description[:40]}...>'


# ── Pantry Inventory Models ─────────────────────────────────────────────

class PantryItem(db.Model):
    """An item in the user's pantry inventory.

    Attributes:
        id: Unique identifier
        name: Item name (unique)
        quantity: How much you have (default 0)
        unit: Unit of measurement (cups, lbs, pieces, etc.)
        category: Mirrors aisle categorization (Produce, Meat, etc.)
        min_quantity: Low-stock threshold (default 0 = no alert)
        purchased_date: Last time you bought it
        expiry_date: When it expires
        notes: Optional notes
        created_at, updated_at: Timestamps
    """
    __tablename__ = 'pantry_items'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True, index=True)
    quantity = db.Column(db.Float, default=0)
    unit = db.Column(db.String(50), nullable=True)
    category = db.Column(db.String(50), default='Other', index=True)
    min_quantity = db.Column(db.Float, default=0)
    purchased_date = db.Column(db.DateTime, nullable=True)
    expiry_date = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    @property
    def is_low_stock(self):
        """True if quantity is non-zero and at or below min_quantity."""
        return self.min_quantity > 0 and self.quantity <= self.min_quantity

    @property
    def days_until_expiry(self):
        """Return days until expiry (negative if past), or None."""
        if self.expiry_date is None:
            return None
        delta = self.expiry_date - datetime.now(timezone.utc)
        return delta.days

    def to_dict(self):
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'name': self.name,
            'quantity': self.quantity,
            'unit': self.unit,
            'category': self.category,
            'min_quantity': self.min_quantity,
            'is_low_stock': self.is_low_stock,
            'days_until_expiry': self.days_until_expiry,
            'purchased_date': self.purchased_date.isoformat() if self.purchased_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<PantryItem {self.name}>'


# ── Aisle classification keyword mappings ──────────────────────────────

# Keyword → aisle name.  Checked in order; first match wins.
_AISLE_KEYWORDS = [
    # Produce
    (['lettuce', 'spinach', 'kale', 'arugula', 'cabbage', 'broccoli', 'cauliflower',
      'carrot', 'celery', 'cucumber', 'zucchini', 'bell pepper', 'pepper', 'tomato',
      'onion', 'garlic', 'ginger', 'potato', 'sweet potato', 'avocado', 'mushroom',
      'corn', 'green bean', 'peas', 'asparagus', 'brussels sprout', 'radish',
      'beet', 'leek', 'scallion', 'green onion', 'shallot', 'squash', 'eggplant',
      'pumpkin', 'parsnip', 'turnip', 'rutabaga', 'artichoke', 'okra',
      'fruit', 'apple', 'banana', 'orange', 'lemon', 'lime', 'grape', 'berry',
      'strawberry', 'blueberry', 'raspberry', 'blackberry', 'mango', 'pineapple',
      'peach', 'pear', 'plum', 'cherry', 'watermelon', 'cantaloupe', 'melon',
      'kiwi', 'pomegranate', 'coconut', 'herb', 'basil', 'cilantro', 'parsley',
      'mint', 'rosemary', 'thyme', 'dill', 'sage', 'oregano', 'chive',
      'salad', 'greens'], 'Produce'),

    # Meat & Seafood
    (['chicken', 'beef', 'pork', 'lamb', 'turkey', 'duck', 'bacon', 'sausage',
      'ham', 'steak', 'ground beef', 'ground pork', 'ground turkey', 'ground chicken',
      'veal', 'venison', 'bison', 'prosciutto', 'salami', 'pepperoni',
      'fish', 'salmon', 'tuna', 'cod', 'tilapia', 'halibut', 'trout', 'sardine',
      'anchovy', 'mahi', 'sea bass', 'snapper', 'catfish', 'swordfish',
      'shrimp', 'prawn', 'crab', 'lobster', 'mussel', 'clam', 'oyster', 'scallop',
      'calamari', 'squid', 'octopus', 'roe', 'caviar',
      'meat', 'seafood', 'steak', 'roast', 'chop', 'fillet', 'loin', 'rib',
      'wing', 'drumstick', 'thigh', 'breast'], 'Meat & Seafood'),

    # Deli
    (['deli', 'lunch meat', 'cold cut', 'bologna', 'pastrami', 'mortadella',
      'roast beef', 'corned beef', 'pâté', 'terrine', 'olive bar',
      'hummus', 'prepared', 'ready-to-eat', 'sandwich'], 'Deli'),

    # Dairy
    (['milk', 'cream', 'butter', 'cheese', 'yogurt', 'sour cream', 'cream cheese',
      'mascarpone', 'ricotta', 'mozzarella', 'cheddar', 'parmesan', 'feta',
      'brie', 'gouda', 'swiss', 'provolone', 'colby', 'monterey jack',
      'blue cheese', 'goat cheese', 'paneer', 'quark', 'buttermilk',
      'half and half', 'half-and-half', 'whipping cream', 'heavy cream',
      'ice cream', 'egg', 'eggs', 'egg substitute', 'margarine',
      'dairy', 'whey', 'casein', 'lactose'], 'Dairy'),

    # Bakery
    (['bread', 'roll', 'bagel', 'croissant', 'brioche', 'baguette', 'ciabatta',
      'sourdough', 'rye', 'pita', 'naan', 'tortilla', 'wrap', 'bun',
      'english muffin', 'muffin', 'scone', 'doughnut', 'donut', 'pastry',
      'cake', 'pie', 'cookie', 'brownie', 'cracker', 'baking',
      'baked good', 'baker'], 'Bakery'),

    # Grains & Pasta
    (['pasta', 'spaghetti', 'penne', 'fusilli', 'linguine', 'fettuccine',
      'macaroni', 'lasagna', 'ravioli', 'tortellini', 'gnocchi', 'noodle',
      'ramen', 'udon', 'soba', 'rice noodle', 'rice paper',
      'rice', 'quinoa', 'couscous', 'barley', 'farro', 'oats', 'oatmeal',
      'grits', 'polenta', 'cornmeal', 'cereal', 'granola', 'muesli',
      'flour', 'breadcrumb', 'panko', 'grain', 'wheat', 'bulgur',
      'millet', 'amaranth', 'buckwheat', 'semolina'], 'Grains & Pasta'),

    # Canned Goods
    (['canned', 'tin', 'jarred', 'canned tomato', 'canned bean', 'canned soup',
      'canned tuna', 'canned salmon', 'canned corn', 'canned pea',
      'tomato paste', 'tomato sauce', 'coconut milk', 'broth', 'stock',
      'sardine', 'anchovy', 'bean', 'chickpea', 'lentil', 'kidney bean',
      'black bean', 'pinto bean', 'cannellini', 'navy bean', 'lima bean',
      'baked bean', 'refried bean'], 'Canned Goods'),

    # Spices
    (['salt', 'pepper', 'cumin', 'coriander', 'turmeric', 'paprika', 'chili powder',
      'cinnamon', 'nutmeg', 'clove', 'cardamom', 'allspice', 'ginger powder',
      'garlic powder', 'onion powder', 'bay leaf', 'mustard seed', 'fennel seed',
      'fenugreek', 'star anise', 'saffron', 'vanilla extract', 'vanilla bean',
      'almond extract', 'seasoning', 'spice', 'spice blend', 'garam masala',
      'curry powder', 'five spice', 'za\'atar', 'sumac', 'oregano dried',
      'thyme dried', 'basil dried', 'rosemary dried', 'dill dried',
      'red pepper flake', 'crushed red pepper', 'cayenne', 'smoked paprika'], 'Spices'),

    # Condiments & Sauces
    (['ketchup', 'mustard', 'mayonnaise', 'mayo', 'relish', 'hot sauce', 'sriracha',
      'soy sauce', 'tamari', 'fish sauce', 'oyster sauce', 'hoisin', 'worcestershire',
      'vinegar', 'balsamic', 'apple cider vinegar', 'rice vinegar', 'wine vinegar',
      'olive oil', 'vegetable oil', 'canola oil', 'sesame oil', 'peanut oil',
      'avocado oil', 'coconut oil', 'cooking spray', 'pam',
      'bbq sauce', 'barbecue sauce', 'steak sauce', 'a1', 'teriyaki',
      'salsa', 'pico', 'guacamole', 'pickle', 'chutney', 'marmalade',
      'jam', 'jelly', 'preserves', 'honey', 'maple syrup', 'agave',
      'molasses', 'corn syrup', 'syrup', 'condiment', 'sauce', 'dressing',
      'salad dressing', 'vinaigrette', 'marinade', 'dip', 'pesto',
      'tahini', 'miso', 'gochujang', 'harissa', 'sambal',
      'capers', 'olive'], 'Condiments & Sauces'),

    # Frozen
    (['frozen', 'freezer', 'ice cream', 'popsicle', 'frozen vegetable',
      'frozen fruit', 'frozen pizza', 'frozen dinner', 'frozen meal',
      'tv dinner', 'waffle', 'frozen waffle', 'tater tot', 'french fry',
      'frozen fish', 'fish stick', 'frozen shrimp', 'frozen berry',
      'sorbet', 'gelato', 'frozen yogurt'], 'Frozen'),

    # Beverages
    (['coffee', 'tea', 'juice', 'soda', 'pop', 'water', 'sparkling water',
      'tonic', 'seltzer', 'club soda', 'mineral water', 'soft drink',
      'energy drink', 'sports drink', 'lemonade', 'iced tea',
      'hot chocolate', 'cocoa', 'milk alternative', 'almond milk',
      'oat milk', 'soy milk', 'coconut water', 'kombucha',
      'beer', 'wine', 'liquor', 'spirit', 'whiskey', 'vodka', 'rum',
      'gin', 'tequila', 'champagne', 'prosecco', 'beverage', 'drink'], 'Beverages'),

    # International
    (['soy', 'tofu', 'tempeh', 'kimchi', 'seaweed', 'nori', 'wakame',
      'rice cake', 'mochi', 'daikon', 'bok choy', 'napa cabbage', 'choy',
      'wasabi', 'pickled ginger', 'mirin', 'sake', 'dashi',
      'curry paste', 'curry', 'tikka', 'masala', 'naan bread',
      'sambal oelek', 'sambal', 'kecap manis', 'shrimp paste',
      'tortilla', 'salsa verde', 'chipotle', 'taco', 'enchilada',
      'mole', 'adobo', 'sofrito', 'goya', 'latino',
      'pho', 'bahn', 'wonton', 'dumpling', 'spring roll', 'egg roll',
      'international', 'ethnic', 'asian', 'latin', 'mediterranean',
      'halal', 'kosher'], 'International'),

    # Health & Beauty
    (['shampoo', 'conditioner', 'soap', 'body wash', 'deodorant', 'toothpaste',
      'toothbrush', 'floss', 'mouthwash', 'lotion', 'sunscreen', 'razor',
      'shaving', 'tampon', 'pad', 'tissue', 'paper towel', 'toilet paper',
      'laundry', 'detergent', 'bleach', 'cleaner', 'cleaning', 'dish soap',
      'sponge', 'trash bag', 'ziploc', 'aluminum foil', 'plastic wrap',
      'parchment paper', 'wax paper', 'band-aid', 'first aid', 'medicine',
      'vitamin', 'supplement', 'pain reliever', 'aspirin', 'ibuprofen',
      'acetaminophen', 'allergy', 'cold medicine'], 'Health & Beauty'),

    # Household
    (['battery', 'light bulb', 'hardware', 'tool', 'duct tape', 'glue',
      'extension cord', 'air freshener', 'candle', 'pet food', 'dog food',
      'cat food', 'cat litter', 'bird seed', 'plant', 'potting soil',
      'gardening', 'office supply', 'pen', 'paper', 'envelope', 'broom',
      'mop', 'vacuum bag'], 'Household'),
]


def classify_aisle(item_name):
    """Classify a shopping item name into a default aisle name using keyword matching.

    Args:
        item_name: The shopping item name string.

    Returns:
        Aisle name string (e.g. 'Produce', 'Dairy'). Returns 'Other' if no match.
    """
    if not item_name:
        return 'Other'
    name_lower = item_name.lower().strip()
    for keywords, aisle_name in _AISLE_KEYWORDS:
        for kw in keywords:
            if kw in name_lower:
                return aisle_name
    return 'Other'


DEFAULT_AISLES = [
    'Produce', 'Meat & Seafood', 'Deli', 'Dairy', 'Bakery',
    'Grains & Pasta', 'Canned Goods', 'Spices', 'Condiments & Sauces',
    'Frozen', 'Beverages', 'International', 'Health & Beauty',
    'Household', 'Other'
]


class Store(db.Model):
    """Grocery store model with per-store aisle layouts and item overrides.

    Attributes:
        id: Unique identifier
        name: Store display name (e.g. "Safeway #1234")
        created_at: Creation timestamp
    """
    __tablename__ = 'stores'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)

    aisles = db.relationship(
        'StoreAisle', backref='store', lazy='select',
        cascade='all, delete-orphan',
        order_by='StoreAisle.sort_order'
    )
    overrides = db.relationship(
        'AisleOverride', backref='store', lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def to_dict(self, include_aisles=False):
        d = {
            'id': self.id,
            'name': self.name,
            'aisle_count': len(self.aisles) if self.aisles else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_aisles:
            d['aisles'] = [a.to_dict() for a in self.aisles]
        return d

    def __repr__(self):
        return f'<Store {self.name}>'


class StoreAisle(db.Model):
    """Aisle within a specific store, ordered by sort_order.

    Attributes:
        id: Unique identifier
        store_id: FK to the parent store
        name: Display name (e.g. "Produce", "Deli")
        sort_order: Ordering position within the store
    """
    __tablename__ = 'store_aisles'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    __table_args__ = (
        db.UniqueConstraint('store_id', 'name', name='uix_store_aisle'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'name': self.name,
            'sort_order': self.sort_order,
        }

    def __repr__(self):
        return f'<StoreAisle {self.name} (store={self.store_id})>'


class AisleOverride(db.Model):
    """Per-store override mapping a normalized item name to a specific aisle.

    Allows users to customize where items land (e.g. "tortillas"
    might be in "International" at one store but "Bakery" at another).

    Attributes:
        id: Unique identifier
        store_id: FK to the store this override belongs to
        item_name_normalized: Lowercase, stripped item name for matching
        aisle_id: FK to the target StoreAisle
    """
    __tablename__ = 'aisle_overrides'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    item_name_normalized = db.Column(db.String(200), nullable=False)
    aisle_id = db.Column(db.Integer, db.ForeignKey('store_aisles.id'), nullable=False)

    aisle_rel = db.relationship('StoreAisle', lazy='joined')

    __table_args__ = (
        db.UniqueConstraint('store_id', 'item_name_normalized',
                            name='uix_store_item_override'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'item_name_normalized': self.item_name_normalized,
            'aisle_id': self.aisle_id,
            'aisle_name': self.aisle_rel.name if self.aisle_rel else None,
        }

    def __repr__(self):
        return f'<AisleOverride {self.item_name_normalized} → aisle {self.aisle_id}>'


class ShoppingItem(db.Model):
    """Shopping list item model.
    
    Tracks items added from recipe ingredients or manually.
    
    Attributes:
        id: Unique identifier
        name: Item name (e.g., "2 cups flour")
        recipe_id: Optional FK to the source recipe
        purchased: Whether the item has been checked off
        aisle_override_id: Optional FK to a per-store aisle override
        created_at: When the item was added
        updated_at: Last update timestamp
    """
    __tablename__ = 'shopping_items'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(500), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=True)
    purchased = db.Column(db.Boolean, default=False, index=True)
    aisle_override_id = db.Column(db.Integer, db.ForeignKey('aisle_overrides.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    # Optional relationship back to recipe for showing source
    recipe = db.relationship(
        'Recipe',
        backref=db.backref('shopping_items', lazy='dynamic', cascade='all, delete-orphan'),
        lazy='select'
    )

    aisle_override = db.relationship('AisleOverride', lazy='joined')

    def to_dict(self):
        """Convert shopping item to dictionary representation."""
        return {
            'id': self.id,
            'name': self.name,
            'recipe_id': self.recipe_id,
            'recipe_title': self.recipe.title if self.recipe else None,
            'purchased': self.purchased,
            'aisle_override_id': self.aisle_override_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<ShoppingItem {self.name}>'


class MealPlan(db.Model):
    """Meal plan entry mapping a meal type to a recipe on a specific date.

    Attributes:
        id: Unique identifier
        date: The date for this meal
        meal_type: Type of meal (breakfast, lunch, dinner, snack)
        recipe_id: FK to the planned recipe (optional)
        notes: Free-text notes
        created_at / updated_at: Timestamps
    """
    __tablename__ = 'meal_plans'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    meal_type = db.Column(db.String(20), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipes.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    recipe = db.relationship('Recipe', back_populates='meal_plans')

    __table_args__ = (
        db.UniqueConstraint('date', 'meal_type', name='uix_date_meal_type'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'meal_type': self.meal_type,
            'recipe_id': self.recipe_id,
            'recipe_title': self.recipe.title if self.recipe else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<MealPlan {self.date} {self.meal_type}>'


def seed_default_store():
    """Create the 'Default' store with standard aisles if it doesn't exist."""
    if not Store.query.filter_by(name='Default').first():
        store = Store(name='Default')
        db.session.add(store)
        db.session.flush()
        for i, aisle_name in enumerate(DEFAULT_AISLES):
            aisle = StoreAisle(store_id=store.id, name=aisle_name, sort_order=i)
            db.session.add(aisle)
        db.session.commit()
