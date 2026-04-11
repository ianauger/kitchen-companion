#!/bin/bash
# Seed Kitchen Companion with 10 diverse recipes

API_URL="http://localhost:5001/api/recipes"

curl -s -X POST "$API_URL" -H "Content-Type: application/json" -d '{
  "title": "Thai Basil Chicken Stir-Fry",
  "instructions": "1. Heat oil in a wok over high heat until smoking.\n2. Add garlic and Thai chilies, stir-fry 30 seconds.\n3. Add ground chicken, cook until no longer pink (4-5 min).\n4. Add bell peppers and onions, stir-fry 2 min.\n5. Pour in soy sauce, oyster sauce, fish sauce, and sugar.\n6. Fold in Thai basil, cook 30 seconds.\n7. Serve over jasmine rice.",
  "image_url": "https://images.unsplash.com/photo-1603133872878-684f7fb21c1e?w=800&q=80",
  "source_url": "https://hot-thai-kitchen.com/",
  "cooking_time": 15,
  "prep_time": 10,
  "servings": 4,
  "difficulty": "easy",
  "tags": [
    {"name": "Thai", "tag_type": "cuisine"},
    {"name": "Chicken", "tag_type": "protein"},
    {"name": "Spicy", "tag_type": "spice_level"}
  ]
}'

curl -s -X POST "$API_URL" -H "Content-Type: application/json" -d '{
  "title": "Korean Beef Bulgogi Bowl",
  "instructions": "1. Slice beef thinly against the grain.\n2. Mix marinade: soy sauce, brown sugar, sesame oil, garlic, ginger, and pear juice.\n3. Marinate beef for at least 30 min (or overnight).\n4. Heat a grill pan over high heat.\n5. Cook beef in batches, 2-3 min per side until caramelized.\n6. Serve over rice with kimchi and pickled vegetables.",
  "image_url": "https://images.unsplash.com/photo-1590301157890-4810ed352733?w=800&q=80",
  "source_url": "https://www.maangchi.com/",
  "cooking_time": 20,
  "prep_time": 40,
  "servings": 4,
  "difficulty": "medium",
  "tags": [
    {"name": "Korean", "tag_type": "cuisine"},
    {"name": "Beef", "tag_type": "protein"},
    {"name": "Medium", "tag_type": "spice_level"}
  ]
}'

curl -s -X POST "$API_URL" -H "Content-Type: application/json" -d '{
  "title": "Mexican Carnitas Tacos",
  "instructions": "1. Season pork shoulder with salt, cumin, oregano, and garlic.\n2. Place in Dutch oven with orange juice, lime juice, and beer.\n3. Cover and braise at 325°F for 3 hours until tender.\n4. Shred meat with forks.\n5. Spread on baking sheet and broil until crispy edges form.\n6. Serve on warm corn tortillas with cilantro, onion, and salsa verde.",
  "image_url": "https://images.unsplash.com/photo-1551504734-5ee1c4a1479b?w=800&q=80",
  "source_url": "https://www.mexicoinmykitchen.com/",
  "cooking_time": 180,
  "prep_time": 20,
  "servings": 8,
  "difficulty": "medium",
  "tags": [
    {"name": "Mexican", "tag_type": "cuisine"},
    {"name": "Pork", "tag_type": "protein"},
    {"name": "Mild", "tag_type": "spice_level"}
  ]
}'

curl -s -X POST "$API_URL" -H "Content-Type: application/json" -d '{
  "title": "Mediterranean Chicken Souvlaki",
  "instructions": "1. Cut chicken breast into 1-inch cubes.\n2. Whisk marinade: olive oil, lemon juice, garlic, oregano, and thyme.\n3. Marinate chicken 2-4 hours.\n4. Thread onto skewers with bell peppers and red onion.\n5. Grill over medium-high heat, 4-5 min per side until charred.\n6. Serve with tzatziki and warm pita bread.",
  "image_url": "https://images.unsplash.com/photo-1529193591184-b1d58069ecdd?w=800&q=80",
  "source_url": "https://www.themediterraneandish.com/",
  "cooking_time": 15,
  "prep_time": 30,
  "servings": 4,
  "difficulty": "easy",
  "tags": [
    {"name": "Mediterranean", "tag_type": "cuisine"},
    {"name": "Chicken", "tag_type": "protein"},
    {"name": "Mild", "tag_type": "spice_level"}
  ]
}'

curl -s -X POST "$API_URL" -H "Content-Type: application/json" -d '{
  "title": "Japanese Chicken Teriyaki",
  "instructions": "1. Pat chicken thighs dry and season with salt.\n2. Pan-sear skin-side down until golden (5 min).\n3. Flip and cook 3 min more.\n4. Remove chicken, pour off excess fat.\n5. Make sauce: soy sauce, mirin, sake, sugar. Simmer until syrupy.\n6. Return chicken to pan, coat with glaze.\n7. Slice and serve with steamed rice and broccoli.",
  "image_url": "https://images.unsplash.com/photo-1553621042-f6e147245754?w=800&q=80",
  "source_url": "https://www.justonecookbook.com/",
  "cooking_time": 25,
  "prep_time": 10,
  "servings": 4,
  "difficulty": "easy",
  "tags": [
    {"name": "Japanese", "tag_type": "cuisine"},
    {"name": "Chicken", "tag_type": "protein"},
    {"name": "Mild", "tag_type": "spice_level"}
  ]
}'

