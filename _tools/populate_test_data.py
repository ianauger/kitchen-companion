#!/usr/bin/env python3
"""
Populate Kitchen Companion database with ~20 diverse test recipes.

This script uses the existing SQLAlchemy models and image_utils download pipeline
to add test data with proper image handling.
"""
import sys
import os

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Recipe, Tag, Note
from app.image_utils import download_image


# Test recipes data - diverse cuisines, difficulties, and times
TEST_RECIPES = [
    # Italian
    {
        "title": "Classic Margherita Pizza",
        "instructions": "1. Make dough: mix flour, yeast, salt, water. Knead 10 min.\n2. Let rise 1 hour.\n3. Preheat oven to 500°F with pizza stone.\n4. Stretch dough into 12\" round.\n5. Top with San Marzano tomatoes, fresh mozzarella, basil.\n6. Bake 8-10 min until charred edges.\n7. Drizzle with olive oil.",
        "ingredients": "2 cups flour\n1 tsp yeast\n1/2 tsp salt\n3/4 cup water\n1/2 cup San Marzano tomatoes\n8 oz fresh mozzarella\nFresh basil leaves\nOlive oil",
        "cooking_time": 10,
        "prep_time": 90,
        "servings": 2,
        "difficulty": "medium",
        "source_url": "https://www.seriouseats.com/best-margherita-pizza-recipe",
        "image_url": "https://images.unsplash.com/photo-1574071318508-1cdbab00d974?w=800&q=80",
        "tags": [{"name": "Italian", "tag_type": "cuisine"}, {"name": "Vegetarian", "tag_type": "custom"}, {"name": "Mild", "tag_type": "spice_level"}, {"name": "Comfort Food", "tag_type": "custom"}],
        "notes": ["Best with fresh buffalo mozzarella", "Let dough rest at room temp for 2 hours for best results"]
    },
    {
        "title": "Creamy Carbonara",
        "instructions": "1. Cook spaghetti in salted water until al dente.\n2. Cook guanciale in pan until crispy.\n3. Whisk eggs, yolks, pecorino, black pepper.\n4. Drain pasta, reserve pasta water.\n5. Toss hot pasta with guanciale and fat.\n6. Remove from heat, add egg mixture.\n7. Toss vigorously, add pasta water if needed.\n8. Serve immediately with more pecorino.",
        "ingredients": "1 lb spaghetti\n8 oz guanciale or pancetta\n4 egg yolks + 2 whole eggs\n1 cup pecorino romano\nBlack pepper",
        "cooking_time": 15,
        "prep_time": 10,
        "servings": 4,
        "difficulty": "medium",
        "source_url": "https://www.seriouseats.com/recipes/2016/02/pasta-carbonara-sauce-recipe.html",
        "image_url": "https://images.unsplash.com/photo-1612874742237-652038e09a63?w=800&q=80",
        "tags": [{"name": "Italian", "tag_type": "cuisine"}, {"name": "Pork", "tag_type": "protein"}, {"name": "Mild", "tag_type": "spice_level"}, {"name": "Quick", "tag_type": "custom"}]
    },
    # Indian
    {
        "title": "Butter Chicken (Murgh Makhani)",
        "instructions": "1. Marinate chicken in yogurt, ginger-garlic paste, and spices for 1 hour.\n2. Roast chicken at 400°F for 20 min until charred.\n3. Make sauce: sauté onions, tomatoes, cashews, and spices.\n4. Blend until smooth, return to pan.\n5. Add cream and butter, simmer gently.\n6. Add roasted chicken, simmer 10 min.\n7. Serve with naan and rice.",
        "ingredients": "2 lbs chicken thighs\n1 cup yogurt\n2 tbsp ginger-garlic paste\n1 can tomato puree\n1 cup heavy cream\n4 tbsp butter\n1/2 cup cashews\nGaram masala, cumin, coriander",
        "cooking_time": 50,
        "prep_time": 90,
        "servings": 4,
        "difficulty": "medium",
        "source_url": "https://ministryofcurry.com/butter-chicken/",
        "image_url": "https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=800&q=80",
        "tags": [{"name": "Indian", "tag_type": "cuisine"}, {"name": "Chicken", "tag_type": "protein"}, {"name": "Medium", "tag_type": "spice_level"}, {"name": "Comfort Food", "tag_type": "custom"}],
        "notes": ["Marinate overnight for best flavor", "Adjust spice level with more or less chili"]
    },
    {
        "title": "Chana Masala",
        "instructions": "1. Soak chickpeas overnight, cook until tender.\n2. Heat oil, add cumin seeds until they sizzle.\n3. Add onions, cook until golden.\n4. Add ginger-garlic paste, cook 2 min.\n5. Add tomatoes, spices, cook until oil separates.\n6. Add chickpeas, simmer 20 min.\n7. Mash some chickpeas for thick sauce.\n8. Garnish with cilantro, serve with rice.",
        "ingredients": "2 cans chickpeas\n2 onions\n2 tomatoes\n1 tbsp ginger-garlic paste\nCumin, coriander, turmeric, garam masala\nCilantro",
        "cooking_time": 30,
        "prep_time": 15,
        "servings": 4,
        "difficulty": "easy",
        "source_url": "https://www.indianhealthyrecipes.com/chana-masala/",
        "image_url": "https://images.unsplash.com/photo-1596797038530-2c107229654b?w=800&q=80",
        "tags": [{"name": "Indian", "tag_type": "cuisine"}, {"name": "Vegetarian", "tag_type": "custom"}, {"name": "Medium", "tag_type": "spice_level"}, {"name": "Healthy", "tag_type": "custom"}]
    },
    # Chinese
    {
        "title": "Kung Pao Chicken",
        "instructions": "1. Cut chicken into 1-inch cubes.\n2. Marinate in soy sauce, cornstarch, and rice wine.\n3. Make sauce: soy sauce, vinegar, sugar, stock.\n4. Heat wok until smoking, add oil.\n5. Stir-fry chicken until golden, remove.\n6. Fry dried chilies and Sichuan peppercorns.\n7. Add garlic, ginger, green onions.\n8. Return chicken, add sauce.\n9. Toss with peanuts, serve with rice.",
        "ingredients": "1 lb chicken breast\n1/4 cup soy sauce\n2 tbsp rice wine\n1 tbsp cornstarch\nDried red chilies\nSichuan peppercorns\nPeanuts\nGreen onions",
        "cooking_time": 15,
        "prep_time": 20,
        "servings": 4,
        "difficulty": "medium",
        "source_url": "https://www.seriouseats.com/recipes/2017/03/kung-pao-chicken.html",
        "image_url": "https://images.unsplash.com/photo-1525755662778-989d0524087d?w=800&q=80",
        "tags": [{"name": "Chinese", "tag_type": "cuisine"}, {"name": "Chicken", "tag_type": "protein"}, {"name": "Spicy", "tag_type": "spice_level"}, {"name": "Quick", "tag_type": "custom"}],
        "notes": ["Use toasted peanuts for more flavor"]
    },
    {
        "title": "Mapo Tofu",
        "instructions": "1. Cut tofu into 1-inch cubes.\n2. Brown ground pork in wok.\n3. Add doubanjiang, fermented black beans.\n4. Add stock, bring to simmer.\n5. Gently add tofu cubes.\n6. Simmer 5 min, add Sichuan peppercorns.\n7. Thicken with cornstarch slurry.\n8. Garnish with green onions.",
        "ingredients": "14 oz soft tofu\n4 oz ground pork\n2 tbsp doubanjiang\n1 tbsp fermented black beans\n2 tbsp Sichuan peppercorns\n2 cups chicken stock\nCornstarch",
        "cooking_time": 15,
        "prep_time": 10,
        "servings": 4,
        "difficulty": "medium",
        "source_url": "https://www.seriouseats.com/recipes/2017/04/mapo-tofu-sichuan.html",
        "image_url": "https://images.unsplash.com/photo-1582576163090-09d3b6f8a969?w=800&q=80",
        "tags": [{"name": "Chinese", "tag_type": "cuisine"}, {"name": "Pork", "tag_type": "protein"}, {"name": "Spicy", "tag_type": "spice_level"}]
    },
    # Japanese
    {
        "title": "Chicken Teriyaki",
        "instructions": "1. Pat chicken thighs dry, season with salt.\n2. Pan-sear skin-side down until golden (5 min).\n3. Flip and cook 3 min more.\n4. Remove chicken, pour off excess fat.\n5. Make sauce: soy sauce, mirin, sake, sugar. Simmer until syrupy.\n6. Return chicken to pan, coat with glaze.\n7. Slice and serve with steamed rice and broccoli.",
        "ingredients": "4 chicken thighs\n1/4 cup soy sauce\n2 tbsp mirin\n2 tbsp sake\n1 tbsp sugar\nSesame seeds\nGreen onions",
        "cooking_time": 25,
        "prep_time": 10,
        "servings": 4,
        "difficulty": "easy",
        "source_url": "https://www.justonecookbook.com/chicken-teriyaki/",
        "image_url": "https://images.unsplash.com/photo-1553621042-f6e147245754?w=800&q=80",
        "tags": [{"name": "Japanese", "tag_type": "cuisine"}, {"name": "Chicken", "tag_type": "protein"}, {"name": "Mild", "tag_type": "spice_level"}, {"name": "Quick", "tag_type": "custom"}]
    },
    {
        "title": "Tonkotsu Ramen",
        "instructions": "1. Blanch pork bones, drain, scrub clean.\n2. Simmer bones 12+ hours until broth is milky white.\n3. Make chashu: braise pork belly in soy sauce, sake, sugar.\n4. Prepare soft-boiled eggs (6 min), marinate.\n5. Cook noodles according to package.\n6. Assemble: broth, noodles, sliced chashu, egg, nori, green onions.\n7. Add sesame seeds, garlic oil.",
        "ingredients": "Pork bones\nPork belly\nRamen noodles\nSoft-boiled eggs\nNori\nGreen onions\nSoy sauce, mirin, sake\nSesame oil",
        "cooking_time": 780,
        "prep_time": 60,
        "servings": 4,
        "difficulty": "hard",
        "source_url": "https://www.seriouseats.com/recipes/tonkotsu-ramen",
        "image_url": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?w=800&q=80",
        "tags": [{"name": "Japanese", "tag_type": "cuisine"}, {"name": "Pork", "tag_type": "protein"}, {"name": "Mild", "tag_type": "spice_level"}, {"name": "Comfort Food", "tag_type": "custom"}],
        "notes": ["Can use pressure cooker to reduce broth time to 2 hours", "Make chashu the day before for easier slicing"]
    },
    # Mexican
    {
        "title": "Carnitas Tacos",
        "instructions": "1. Cut pork shoulder into 2-inch chunks.\n2. Season with salt, cumin, oregano, garlic.\n3. Place in Dutch oven with orange juice, lime juice, bay leaves.\n4. Cover and braise at 325°F for 3 hours.\n5. Shred meat with forks.\n6. Spread on baking sheet, broil until crispy.\n7. Serve on warm corn tortillas with cilantro, onion, salsa verde.",
        "ingredients": "3 lbs pork shoulder\n1 cup orange juice\n1/2 cup lime juice\n4 bay leaves\nCumin, oregano, garlic\nCorn tortillas\nCilantro, onion, salsa verde",
        "cooking_time": 180,
        "prep_time": 20,
        "servings": 8,
        "difficulty": "medium",
        "source_url": "https://www.mexicoinmykitchen.com/pork-carnitas/",
        "image_url": "https://images.unsplash.com/photo-1551504734-5ee1c4a1479b?w=800&q=80",
        "tags": [{"name": "Mexican", "tag_type": "cuisine"}, {"name": "Pork", "tag_type": "protein"}, {"name": "Mild", "tag_type": "spice_level"}, {"name": "Comfort Food", "tag_type": "custom"}],
        "notes": ["Leftover carnitas freeze well for up to 3 months"]
    },
    {
        "title": "Beef Barbacoa",
        "instructions": "1. Blend chipotles, vinegar, lime juice, garlic, and spices into paste.\n2. Rub all over beef chuck roast.\n3. Place in slow cooker with bay leaves and broth.\n4. Cook on low 8 hours until falling apart.\n5. Shred meat with two forks.\n6. Serve in tacos with cilantro, onion, and salsa.",
        "ingredients": "3 lbs beef chuck\n4 chipotle peppers\n1/2 cup apple cider vinegar\n1/4 cup lime juice\nGarlic, cumin, oregano\nBay leaves\nCorn tortillas",
        "cooking_time": 480,
        "prep_time": 20,
        "servings": 8,
        "difficulty": "easy",
        "source_url": "https://www.isabeleats.com/barbacoa-beef-recipe/",
        "image_url": "https://images.unsplash.com/photo-1599974579688-8dbdd335c77f?w=800&q=80",
        "tags": [{"name": "Mexican", "tag_type": "cuisine"}, {"name": "Beef", "tag_type": "protein"}, {"name": "Spicy", "tag_type": "spice_level"}]
    },
    # Thai
    {
        "title": "Pad Thai",
        "instructions": "1. Soak rice noodles in warm water 30 min.\n2. Make sauce: tamarind paste, fish sauce, palm sugar.\n3. Heat wok, scramble eggs, set aside.\n4. Stir-fry shrimp until pink.\n5. Add noodles and sauce, toss well.\n6. Add eggs, bean sprouts, green onions.\n7. Serve with lime wedges, peanuts, chili flakes.",
        "ingredients": "8 oz rice noodles\n1/2 lb shrimp\n2 eggs\n1/2 cup bean sprouts\n3 tbsp fish sauce\n2 tbsp tamarind paste\n1 tbsp palm sugar\nPeanuts\nGreen onions",
        "cooking_time": 15,
        "prep_time": 35,
        "servings": 4,
        "difficulty": "medium",
        "source_url": "https://hot-thai-kitchen.com/pad-thai/",
        "image_url": "https://images.unsplash.com/photo-1559314809-26d320e60514?w=800&q=80",
        "tags": [{"name": "Thai", "tag_type": "cuisine"}, {"name": "Shrimp", "tag_type": "protein"}, {"name": "Mild", "tag_type": "spice_level"}, {"name": "Quick", "tag_type": "custom"}]
    },
    {
        "title": "Thai Basil Chicken Stir-Fry",
        "instructions": "1. Heat oil in wok until smoking.\n2. Add garlic and Thai chilies, stir-fry 30 seconds.\n3. Add ground chicken, cook until no longer pink (4-5 min).\n4. Add bell peppers and onions, stir-fry 2 min.\n5. Pour in soy sauce, oyster sauce, fish sauce, sugar.\n6. Fold in Thai basil, cook 30 seconds.\n7. Serve over jasmine rice.",
        "ingredients": "1 lb ground chicken\n4 cloves garlic\n4 Thai chilies\n1 red bell pepper\n1/2 onion\n2 tbsp soy sauce\n1 tbsp oyster sauce\n1 tbsp fish sauce\n1 tsp sugar\nThai basil leaves",
        "cooking_time": 15,
        "prep_time": 10,
        "servings": 4,
        "difficulty": "easy",
        "source_url": "https://hot-thai-kitchen.com/basil-chicken/",
        "image_url": "https://images.unsplash.com/photo-1603133872878-684f7fb21c1e?w=800&q=80",
        "tags": [{"name": "Thai", "tag_type": "cuisine"}, {"name": "Chicken", "tag_type": "protein"}, {"name": "Spicy", "tag_type": "spice_level"}, {"name": "Quick", "tag_type": "custom"}],
        "notes": ["Adjust Thai chilies to your spice tolerance", "Holy basil is traditional but sweet basil works too"]
    },
    # Korean
    {
        "title": "Korean Beef Bulgogi",
        "instructions": "1. Slice beef thinly against the grain.\n2. Make marinade: soy sauce, brown sugar, sesame oil, garlic, ginger, pear juice.\n3. Marinate beef at least 30 min (overnight is better).\n4. Heat grill pan over high heat.\n5. Cook beef in batches, 2-3 min per side until caramelized.\n6. Serve over rice with kimchi and pickled vegetables.",
        "ingredients": "2 lbs ribeye or sirloin\n1/2 cup soy sauce\n2 tbsp brown sugar\n1 tbsp sesame oil\n4 cloves garlic\n1-inch ginger\n1/4 cup Asian pear juice\nGreen onions\nSesame seeds",
        "cooking_time": 20,
        "prep_time": 40,
        "servings": 4,
        "difficulty": "medium",
        "source_url": "https://www.maangchi.com/recipe/bulgogi",
        "image_url": "https://images.unsplash.com/photo-1590301157890-4810ed352733?w=800&q=80",
        "tags": [{"name": "Korean", "tag_type": "cuisine"}, {"name": "Beef", "tag_type": "protein"}, {"name": "Mild", "tag_type": "spice_level"}, {"name": "Comfort Food", "tag_type": "custom"}]
    },
    {
        "title": "Kimchi Jjigae",
        "instructions": "1. Cut pork belly into bite-sized pieces.\n2. Sauté pork until lightly browned.\n3. Add old (fermented) kimchi, cook 3 min.\n4. Add kimchi juice, stock, and gochugaru.\n5. Simmer 15-20 min until pork is tender.\n6. Add tofu and green onions.\n7. Serve bubbling hot with rice.",
        "ingredients": "1 lb pork belly\n2 cups fermented kimchi\n1/2 cup kimchi juice\n2 cups pork or anchovy stock\n1 tbsp gochugaru\nFirm tofu\nGreen onions",
        "cooking_time": 25,
        "prep_time": 10,
        "servings": 4,
        "difficulty": "easy",
        "source_url": "https://www.maangchi.com/recipe/kimchi-jjigae",
        "image_url": "https://images.unsplash.com/photo-1498654896293-37aacf113fd9?w=800&q=80",
        "tags": [{"name": "Korean", "tag_type": "cuisine"}, {"name": "Pork", "tag_type": "protein"}, {"name": "Medium", "tag_type": "spice_level"}, {"name": "Comfort Food", "tag_type": "custom"}],
        "notes": ["Old/fermented kimchi is essential for authentic flavor"]
    },
    # Mediterranean
    {
        "title": "Greek Chicken Souvlaki",
        "instructions": "1. Cut chicken breast into 1-inch cubes.\n2. Whisk marinade: olive oil, lemon juice, garlic, oregano, thyme.\n3. Marinate chicken 2-4 hours.\n4. Thread onto skewers with bell peppers and red onion.\n5. Grill over medium-high heat, 4-5 min per side.\n6. Serve with tzatziki and warm pita bread.",
        "ingredients": "2 lbs chicken breast\n1/4 cup olive oil\n1/4 cup lemon juice\n4 cloves garlic\n1 tbsp oregano\n1 tbsp thyme\nBell peppers, red onion\nPita bread\nTzatziki sauce",
        "cooking_time": 15,
        "prep_time": 30,
        "servings": 4,
        "difficulty": "easy",
        "source_url": "https://www.themediterraneandish.com/chicken-souvlaki/",
        "image_url": "https://images.unsplash.com/photo-1529193591184-b1d58069ecdd?w=800&q=80",
        "tags": [{"name": "Mediterranean", "tag_type": "cuisine"}, {"name": "Chicken", "tag_type": "protein"}, {"name": "Mild", "tag_type": "spice_level"}, {"name": "Healthy", "tag_type": "custom"}]
    },
    {
        "title": "Hummus and Falafel Platter",
        "instructions": "1. Soak dried chickpeas overnight.\n2. Blend chickpeas, herbs, spices for falafel.\n3. Rest mixture 30 min, form into balls.\n4. Deep fry at 350°F until golden brown.\n5. Make hummus: blend chickpeas, tahini, lemon, garlic.\n6. Serve with pita, pickled vegetables, and tahini sauce.",
        "ingredients": "2 cups dried chickpeas\nFresh parsley, cilantro\nCumin, coriander, garlic\nTahini\nLemon juice\nOlive oil\nPita bread",
        "cooking_time": 20,
        "prep_time": 720,
        "servings": 6,
        "difficulty": "medium",
        "source_url": "https://www.themediterraneandish.com/falafel/",
        "image_url": "https://images.unsplash.com/photo-1547496502-affa22d38842?w=800&q=80",
        "tags": [{"name": "Mediterranean", "tag_type": "cuisine"}, {"name": "Vegetarian", "tag_type": "custom"}, {"name": "Mild", "tag_type": "spice_level"}, {"name": "Healthy", "tag_type": "custom"}]
    },
    # Vietnamese
    {
        "title": "Beef Pho",
        "instructions": "1. Char ginger and onion over open flame.\n2. Toast spices: star anise, cinnamon, cloves, cardamom.\n3. Simmer beef bones with charred aromatics 3 hours.\n4. Strain broth, season with fish sauce and sugar.\n5. Cook rice noodles according to package.\n6. Assemble: noodles, thinly sliced raw beef, hot broth.\n7. Garnish with herbs, lime, bean sprouts, jalapeño.",
        "ingredients": "3 lbs beef bones\n1 lb beef sirloin\nStar anise, cinnamon, cloves\nGinger, onion\nFish sauce, sugar\nRice noodles\nThai basil, cilantro, lime",
        "cooking_time": 200,
        "prep_time": 30,
        "servings": 6,
        "difficulty": "hard",
        "source_url": "https://www.seriouseats.com/recipes/2012/09/vietnamese-beef-noodle-soup-pho.html",
        "image_url": "https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=800&q=80",
        "tags": [{"name": "Vietnamese", "tag_type": "cuisine"}, {"name": "Beef", "tag_type": "protein"}, {"name": "Mild", "tag_type": "spice_level"}, {"name": "Comfort Food", "tag_type": "custom"}],
        "notes": ["Freeze beef for 15 min before slicing for paper-thin cuts"]
    },
    # American Comfort
    {
        "title": "Classic Beef Burger",
        "instructions": "1. Form ground beef into patties, season generously with salt and pepper.\n2. Make a small indent in center of each patty.\n3. Heat cast iron skillet until smoking hot.\n4. Cook patties 4 min per side for medium.\n5. Add cheese slice in last minute, cover to melt.\n6. Toast buns lightly.\n7. Assemble with lettuce, tomato, onion, pickles, condiments.",
        "ingredients": "2 lbs ground beef (80/20)\n4 slices cheddar cheese\n4 brioche buns\nLettuce, tomato, onion\nPickles\nKetchup, mustard, mayo",
        "cooking_time": 15,
        "prep_time": 10,
        "servings": 4,
        "difficulty": "easy",
        "source_url": "https://www.seriouseats.com/the-food-lab-best-burgers",
        "image_url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=800&q=80",
        "tags": [{"name": "American", "tag_type": "cuisine"}, {"name": "Beef", "tag_type": "protein"}, {"name": "Mild", "tag_type": "spice_level"}, {"name": "Comfort Food", "tag_type": "custom"}],
        "notes": ["Don't press down on the patties while cooking!"]
    },
    {
        "title": "Macaroni and Cheese",
        "instructions": "1. Cook macaroni until al dente, drain.\n2. Make roux: melt butter, whisk in flour 1 min.\n3. Slowly whisk in milk, simmer until thickened.\n4. Remove from heat, stir in cheeses until melted.\n5. Add cooked pasta, season with salt and pepper.\n6. Optional: top with breadcrumbs, bake at 375°F 20 min.\n7. Let rest 5 min before serving.",
        "ingredients": "1 lb elbow macaroni\n4 tbsp butter\n4 tbsp flour\n3 cups milk\n3 cups sharp cheddar\n1 cup gruyère\nSalt, pepper, nutmeg",
        "cooking_time": 25,
        "prep_time": 10,
        "servings": 6,
        "difficulty": "easy",
        "source_url": "https://www.seriouseats.com/recipes/2015/10/best-stovetop-mac-and-cheese.html",
        "image_url": "https://images.unsplash.com/photo-1543339494-b4cd4f7ba686?w=800&q=80",
        "tags": [{"name": "American", "tag_type": "cuisine"}, {"name": "Vegetarian", "tag_type": "custom"}, {"name": "Mild", "tag_type": "spice_level"}, {"name": "Comfort Food", "tag_type": "custom"}]
    },
    # Quick meals
    {
        "title": "Shrimp Scampi",
        "instructions": "1. Cook linguine until al dente.\n2. Pat shrimp dry, season with salt and pepper.\n3. Sauté shrimp in butter and olive oil until pink.\n4. Add garlic, cook 30 seconds.\n5. Add white wine, lemon juice, red pepper flakes.\n6. Simmer 2 min, add pasta water if needed.\n7. Toss with linguine and parsley.",
        "ingredients": "1 lb large shrimp\n8 oz linguine\n4 tbsp butter\n2 tbsp olive oil\n4 cloves garlic\n1/2 cup white wine\nLemon juice\nRed pepper flakes\nParsley",
        "cooking_time": 10,
        "prep_time": 10,
        "servings": 4,
        "difficulty": "easy",
        "source_url": "https://www.seriouseats.com/shrimp-scampi-recipe",
        "image_url": "https://images.unsplash.com/photo-1563379926898-05f807cc1c74?w=800&q=80",
        "tags": [{"name": "Italian", "tag_type": "cuisine"}, {"name": "Shrimp", "tag_type": "protein"}, {"name": "Mild", "tag_type": "spice_level"}, {"name": "Quick", "tag_type": "custom"}]
    },
    {
        "title": "Chicken Piccata",
        "instructions": "1. Pound chicken breasts to 1/4 inch thickness.\n2. Season with salt, pepper, dredge in flour.\n3. Sauté in olive oil 3 min per side until golden.\n4. Remove chicken, add garlic to pan.\n5. Deglaze with white wine and lemon juice.\n6. Add capers and butter, swirl to combine.\n7. Return chicken, spoon sauce over.\n8. Garnish with parsley.",
        "ingredients": "4 chicken breasts\n1/2 cup flour\n2 tbsp olive oil\n1/2 cup white wine\nLemon juice\n3 tbsp capers\n2 tbsp butter\nParsley",
        "cooking_time": 15,
        "prep_time": 10,
        "servings": 4,
        "difficulty": "easy",
        "source_url": "https://www.seriouseats.com/chicken-piccata-recipe",
        "image_url": "https://images.unsplash.com/photo-1529692243512-3a62a43bd7b9?w=800&q=80",
        "tags": [{"name": "Italian", "tag_type": "cuisine"}, {"name": "Chicken", "tag_type": "protein"}, {"name": "Mild", "tag_type": "spice_level"}, {"name": "Quick", "tag_type": "custom"}, {"name": "Healthy", "tag_type": "custom"}]
    },
]


