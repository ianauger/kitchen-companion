#!/bin/bash
# Fix missing images for recipes 1 and 9

API_URL="http://localhost:5001/api/recipes"

# Recipe 1 - Thai Basil Chicken - Update with a working image URL
curl -s -X PUT "$API_URL/1" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=800&q=80"
  }'

echo ""

# Recipe 9 - Thai Red Curry Pork - Update with a working image URL
curl -s -X PUT "$API_URL/9" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://images.unsplash.com/photo-1455619452474-d2be8b1e70cd?w=800&q=80"
  }'

echo ""
echo "Done fixing images!"
