// ========================================
// LinkShort - Enhanced JavaScript
// ========================================

/**
 * Copy link to clipboard with visual feedback
 */
function copyLink(btn) {
    const input = document.getElementById("shortLink");
    const originalText = btn.innerHTML;
    
    // Copy to clipboard
    navigator.clipboard.writeText(input.value).then(() => {
        // Visual feedback
        btn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
            </svg>
            Copied!
        `;
        btn.style.background = "var(--success)";
        
        // Reset after delay
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.style.background = "";
        }, 2000);
    }).catch(err => {
        // Fallback for older browsers
        input.select();
        document.execCommand('copy');
        btn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
            </svg>
            Copied!
        `;
        setTimeout(() => {
            btn.innerHTML = originalText;
        }, 2000);
    });
}

/**
 * Add keyboard shortcuts
 */
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + K to focus URL input
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const urlInput = document.querySelector('input[name="url"]');
        if (urlInput) urlInput.focus();
    }
    
    // Enter to submit form when input is focused
    if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
        const form = e.target.closest('form');
        if (form) {
            const button = form.querySelector('button[type="submit"]');
            if (button) button.click();
        }
    }
});

/**
 * Add smooth reveal animation on page load
 */
document.addEventListener('DOMContentLoaded', function() {
    const cards = document.querySelectorAll('.card, .link-item, .stat-card');
    
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
        
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 100 + (index * 80));
    });
});

/**
 * Auto-dismiss alerts after delay
 */
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            alert.style.transition = 'all 0.3s ease';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});
