// Kitchen Companion - Pure JavaScript
// Fetches and parses the recipe database

let recipes = [];
let currentRecipe = null;
let currentStep = 0;
let selectedMeals = new Set();

// Initialize the app
async function init() {
    try {
        const response = await fetch('/recipes/database.json');
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (!data || !Array.isArray(data.recipes)) {
            throw new Error('Invalid database format: missing recipes array');
        }
        
        recipes = data.recipes;
        
        populateFilters();
        renderRecipeGrid(recipes.map((recipe, index) => ({ recipe, originalIndex: index })));
        populateWeekSelection();
        
        console.log(`Loaded ${recipes.length} recipes`);
    } catch (error) {
        console.error('Failed to load recipes:', error);
        const errorMessage = error.message.includes('HTTP') 
            ? `Server error: ${error.message}. Please ensure the server is running.`
            : 'Failed to load recipe database. Please ensure database.json exists and is valid.';
        alert(errorMessage);
    }
}

// Populate filter dropdowns
function populateFilters() {
    const bases = [...new Set(recipes.map(r => r.base))];
    const proteins = [...new Set(recipes.map(r => r.protein))];
    const pivots = [...new Set(recipes.map(r => r.pivot))];
    
    const baseFilter = document.getElementById('base-filter');
    const proteinFilter = document.getElementById('protein-filter');
    const pivotFilter = document.getElementById('pivot-filter');
    
    bases.forEach(base => {
        const option = document.createElement('option');
        option.value = base;
        option.textContent = base;
        baseFilter.appendChild(option);
    });
    
    proteins.forEach(protein => {
        const option = document.createElement('option');
        option.value = protein;
        option.textContent = protein;
        proteinFilter.appendChild(option);
    });
    
    pivots.forEach(pivot => {
        const option = document.createElement('option');
        option.value = pivot;
        option.textContent = pivot;
        pivotFilter.appendChild(option);
    });
    
    // Add filter listeners
    baseFilter.addEventListener('change', applyFilters);
    proteinFilter.addEventListener('change', applyFilters);
    pivotFilter.addEventListener('change', applyFilters);
}

// Apply filters to recipe grid
function applyFilters() {
    const baseFilter = document.getElementById('base-filter').value;
    const proteinFilter = document.getElementById('protein-filter').value;
    const pivotFilter = document.getElementById('pivot-filter').value;
    
    let filtered = recipes.map((recipe, index) => ({ recipe, originalIndex: index }));
    
    if (baseFilter !== 'all') {
        filtered = filtered.filter(item => item.recipe.base === baseFilter);
    }
    
    if (proteinFilter !== 'all') {
        filtered = filtered.filter(item => item.recipe.protein === proteinFilter);
    }
    
    if (pivotFilter !== 'all') {
        filtered = filtered.filter(item => item.recipe.pivot === pivotFilter);
    }
    
    renderRecipeGrid(filtered);
}

// Render recipe grid
function renderRecipeGrid(recipeList) {
    const grid = document.getElementById('recipe-grid');
    grid.innerHTML = '';
    
    if (recipeList.length === 0) {
        grid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; font-size: 1.25rem; color: #6b7280;">No recipes match your filters.</p>';
        return;
    }
    
    recipeList.forEach((item) => {
        const recipe = item.recipe;
        const originalIndex = item.originalIndex;
        const card = document.createElement('div');
        card.className = 'recipe-card';
        card.onclick = () => showRecipeDetail(originalIndex);
        
        card.innerHTML = `
            <h3>${recipe.recipe_name}</h3>
            <div class="modular-preview">
                <span class="modular-badge base">${recipe.base}</span>
                <span class="modular-badge protein">${recipe.protein}</span>
                <span class="modular-badge pivot">${recipe.pivot}</span>
            </div>
            <div class="recipe-stats">
                <span>💰 $${recipe.estimated_cost_per_serving.toFixed(2)}</span>
                <span>🔥 ${recipe.calories_est} cal</span>
            </div>
        `;
        
        grid.appendChild(card);
    });
}

// Show recipe detail view
function showRecipeDetail(recipeIndex) {
    currentRecipe = recipes[recipeIndex];
    currentStep = 0;
    
    // Populate detail view
    document.getElementById('detail-title').textContent = currentRecipe.recipe_name;
    document.getElementById('detail-base').textContent = currentRecipe.base;
    document.getElementById('detail-protein').textContent = currentRecipe.protein;
    document.getElementById('detail-pivot').textContent = currentRecipe.pivot;
    document.getElementById('detail-cost').textContent = currentRecipe.estimated_cost_per_serving.toFixed(2);
    document.getElementById('detail-calories').textContent = currentRecipe.calories_est;
    
    // Populate ingredients
    const ingredientsList = document.getElementById('ingredients-list');
    ingredientsList.innerHTML = '';
    currentRecipe.ingredients.forEach(ing => {
        const li = document.createElement('li');
        li.textContent = `${ing.quantity} ${ing.item}`;
        ingredientsList.appendChild(li);
    });
    
    // Setup cooking mode
    document.getElementById('total-steps').textContent = currentRecipe.steps.length;
    showStep(0);
    
    // Show detail view
    showView('recipe-detail');
}

