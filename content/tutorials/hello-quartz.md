---
title: Hello Quartz
date: 2026-05-27
---

Welcome to **Quartz**! This is a quick introduction to the static site generator. Below are some basic commands to get you started.

## Quick Start

### Install Quartz CLI

```bash
npm i -g @quartz-cli/quartz
```

### Create a new site

```bash
mkdir my-quartz-site
cd my-quartz-site
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
