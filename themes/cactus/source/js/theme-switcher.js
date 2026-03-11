// 定义主题顺序
const themes = ['white', 'classic', 'dark', 'light'];

// 切换逻辑
window.toggleTheme = function() {
    // 1. 获取当前主题 (从 localStorage 获取，如果没有则说明是默认状态)
    // 注意：这里的默认值应与你 _config.yml 里的 colorscheme 一致
    const currentTheme = localStorage.getItem('theme') || 'classic';

    // 2. 计算下一个主题
    const currentIndex = themes.indexOf(currentTheme);
    const nextIndex = (currentIndex + 1) % themes.length;
    const nextTheme = themes[nextIndex];

    // 3. 设置 HTML 属性 (触发 CSS 变量变化)
    document.documentElement.setAttribute('data-theme', nextTheme);

    // 4. 保存到本地存储
    localStorage.setItem('theme', nextTheme);
    
    console.log('Theme switched to:', nextTheme);
};

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
    }
});
