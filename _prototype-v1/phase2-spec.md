# Kitchen Companion - Phase 2 Feature Specification

## Overview
Transition the 'Kitchen Companion' from a simple recipe viewer into a comprehensive meal-management system focused on efficiency, budget, and weight loss.

## Feature 1: The 'Aisle-Aware' Shopping List 🛒
**Goal:** Reduce shopping time and friction by organizing ingredients by store layout.
- **Logic:** Implement a mapping system that categorizes ingredients (e.g., "Spinach" -> Produce, "Chicken Breast" -> Meat/Poultry, "Brown Rice" -> Grains/Pantry).
- **UI Update:** A 'Generate Shopping List' view that groups items by category rather than by recipe.
- **Value:** Prevents backtracking in the store and makes it easier to spot missing staples.

## Feature 2: The 'Master Prep' Workflow 🕒
**Goal:** Minimize time spent in the kitchen by optimizing the cooking sequence.
- **Logic:** An algorithm that analyzes the steps of all selected weekly recipes and identifies 'parallelizable' tasks.
- **The Workflow:**
  - **Stage 1: Long-Boil/Roast** (Start grains, legumes, and oven-roasted veg first).
  - **Stage 2: The Chop** (Process all vegetables while the bases simmer).
  - **Stage 3: The Sear** (High-heat protein cooking at the end to keep them fresh).
  - **Stage 4: Assembly** (Combining bases, proteins, and pivots).
- **UI Update:** A 'Prep Mode' that presents a consolidated checklist of tasks instead of individual recipes.

## Feature 3: The Satiety & Taste Tracker 📉
**Goal:** Use biological feedback to optimize future recipe selections.
- **Logic:** A simple post-meal rating system.
- **Metrics:** 
  - **Taste:** (1-5 stars) - Do I actually like this?
  - **Satiety:** (1-5 stars) - Did this keep me full until dinner?
- **Data Loop:** Store these ratings in the JSON (or future SQLite) database.
- **Value:** I can eventually analyze this data to suggest "High Satiety" recipes when you're feeling extra hungry, or "High Taste" recipes for a treat.

## Technical Roadmap
- [ ] Update `database.json` schema to include category tags for ingredients.
- [ ] Implement `ShoppingList` module in `script.js`.
- [ ] Develop the `PrepWorkflow` sequencer.
- [ ] Add `UserRatings` object to the database and a UI feedback form.
- [ ] **Migration Target:** Transition from `database.json` to `SQLite` once the library exceeds 50 recipes.
