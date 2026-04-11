"""Database models for Kitchen Companion."""
from datetime import datetime
from sqlalchemy import CheckConstraint
from app import db


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
    title = db.Column(db.String(255), nullable=False)
    source_url = db.Column(db.String(500), nullable=True)
    image_url = db.Column(db.String(1000), nullable=True)
    image_path = db.Column(db.String(500), nullable=True)
    ingredients = db.Column(db.Text, nullable=True)
    instructions = db.Column(db.Text, nullable=False)
    cooking_time = db.Column(db.Integer, nullable=True)  # minutes
    prep_time = db.Column(db.Integer, nullable=True)  # minutes
    servings = db.Column(db.Integer, nullable=True)
    difficulty = db.Column(db.String(20), default='medium')  # easy, medium, hard
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    name = db.Column(db.String(100), nullable=False)
    tag_type = db.Column(db.String(50), nullable=False, default='custom')
    
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
        
        # Create new tag
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
