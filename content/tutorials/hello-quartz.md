---
title: Hello Quartz
date: 2026-05-27
---

Welcome to **Quartz**! This is a quick introduction to the static site generator. Below are some basic commands to get you started.

## Quick Start

### Install / Setup Quartz CLI

Quartz 是一个基于源码与内容驱动的静态站点生成器，无需通过 npm 全局安装第三方包：

1. **在已有 Quartz 仓库中使用**：
   在本项目根目录下，直接使用 `npx quartz` 或全局链接命令即可：
   ```bash
   # 全局链接本地命令（可选，支持全局直接运行 quartz）
   npm link
   ```

2. **从零新建 Quartz 站点**：
   ```bash
   git clone https://github.com/jackyzha0/quartz.git my-quartz-site
   cd my-quartz-site
   npm install
   npx quartz create
   ```

### Run the development server

```bash
npx quartz build --serve
```

You can now edit the files under the `content/` folder and see live updates.

### Create a new Markdown document
Create a new file in `content/` with a `.md` extension. For example:
```bash
mkdir -p content
touch content/my-new-post.md
```
Then add front‑matter at the top:
```markdown
---
title: My New Post
date: 2026-05-27
---
```
Write your article in Markdown below the front‑matter.

### Push changes and let CI build the site
```bash
git checkout -b feature/my-new-post
git add content/my-new-post.md
git commit -m "Add new post"
git push -u origin feature/my-new-post
```
Create a Pull Request to `main`. Our GitHub Actions workflow (see `.github/workflows/ci.yml`) runs `npx quartz build` on every push to `main`, automatically generating the static site and publishing it (e.g., to GitHub Pages).

---

## 其他教程
- [Hello Hexo](/tutorials/hello-world.md)

---

> **Tip:** Quartz uses Markdown files with front‑matter to generate pages. Feel free to explore the `content/` directory and experiment with different layouts.
