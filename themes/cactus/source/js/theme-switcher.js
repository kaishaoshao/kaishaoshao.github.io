// source/js/theme-switcher.js

// 1. 设置指定主题
function setTheme(themeName) {
    // 设置 HTML 属性，触发 CSS 变化
    document.documentElement.setAttribute('data-theme', themeName);
    // 保存到本地存储
    localStorage.setItem('theme', themeName);
}

// 2. 初始化下拉菜单的状态 (让菜单显示当前选中的颜色)
function initThemeSelect() {
    const savedTheme = localStorage.getItem('theme') || 'white';
    const selectElement = document.getElementById('theme-select');
    if (selectElement) {
        selectElement.value = savedTheme;
    }
}

// 页面加载完成后，同步菜单状态
document.addEventListener('DOMContentLoaded', initThemeSelect);