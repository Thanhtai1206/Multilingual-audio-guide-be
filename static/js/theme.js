function initTheme() {
    const themeToggle = document.getElementById('theme-toggle');
    const body = document.body;

    function applyTheme(theme) {
        body.setAttribute('data-theme', theme);
        body.classList.remove('dark-mode', 'light-mode');
        body.classList.add(`${theme}-mode`);
        localStorage.setItem('theme', theme);
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const currentTheme = body.getAttribute('data-theme') || 'dark';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(newTheme);
        });
    }

    // Initialize
    const savedTheme = localStorage.getItem('theme') || 'dark';
    applyTheme(savedTheme);
}

document.addEventListener('DOMContentLoaded', initTheme);
