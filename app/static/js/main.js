/**
 * Kitchen Companion - Main JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Kitchen Companion loaded successfully!');
    
    // Health check
    fetch('/api/health')
        .then(response => response.json())
        .then(data => {
            console.log('API Health:', data.status);
        })
        .catch(error => {
            console.error('API connection error:', error);
        });
});