def populate_database():
    """Populate the database with test recipes."""
    app = create_app()
    
    with app.app_context():
        # Check existing count
        existing = Recipe.query.count()
        print(f"Existing recipes: {existing}")
        
        if existing > 0:
            print("Database already has recipes. Skipping population.")
            return
        
        recipes_added = 0
        tags_created = set()
        notes_added = 0
        
        for recipe_data in TEST_RECIPES:
            print(f"\nAdding: {recipe_data['title']}")
            
            # Extract tags and notes before creating recipe
            tags_data = recipe_data.pop('tags', [])
            notes_data = recipe_data.pop('notes', [])
            
            # Create recipe
            recipe = Recipe(
                title=recipe_data['title'],
                instructions=recipe_data['instructions'],
                ingredients=recipe_data.get('ingredients'),
                source_url=recipe_data.get('source_url'),
                image_url=recipe_data.get('image_url'),
                cooking_time=recipe_data.get('cooking_time'),
                prep_time=recipe_data.get('prep_time'),
                servings=recipe_data.get('servings'),
                difficulty=recipe_data.get('difficulty', 'medium')
            )
            
            # Add tags
            for tag_data in tags_data:
                tag, created = Tag.get_or_create(
                    name=tag_data['name'],
                    tag_type=tag_data.get('tag_type', 'custom')
                )
                if created:
                    tags_created.add(f"{tag.name}:{tag.tag_type}")
                recipe.tags.append(tag)
            
            db.session.add(recipe)
            db.session.flush()  # Get recipe ID
            
            # Download image if URL provided
            image_url = recipe_data.get('image_url')
            if image_url:
                print(f"  Downloading image...")
                relative_path, _ = download_image(image_url, recipe_id=recipe.id)
                if relative_path:
                    recipe.image_path = relative_path
                    print(f"  Image saved: {relative_path}")
                else:
                    print(f"  Image download failed (using remote URL only)")
            
            # Add notes
            for note_content in notes_data:
                note = Note(
                    recipe_id=recipe.id,
                    content=note_content
                )
                db.session.add(note)
                notes_added += 1
            
            recipes_added += 1
        
        # Commit all changes
        db.session.commit()
        
        # Print summary
        print("\n" + "="*50)
        print("DATABASE POPULATION COMPLETE")
        print("="*50)
        print(f"Recipes added: {recipes_added}")
        print(f"Tags in database: {Tag.query.count()}")
        print(f"Notes added: {notes_added}")
        print(f"\nRecipes by difficulty:")
        for diff in ['easy', 'medium', 'hard']:
            count = Recipe.query.filter_by(difficulty=diff).count()
            print(f"  {diff.capitalize()}: {count}")
        
        print(f"\nRecipes by cuisine:")
        cuisines = Tag.query.filter_by(tag_type='cuisine').all()
        for cuisine in cuisines:
            count = cuisine.recipes.count()
            print(f"  {cuisine.name}: {count}")


if __name__ == '__main__':
    populate_database()