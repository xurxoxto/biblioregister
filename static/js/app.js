/**
 * BiblioRegister — Frontend JS
 */

// ── Sidebar Toggle (mobile) ─────────────────────────────────────
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    sidebar.classList.toggle('show');
    overlay.classList.toggle('show');
}

// Close sidebar on resize to desktop
window.addEventListener('resize', function() {
    if (window.innerWidth >= 992) {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebarOverlay');
        if (sidebar) sidebar.classList.remove('show');
        if (overlay) overlay.classList.remove('show');
    }
});

// ── Auto-dismiss flash alerts ───────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            try {
                const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                bsAlert.close();
            } catch(e) {}
        }, 5000);
    });

    // Animate stat cards
    document.querySelectorAll('.stat-card').forEach(function(card, i) {
        card.style.animationDelay = (i * 0.08) + 's';
        card.classList.add('animate-in');
    });
});

// ── Confirm before delete actions ───────────────────────────────
document.querySelectorAll('[data-confirm]').forEach(function(el) {
    el.addEventListener('click', function(e) {
        if (!confirm(el.dataset.confirm)) {
            e.preventDefault();
        }
    });
});

// ── Floating Action Button (FAB) ────────────────────────────────
(function() {
    const fabContainer = document.getElementById('fabContainer');
    const fabTrigger = document.getElementById('fabTrigger');
    if (!fabContainer || !fabTrigger) return;

    fabTrigger.addEventListener('click', function(e) {
        e.stopPropagation();
        fabContainer.classList.toggle('open');
    });

    // Close FAB on outside click
    document.addEventListener('click', function(e) {
        if (!fabContainer.contains(e.target)) {
            fabContainer.classList.remove('open');
        }
    });

    // Close FAB on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            fabContainer.classList.remove('open');
        }
    });
})();
