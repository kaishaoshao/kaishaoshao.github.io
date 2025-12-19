// source/js/theme-switcher.js

// 定义主题顺序
const themes = ['white', 'classic', 'dark', 'light'];

// 切换逻辑
function toggleTheme() {
    // 1. 获取当前主题
    const currentTheme = localStorage.getItem('theme') || 'white';

    // 2. 计算下一个主题
    const currentIndex = themes.indexOf(currentTheme);
    const nextIndex = (currentIndex + 1) % themes.length;
    const nextTheme = themes[nextIndex];

    // 3. 设置 HTML 属性 (触发 CSS 变量变化)
    document.documentElement.setAttribute('data-theme', nextTheme);

    // 4. 保存到本地存储
    localStorage.setItem('theme', nextTheme);
}