// Show specific cooking step
function showStep(stepIndex) {
    currentStep = stepIndex;
    document.getElementById('current-step-num').textContent = currentStep + 1;
    document.getElementById('current-step-text').textContent = currentRecipe.steps[currentStep];
    
    // Update button states
    document.getElementById('prev-step-btn').disabled = currentStep === 0;
    document.getElementById('prev-step-btn').style.opacity = currentStep === 0 ? '0.5' : '1';
    
    const nextBtn = document.getElementById('next-step-btn');
    if (currentStep === currentRecipe.steps.length - 1) {
        nextBtn.textContent = '✓ FINISHED!';
        nextBtn.style.background = 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)';
    } else {
        nextBtn.textContent = 'NEXT STEP →';
        nextBtn.style.background = 'linear-gradient(135deg, var(--success) 0%, #16a34a 100%)';
    }
}

// Navigate to next step
function nextStep() {
    if (currentStep < currentRecipe.steps.length - 1) {
        showStep(currentStep + 1);
    }
}

// Navigate to previous step
function previousStep() {
    if (currentStep > 0) {
        showStep(currentStep - 1);
    }
}

// Show view by ID
function showView(viewId) {
    // Hide all views
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });
    
    // Show target view
    document.getElementById(viewId).classList.add('active');
    
    // Update nav
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.view === viewId) {
            item.classList.add('active');
        }
    });
    
    // Scroll to top
    window.scrollTo(0, 0);
}

// Populate week selection checkboxes
function populateWeekSelection() {
    const container = document.getElementById('week-selection');
    container.innerHTML = '';
    
    recipes.forEach((recipe, index) => {
        const label = document.createElement('label');
        label.className = 'week-meal-checkbox';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = index;
        checkbox.onchange = toggleMealSelection;
        
        const span = document.createElement('span');
        span.textContent = recipe.recipe_name;
        
        label.appendChild(checkbox);
        label.appendChild(span);
        container.appendChild(label);
    });
}

// Toggle meal selection
function toggleMealSelection(e) {
    const index = parseInt(e.target.value);
    if (e.target.checked) {
        selectedMeals.add(index);
    } else {
        selectedMeals.delete(index);
    }
}

// Generate shopping list from selected meals
function generateShoppingList() {
    if (selectedMeals.size === 0) {
        alert('Please select at least one meal for the week!');
        return;
    }
    
    // Aggregate ingredients
    const ingredientMap = new Map();
    
    selectedMeals.forEach(index => {
        const recipe = recipes[index];
        recipe.ingredients.forEach(ing => {
            const key = ing.item.toLowerCase();
            if (ingredientMap.has(key)) {
                ingredientMap.get(key).quantities.push(ing.quantity);
            } else {
                ingredientMap.set(key, {
                    item: ing.item,
                    quantities: [ing.quantity]
                });
            }
        });
    });
    
    // Render shopping list
    const output = document.getElementById('shopping-list-output');
    const itemsContainer = document.getElementById('shopping-items');
    itemsContainer.innerHTML = '';
    
    // Group by category (simple heuristic)
    const categories = {
        'Produce': [],
        'Protein': [],
        'Pantry': [],
        'Spices & Seasonings': [],
        'Dairy': []
    };
    
    ingredientMap.forEach((value, key) => {
        const item = value.item;
        const qty = value.quantities.join(' + ');
        
        // Simple categorization
        if (item.match(/chicken|beef|pork|lentils/i)) {
            categories['Protein'].push(`${qty} ${item}`);
        } else if (item.match(/onion|garlic|ginger|tomato|cucumber|carrot|broccoli|pepper|bok choy|spinach|cilantro|parsley|avocado|sweet potato|beets|butternut|daikon|parsnip/i)) {
            categories['Produce'].push(`${qty} ${item}`);
        } else if (item.match(/milk|yogurt|feta|cheese/i)) {
            categories['Dairy'].push(`${qty} ${item}`);
        } else if (item.match(/salt|pepper|cumin|turmeric|curry|oregano|garam|chili powder|sesame seeds|pumpkin seeds/i)) {
            categories['Spices & Seasonings'].push(`${qty} ${item}`);
        } else {
            categories['Pantry'].push(`${qty} ${item}`);
        }
    });
    
    // Render categories
    Object.entries(categories).forEach(([category, items]) => {
        if (items.length > 0) {
            const div = document.createElement('div');
            div.className = 'shopping-category';
            div.innerHTML = `
                <h4>${category}</h4>
                <ul>
                    ${items.map(item => `<li>☐ ${item}</li>`).join('')}
                </ul>
            `;
            itemsContainer.appendChild(div);
        }
    });
    
    output.classList.add('active');
    output.scrollIntoView({ behavior: 'smooth' });
}

// Copy shopping list to clipboard
function copyShoppingList() {
    const itemsContainer = document.getElementById('shopping-items');
    const text = itemsContainer.innerText;
    
    navigator.clipboard.writeText(text).then(() => {
        alert('Shopping list copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy:', err);
        alert('Failed to copy to clipboard');
    });
}

// Print shopping list
function printShoppingList() {
    window.print();
}

// Keyboard navigation for cooking mode
document.addEventListener('keydown', (e) => {
    if (document.getElementById('recipe-detail').classList.contains('active')) {
        if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'Enter') {
            e.preventDefault();
            nextStep();
        } else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            previousStep();
        }
    }
});

// Initialize on load
window.addEventListener('DOMContentLoaded', init);