curl -s -X POST "$API_URL" -H "Content-Type: application/json" -d '{
  "title": "Indian Butter Chicken",
  "instructions": "1. Marinate chicken in yogurt, ginger-garlic paste, and spices for 1 hour.\n2. Roast chicken at 400°F for 20 min until charred.\n3. Make sauce: sauté onions, tomatoes, cashews, and spices.\n4. Blend until smooth, return to pan.\n5. Add cream and butter, simmer gently.\n6. Add roasted chicken, simmer 10 min.\n7. Serve with naan and rice.",
  "image_url": "https://images.unsplash.com/photo-1585937421612-70a008356fbe?w=800&q=80",
  "source_url": "https://ministryofcurry.com/",
  "cooking_time": 50,
  "prep_time": 90,
  "servings": 4,
  "difficulty": "medium",
  "tags": [
    {"name": "Indian", "tag_type": "cuisine"},
    {"name": "Chicken", "tag_type": "protein"},
    {"name": "Medium", "tag_type": "spice_level"}
  ]
}'

curl -s -X POST "$API_URL" -H "Content-Type: application/json" -d '{
  "title": "Vietnamese Beef Pho",
  "instructions": "1. Char ginger and onion over open flame.\n2. Toast spices: star anise, cinnamon, cloves, cardamom.\n3. Simmer beef bones with charred aromatics and spices for 3 hours.\n4. Strain broth, season with fish sauce and sugar.\n5. Cook rice noodles according to package.\n6. Assemble: noodles, thinly sliced raw beef, hot broth.\n7. Garnish with herbs, lime, bean sprouts, jalapeño.",
  "image_url": "https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=800&q=80",
  "source_url": "https://www.seriouseats.com/",
  "cooking_time": 200,
  "prep_time": 30,
  "servings": 6,
  "difficulty": "hard",
  "tags": [
    {"name": "Vietnamese", "tag_type": "cuisine"},
    {"name": "Beef", "tag_type": "protein"},
    {"name": "Mild", "tag_type": "spice_level"}
  ]
}'

curl -s -X POST "$API_URL" -H "Content-Type: application/json" -d '{
  "title": "Mexican Beef Barbacoa",
  "instructions": "1. Blend chipotles, vinegar, lime juice, garlic, and spices into a paste.\n2. Rub all over beef chuck roast.\n3. Place in slow cooker with bay leaves and broth.\n4. Cook on low 8 hours until falling apart.\n5. Shred meat with two forks.\n6. Serve in tacos with cilantro, onion, and salsa.",
  "image_url": "https://images.unsplash.com/photo-1551504734-5ee1c4a1479b?w=800&q=80",
  "source_url": "https://www.isabeleats.com/",
  "cooking_time": 480,
  "prep_time": 20,
  "servings": 8,
  "difficulty": "easy",
  "tags": [
    {"name": "Mexican", "tag_type": "cuisine"},
    {"name": "Beef", "tag_type": "protein"},
    {"name": "Spicy", "tag_type": "spice_level"}
  ]
}'

curl -s -X POST "$API_URL" -H "Content-Type: application/json" -d '{
  "title": "Thai Red Curry Pork",
  "instructions": "1. Cut pork shoulder into bite-sized cubes.\n2. Heat coconut cream in a pot until it separates.\n3. Fry red curry paste for 2 min until fragrant.\n4. Add pork, brown on all sides.\n5. Add coconut milk, fish sauce, palm sugar, kaffir lime leaves.\n6. Simmer 45 min until pork is tender.\n7. Add Thai basil and bell peppers. Serve with jasmine rice.",
  "image_url": "https://images.unsplash.com/photo-1626804475297-411dbeefeeab?w=800&q=80",
  "source_url": "https://hot-thai-kitchen.com/",
  "cooking_time": 60,
  "prep_time": 20,
  "servings": 4,
  "difficulty": "medium",
  "tags": [
    {"name": "Thai", "tag_type": "cuisine"},
    {"name": "Pork", "tag_type": "protein"},
    {"name": "Spicy", "tag_type": "spice_level"}
  ]
}'

curl -s -X POST "$API_URL" -H "Content-Type: application/json" -d '{
  "title": "Greek Pork Gyros",
  "instructions": "1. Combine yogurt marinade with lemon, oregano, garlic, and olive oil.\n2. Marinate pork tenderloin overnight.\n3. Roast at 400°F for 25 min until internal temp reaches 145°F.\n4. Rest 10 min, slice thin.\n5. Warm pita bread.\n6. Assemble with sliced pork, tomatoes, onions, and tzatziki sauce.",
  "image_url": "https://images.unsplash.com/photo-1547592180-85f173990554?w=800&q=80",
  "source_url": "https://www.themediterraneandish.com/",
  "cooking_time": 35,
  "prep_time": 720,
  "servings": 6,
  "difficulty": "medium",
  "tags": [
    {"name": "Mediterranean", "tag_type": "cuisine"},
    {"name": "Pork", "tag_type": "protein"},
    {"name": "Mild", "tag_type": "spice_level"}
  ]
}'

echo "Done seeding recipes!"