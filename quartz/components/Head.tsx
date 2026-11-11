import { i18n } from "../i18n"
import { FullSlug, getFileExtension, joinSegments, pathToRoot } from "../util/path"
import { CSSResourceToStyleElement, JSResourceToScriptElement } from "../util/resources"
import { googleFontHref, googleFontSubsetHref } from "../util/theme"
import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import { unescapeHTML } from "../util/escape"
// Fallback emitter name when og-image plugin is disabled
const CustomOgImagesEmitterName = "custom-og-image"

const ALAN_CLIENT_SCRIPT = `
(function () {
  if (window.__alanRunInit) {
    window.__alanRunInit();
    return;
  }

  var PALETTES = [
    { id: "alan", name: "羊皮暖纸 (Alan)", swatch: "swatch-alan" },
    { id: "blue", name: "科技极简蓝", swatch: "swatch-blue" },
    { id: "green", name: "数字花园绿", swatch: "swatch-green" },
    { id: "purple", name: "赛博曜石紫", swatch: "swatch-purple" },
    { id: "catppuccin", name: "猫咪暖色 (Mocha)", swatch: "swatch-catppuccin" }
  ];

  function getPalette() {
    try {
      return localStorage.getItem("theme-palette") || "alan";
    } catch (e) {
      return "alan";
    }
  }

  function updatePaletteMenu() {
    var cur = getPalette();
    document.querySelectorAll(".palette-option-btn").forEach(function (btn) {
      if (btn.getAttribute("data-palette") === cur) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    });
  }

  function setPalette(id) {
    document.documentElement.setAttribute("theme-palette", id);
    try {
      localStorage.setItem("theme-palette", id);
    } catch (e) {}
    updatePaletteMenu();
    window.dispatchEvent(new CustomEvent("theme-palette-change", { detail: { palette: id } }));
  }

  function mountPalettePicker(isHome) {
    var existing = document.getElementById("theme-palette-wrapper");
    var homeSlot = isHome ? document.getElementById("alan-top-palette-slot") : null;
    var darkBtn = document.querySelector(".sidebar.left button.darkmode");

    if (existing) {
      if (isHome && homeSlot && existing.parentElement !== homeSlot) {
        homeSlot.appendChild(existing);
      } else if (
        !isHome &&
        darkBtn &&
        darkBtn.parentElement &&
        darkBtn.parentElement.parentElement &&
        existing.parentElement !== darkBtn.parentElement.parentElement
      ) {
        darkBtn.parentElement.parentElement.insertBefore(existing, darkBtn.parentElement.nextSibling);
      }
      updatePaletteMenu();
      return;
    }

    if (isHome && !homeSlot) return;
    if (!isHome && (!darkBtn || !darkBtn.parentElement || !darkBtn.parentElement.parentElement)) return;

    var wrapper = document.createElement("div");
    wrapper.id = "theme-palette-wrapper";
    wrapper.className = "palette-picker-wrapper";
    wrapper.style.cssText =
      "flex-grow:0;flex-shrink:1;flex-basis:auto;order:0;align-self:center;justify-self:center;";

    var btn = document.createElement("button");
    btn.className = "palette-toggle-btn";
    btn.setAttribute("aria-label", "切换主题配色 (Palette)");
    btn.setAttribute("title", "切换主题配色");
    btn.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/></svg>';

    var menu = document.createElement("div");
    menu.className = "palette-menu hidden";

    PALETTES.forEach(function (p) {
      var opt = document.createElement("button");
      opt.type = "button";
      opt.className = "palette-option-btn";
      opt.setAttribute("data-palette", p.id);
      opt.innerHTML =
        '<span class="palette-swatch ' +
        p.swatch +
        '"></span><span class="palette-name">' +
        p.name +
        '</span><span class="palette-check">✓</span>';
      opt.addEventListener("click", function (e) {
        e.stopPropagation();
        setPalette(p.id);
        menu.classList.add("hidden");
      });
      menu.appendChild(opt);
    });

    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      menu.classList.toggle("hidden");
    });

    wrapper.appendChild(btn);
    wrapper.appendChild(menu);
    if (isHome && homeSlot) {
      homeSlot.appendChild(wrapper);
    } else if (darkBtn && darkBtn.parentElement && darkBtn.parentElement.parentElement) {
      darkBtn.parentElement.parentElement.insertBefore(wrapper, darkBtn.parentElement.nextSibling);
    }
    updatePaletteMenu();

    if (!window.__alanPaletteDocBound) {
      window.__alanPaletteDocBound = true;
      document.addEventListener("click", function (e) {
        var w = document.getElementById("theme-palette-wrapper");
        var m = w ? w.querySelector(".palette-menu") : null;
        if (w && m && !w.contains(e.target)) {
          m.classList.add("hidden");
        }
      });
    }
  }

  function syncTopThemeBtn() {
    var btn = document.getElementById("alan-top-theme");
    if (!btn) return;
    var isDark = document.documentElement.getAttribute("saved-theme") === "dark";
    btn.setAttribute("title", isDark ? "切换亮色模式" : "切换暗色模式");
    btn.setAttribute("aria-label", isDark ? "切换亮色模式" : "切换暗色模式");
    btn.innerHTML = isDark
      ? '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>'
      : '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>';
  }

  function mountTopMenu(isHome) {
    var existing = document.getElementById("alan-top-menu");
    if (!isHome) {
      if (existing) existing.remove();
      return;
    }
    if (existing) {
      syncTopThemeBtn();
      return;
    }

    var nav = document.createElement("nav");
    nav.id = "alan-top-menu";
    nav.setAttribute("aria-label", "Primary navigation");
    nav.innerHTML =
      '<div class="alan-menu-inner">' +
        '<a href="#alan-intro" class="alan-menu-brand" data-router-ignore="true" data-alan-target="alan-intro">kaishaoshao</a>' +
        '<ul id="alan-menu-items">' +
          '<li><a href="#alan-intro" data-router-ignore="true" data-alan-target="alan-intro" class="active">Intro</a></li>' +
          '<li><a href="#alan-about" data-router-ignore="true" data-alan-target="alan-about">About</a></li>' +
          '<li><a href="#alan-directories" data-router-ignore="true" data-alan-target="alan-directories">Directories</a></li>' +
          '<li><a href="#alan-graph" data-router-ignore="true" data-alan-target="alan-graph">Graph</a></li>' +
          '<li><a href="./notes/">Notes</a></li>' +
        '</ul>' +
        '<div class="alan-top-actions">' +
          '<button type="button" id="alan-top-search" class="alan-top-icon-btn" aria-label="Search (Ctrl+K)" title="搜索文章 (Ctrl+K)">' +
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>' +
          '</button>' +
          '<button type="button" id="alan-top-theme" class="alan-top-icon-btn"></button>' +
          '<div id="alan-top-palette-slot"></div>' +
        '</div>' +
      '</div>';

    var root = document.getElementById("quartz-root") || document.body;
    root.insertBefore(nav, root.firstChild);

    nav.querySelectorAll("[data-alan-target]").forEach(function (link) {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        var id = link.getAttribute("data-alan-target");
        var target = id ? document.getElementById(id) : null;
        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });

    var searchBtn = document.getElementById("alan-top-search");
    if (searchBtn) {
      searchBtn.addEventListener("click", function () {
        var realSearch = document.querySelector(".sidebar.left .search-button");
        if (realSearch) realSearch.click();
      });
    }

    var themeBtn = document.getElementById("alan-top-theme");
    if (themeBtn) {
      themeBtn.addEventListener("click", function () {
        var realDark = document.querySelector(".sidebar.left button.darkmode");
        if (realDark) realDark.click();
      });
    }

    if (!window.__alanThemeBound) {
      window.__alanThemeBound = true;
      document.addEventListener("themechange", syncTopThemeBtn);
    }
    syncTopThemeBtn();
  }

  function ensureReadingProgress() {
    var bar = document.getElementById("alan-reading-progress");
    if (!bar && document.body) {
      bar = document.createElement("div");
      bar.id = "alan-reading-progress";
      bar.innerHTML = '<div class="alan-progress-fill"></div>';
      document.body.appendChild(bar);
    }
    updateScrollEffects();
  }

  function updateScrollEffects() {
    var fill = document.querySelector("#alan-reading-progress .alan-progress-fill");
    var scrollTop = window.scrollY || document.documentElement.scrollTop || 0;
    var docHeight = document.documentElement.scrollHeight - window.innerHeight;
    if (fill) {
      var ratio = docHeight > 0 ? Math.min(1, Math.max(0, scrollTop / docHeight)) : 0;
      fill.style.width = (ratio * 100).toFixed(2) + "%";
    }
    var star = document.getElementById("alan-intro-star");
    if (star) {
      var deg = -(scrollTop * 0.12);
      var scale = Math.max(0.76, 1 - scrollTop / 2200);
      star.style.transform = "rotate(" + deg.toFixed(1) + "deg) scale(" + scale.toFixed(3) + ")";
    }

    var menuLinks = document.querySelectorAll("#alan-menu-items a[data-alan-target]");
    if (menuLinks.length > 0) {
      var activeId = "alan-intro";
      var anchorIds = ["alan-intro", "alan-about", "alan-directories", "alan-graph"];
      anchorIds.forEach(function (id) {
        var sec = document.getElementById(id);
        if (sec && sec.getBoundingClientRect().top <= 160) {
          activeId = id;
        }
      });
      menuLinks.forEach(function (a) {
        if (a.getAttribute("data-alan-target") === activeId) {
          a.classList.add("active");
        } else {
          a.classList.remove("active");
        }
      });
    }
  }

  function bindGlobalScroll() {
    if (window.__alanScrollBound) return;
    window.__alanScrollBound = true;
    var ticking = false;
    window.addEventListener(
      "scroll",
      function () {
        if (!ticking) {
          ticking = true;
          window.requestAnimationFrame(function () {
            updateScrollEffects();
            ticking = false;
          });
        }
      },
      { passive: true }
    );
  }

  function getDirCardMeta(dirLabel, href) {
    var key = (dirLabel || "").replace(/\\/$/, "").toLowerCase();
    var map = {
      notes: {
        kicker: "NOTES · KNOWLEDGE BASE",
        tags: ["Arch · LLM", "LLVM · MLIR", "Opt · RISCV"],
        svg: '<svg viewBox="0 0 240 120" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="36" y="22" width="50" height="76" rx="8" stroke="currentColor" stroke-width="2" fill="currentColor" fill-opacity="0.08"/><rect x="95" y="18" width="50" height="80" rx="8" stroke="var(--secondary)" stroke-width="2.2" fill="var(--secondary)" fill-opacity="0.16"/><rect x="154" y="22" width="50" height="76" rx="8" stroke="currentColor" stroke-width="2" fill="currentColor" fill-opacity="0.08"/><path d="M48 42h26M48 56h20M48 70h16M107 40h26M107 54h22M107 68h18M166 42h26M166 56h20M166 70h16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
      },
      arch: {
        kicker: "NOTES · ARCHITECTURE",
        tags: ["ISA", "流水线", "Cache"],
        svg: '<svg viewBox="0 0 240 120" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="64" y="24" width="112" height="72" rx="10" stroke="currentColor" stroke-width="2" fill="currentColor" fill-opacity="0.08"/><rect x="86" y="42" width="68" height="36" rx="5" stroke="var(--secondary)" stroke-width="2" fill="var(--secondary)" fill-opacity="0.14"/><path d="M40 42h24M40 60h24M40 78h24M176 42h24M176 60h24M176 78h24M96 10v14M120 10v14M144 10v14M96 96v14M120 96v14M144 96v14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
      },
      llm: {
        kicker: "NOTES · LLM SYSTEMS",
        tags: ["Transformer", "Zero-to-Hero", "训练"],
        svg: '<svg viewBox="0 0 240 120" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="62" cy="36" r="10" stroke="currentColor" stroke-width="2" fill="currentColor" fill-opacity="0.1"/><circle cx="62" cy="84" r="10" stroke="currentColor" stroke-width="2" fill="currentColor" fill-opacity="0.1"/><circle cx="120" cy="60" r="14" stroke="var(--secondary)" stroke-width="2.2" fill="var(--secondary)" fill-opacity="0.18"/><circle cx="178" cy="36" r="10" stroke="currentColor" stroke-width="2" fill="currentColor" fill-opacity="0.1"/><circle cx="178" cy="84" r="10" stroke="currentColor" stroke-width="2" fill="currentColor" fill-opacity="0.1"/><path d="M72 40l36 16M72 80l36-16M134 56l34-16M134 64l34 16M62 46v28M178 46v28" stroke="currentColor" stroke-width="1.8" opacity="0.8"/></svg>'
      },
      llvm: {
        kicker: "NOTES · COMPILERS",
        tags: ["CodeGen", "LLVM IR", "Backend"],
        svg: '<svg viewBox="0 0 240 120" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="28" y="42" width="44" height="36" rx="8" stroke="currentColor" stroke-width="2" fill="currentColor" fill-opacity="0.08"/><rect x="98" y="34" width="44" height="52" rx="8" stroke="var(--secondary)" stroke-width="2.2" fill="var(--secondary)" fill-opacity="0.16"/><rect x="168" y="42" width="44" height="36" rx="8" stroke="currentColor" stroke-width="2" fill="currentColor" fill-opacity="0.08"/><path d="M72 60h22M142 60h22" stroke="var(--secondary)" stroke-width="2.2" stroke-linecap="round"/><path d="M88 54l6 6-6 6M158 54l6 6-6 6" stroke="var(--secondary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
      },
      mlir: {
        kicker: "NOTES · MLIR & TABLEGEN",
        tags: ["Dialects", "TableGen", "Lowering"],
        svg: '<svg viewBox="0 0 240 120" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M48 32h144M64 60h112M82 88h76" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><circle cx="72" cy="32" r="7" fill="var(--secondary)"/><circle cx="120" cy="60" r="7" fill="var(--tertiary)"/><circle cx="144" cy="88" r="7" fill="var(--secondary)"/><path d="M72 39l44 15M122 67l18 15" stroke="var(--secondary)" stroke-width="1.8" stroke-dasharray="3 3"/></svg>'
      },
      opt: {
        kicker: "NOTES · PERFORMANCE",
        tags: ["Cache 局部性", "GEMM", "Profiling"],
        svg: '<svg viewBox="0 0 240 120" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M36 92h168" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><rect x="52" y="66" width="22" height="26" rx="4" fill="currentColor" fill-opacity="0.2" stroke="currentColor" stroke-width="1.8"/><rect x="90" y="50" width="22" height="42" rx="4" fill="currentColor" fill-opacity="0.28" stroke="currentColor" stroke-width="1.8"/><rect x="128" y="34" width="22" height="58" rx="4" fill="var(--tertiary)" fill-opacity="0.35" stroke="var(--tertiary)" stroke-width="1.8"/><rect x="166" y="20" width="22" height="72" rx="4" fill="var(--secondary)" fill-opacity="0.35" stroke="var(--secondary)" stroke-width="2"/><path d="M56 54l38-16 38-14 40-12" stroke="var(--secondary)" stroke-width="2" stroke-linecap="round" stroke-dasharray="4 4"/></svg>'
      },
      riscv: {
        kicker: "NOTES · RISC-V RVV",
        tags: ["Vector ISA", "SIMD", "VLEN"],
        svg: '<svg viewBox="0 0 240 120" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="34" y="30" width="38" height="60" rx="6" stroke="currentColor" stroke-width="2" fill="currentColor" fill-opacity="0.08"/><rect x="82" y="30" width="38" height="60" rx="6" stroke="var(--secondary)" stroke-width="2" fill="var(--secondary)" fill-opacity="0.16"/><rect x="130" y="30" width="38" height="60" rx="6" stroke="currentColor" stroke-width="2" fill="currentColor" fill-opacity="0.08"/><rect x="178" y="30" width="38" height="60" rx="6" stroke="var(--secondary)" stroke-width="2" fill="var(--secondary)" fill-opacity="0.16"/><path d="M44 50h18M44 68h18M92 50h18M92 68h18M140 50h18M140 68h18M188 50h18M188 68h18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
      },
      tutorials: {
        kicker: "TUTORIALS · GUIDES",
        tags: ["Quartz v5", "Hexo", "建站"],
        svg: '<svg viewBox="0 0 240 120" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M46 28h64c8 0 10 6 10 12v54c-4-4-10-6-16-6H46V28Z" stroke="currentColor" stroke-width="2" fill="currentColor" fill-opacity="0.08"/><path d="M194 28h-64c-8 0-10 6-10 12v54c4-4 10-6 16-6h58V28Z" stroke="var(--secondary)" stroke-width="2" fill="var(--secondary)" fill-opacity="0.12"/><path d="M62 46h36M62 60h30M142 46h36M142 60h30" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
      },
      skills: {
        kicker: "SKILLS · TOOLCHAIN",
        tags: ["LLVM / Clang", "GCC", "Cross-Compile"],
        svg: '<svg viewBox="0 0 240 120" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="96" cy="60" r="24" stroke="var(--secondary)" stroke-width="2.2" fill="var(--secondary)" fill-opacity="0.14"/><circle cx="96" cy="60" r="9" stroke="var(--secondary)" stroke-width="2"/><path d="M96 28v8M96 84v8M64 60h8M120 60h8M73 37l6 6M113 77l6 6M119 37l-6 6M79 77l-6 6" stroke="var(--secondary)" stroke-width="2.2" stroke-linecap="round"/><circle cx="156" cy="70" r="16" stroke="currentColor" stroke-width="2" fill="currentColor" fill-opacity="0.08"/><circle cx="156" cy="70" r="5" stroke="currentColor" stroke-width="1.8"/></svg>'
      }
    };
    return map[key] || {
      kicker: (href && href.indexOf("/notes/") !== -1) ? "NOTES" : "DIRECTORY",
      tags: ["目录归档"],
      svg: '<svg viewBox="0 0 240 120" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M52 34h48l12 12h76v46H52V34Z" stroke="var(--secondary)" stroke-width="2.2" fill="var(--secondary)" fill-opacity="0.14" stroke-linejoin="round"/></svg>'
    };
  }

  function buildAboutSection() {
    var sec = document.createElement("section");
    sec.id = "alan-about";
    sec.setAttribute("aria-label", "About");
    sec.innerHTML =
      '<h2 class="alan-section-title">About</h2>' +
      '<div class="alan-about-carousel">' +
        '<button type="button" class="alan-carousel-btn alan-carousel-prev" aria-label="上一张卡片" title="上一张">' +
          '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>' +
        '</button>' +
        '<div class="alan-about-deck" tabindex="0" role="region" aria-label="About cards">' +
          '<article class="alan-about-card is-active" data-slide="0">' +
            '<div class="alan-about-art" aria-hidden="true">' +
              '<svg viewBox="0 0 160 140" fill="none" xmlns="http://www.w3.org/2000/svg">' +
                '<circle cx="80" cy="70" r="52" stroke="currentColor" stroke-width="1.8" stroke-dasharray="4 5" opacity="0.65"/>' +
                '<circle cx="80" cy="70" r="36" stroke="var(--secondary)" stroke-width="2" fill="var(--secondary)" fill-opacity="0.1"/>' +
                '<path d="M80 24l11 35 35 11-35 11-11 35-11-35-35-11 35-11 11-35Z" stroke="var(--secondary)" stroke-width="1.8" fill="var(--secondary)" fill-opacity="0.18" stroke-linejoin="round"/>' +
                '<circle cx="80" cy="70" r="5" fill="var(--dark)"/>' +
              '</svg>' +
            '</div>' +
            '<div class="alan-about-content">' +
              '<h3 class="alan-about-title">Explorer</h3>' +
              '<p class="alan-about-text">保持好奇心的底层技术探索者，习惯用第一性原理把复杂的系统拆解清楚。喜欢简洁、克制且直击本质的表达方式，在这里持续记录对计算机体系结构、编译技术与系统性能的思考。</p>' +
            '</div>' +
          '</article>' +
          '<article class="alan-about-card" data-slide="1">' +
            '<div class="alan-about-art" aria-hidden="true">' +
              '<svg viewBox="0 0 160 140" fill="none" xmlns="http://www.w3.org/2000/svg">' +
                '<rect x="20" y="28" width="120" height="84" rx="12" stroke="currentColor" stroke-width="1.8" fill="currentColor" fill-opacity="0.06"/>' +
                '<rect x="34" y="44" width="38" height="22" rx="5" stroke="var(--secondary)" stroke-width="1.8" fill="var(--secondary)" fill-opacity="0.18"/>' +
                '<rect x="88" y="44" width="38" height="22" rx="5" stroke="currentColor" stroke-width="1.8"/>' +
                '<rect x="34" y="76" width="92" height="20" rx="5" stroke="var(--tertiary)" stroke-width="1.8" fill="var(--tertiary)" fill-opacity="0.16"/>' +
                '<path d="M72 55h16M80 66v10" stroke="var(--secondary)" stroke-width="1.8" stroke-linecap="round"/>' +
              '</svg>' +
            '</div>' +
            '<div class="alan-about-content">' +
              '<h3 class="alan-about-title">Compilers &amp; Systems</h3>' +
              '<p class="alan-about-text">日常研究与实践围绕 LLVM / MLIR 多级中间表示、TableGen 与代码生成、程序性能优化（Cache 局部性与矩阵乘法调优）、RISC-V RVV 向量扩展以及 LLM 大模型底层系统展开。</p>' +
            '</div>' +
          '</article>' +
          '<article class="alan-about-card" data-slide="2">' +
            '<div class="alan-about-art" aria-hidden="true">' +
              '<svg viewBox="0 0 160 140" fill="none" xmlns="http://www.w3.org/2000/svg">' +
                '<rect x="34" y="22" width="92" height="96" rx="12" stroke="currentColor" stroke-width="1.8" fill="currentColor" fill-opacity="0.06"/>' +
                '<circle cx="80" cy="36" r="5" fill="var(--light)" stroke="currentColor" stroke-width="1.6"/>' +
                '<path d="M50 56h60M50 72h52M50 88h40" stroke="var(--secondary)" stroke-width="2.2" stroke-linecap="round"/>' +
                '<path d="M104 94l16-16 6 6-16 16-8 2 2-8Z" stroke="currentColor" stroke-width="1.8" fill="var(--secondary)" fill-opacity="0.25" stroke-linejoin="round"/>' +
              '</svg>' +
            '</div>' +
            '<div class="alan-about-content">' +
              '<h3 class="alan-about-title">Why This Garden?</h3>' +
              '<p class="alan-about-text">看过的论文、读过的源码和踩过的坑如果不系统整理很容易遗忘。我把笔记按主题目录沉淀成这座可检索的数字花园——只求脉络清晰、随时可翻阅，也希望能给同路人带来一点参考。</p>' +
              '<div class="alan-about-action">' +
                '<a href="#alan-directories" class="alan-flat-btn" data-router-ignore="true" data-alan-scroll="directories">Explore Directories →</a>' +
              '</div>' +
            '</div>' +
          '</article>' +
        '</div>' +
        '<button type="button" class="alan-carousel-btn alan-carousel-next" aria-label="下一张卡片" title="下一张">' +
          '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>' +
        '</button>' +
      '</div>' +
      '<div class="alan-carousel-dots" role="tablist" aria-label="About 卡片导航">' +
        '<button type="button" class="alan-carousel-dot is-active" data-slide-to="0" aria-label="第 1 张卡片"></button>' +
        '<button type="button" class="alan-carousel-dot" data-slide-to="1" aria-label="第 2 张卡片"></button>' +
        '<button type="button" class="alan-carousel-dot" data-slide-to="2" aria-label="第 3 张卡片"></button>' +
      '</div>';

    var deck = sec.querySelector(".alan-about-deck");
    var cards = Array.from(sec.querySelectorAll(".alan-about-card"));
    var dots = Array.from(sec.querySelectorAll(".alan-carousel-dot"));
    var prevBtn = sec.querySelector(".alan-carousel-prev");
    var nextBtn = sec.querySelector(".alan-carousel-next");
    var activeIdx = 0;

    function scrollToCard(idx) {
      if (!deck || cards.length === 0) return;
      var wrapped = ((idx % cards.length) + cards.length) % cards.length;
      var card = cards[wrapped];
      var targetLeft = card.offsetLeft - (deck.clientWidth - card.clientWidth) / 2;
      deck.scrollTo({ left: Math.max(0, targetLeft), behavior: "smooth" });
    }

    function syncCarouselState() {
      if (!deck || cards.length === 0) return;
      var centerX = deck.scrollLeft + deck.clientWidth / 2;
      var bestIdx = 0;
      var bestDist = Infinity;
      cards.forEach(function (card, idx) {
        var cardCenter = card.offsetLeft + card.clientWidth / 2;
        var dist = Math.abs(centerX - cardCenter);
        if (dist < bestDist) {
          bestDist = dist;
          bestIdx = idx;
        }
      });
      activeIdx = bestIdx;
      cards.forEach(function (card, idx) {
        if (idx === bestIdx) {
          card.classList.add("is-active");
        } else {
          card.classList.remove("is-active");
        }
      });
      dots.forEach(function (dot, idx) {
        if (idx === bestIdx) {
          dot.classList.add("is-active");
        } else {
          dot.classList.remove("is-active");
        }
      });
    }

    if (deck) {
      var rafPending = false;
      deck.addEventListener(
        "scroll",
        function () {
          if (!rafPending) {
            rafPending = true;
            window.requestAnimationFrame(function () {
              syncCarouselState();
              rafPending = false;
            });
          }
        },
        { passive: true }
      );

      cards.forEach(function (card, idx) {
        card.addEventListener("click", function (e) {
          if (e.target && e.target.closest && e.target.closest("a, button")) return;
          if (idx !== activeIdx) scrollToCard(idx);
        });
      });

      var isDragging = false;
      var startX = 0;
      var startScroll = 0;
      deck.addEventListener("mousedown", function (e) {
        if (e.button !== 0) return;
        if (e.target && e.target.closest && e.target.closest("a, button")) return;
        isDragging = true;
        startX = e.pageX;
        startScroll = deck.scrollLeft;
        deck.classList.add("is-dragging");
      });
      window.addEventListener("mousemove", function (e) {
        if (!isDragging) return;
        var dx = e.pageX - startX;
        deck.scrollLeft = startScroll - dx;
      });
      window.addEventListener("mouseup", function () {
        if (!isDragging) return;
        isDragging = false;
        deck.classList.remove("is-dragging");
      });

      deck.addEventListener("keydown", function (e) {
        if (e.key === "ArrowLeft") {
          e.preventDefault();
          scrollToCard(activeIdx - 1);
        } else if (e.key === "ArrowRight") {
          e.preventDefault();
          scrollToCard(activeIdx + 1);
        }
      });
    }

    if (prevBtn) {
      prevBtn.addEventListener("click", function () {
        scrollToCard(activeIdx - 1);
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener("click", function () {
        scrollToCard(activeIdx + 1);
      });
    }
    dots.forEach(function (dot) {
      dot.addEventListener("click", function () {
        var idx = parseInt(dot.getAttribute("data-slide-to") || "0", 10);
        scrollToCard(idx);
      });
    });

    var btn = sec.querySelector('[data-alan-scroll="directories"]');
    if (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        var dirSec = document.getElementById("alan-directories");
        if (dirSec) dirSec.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }

    window.requestAnimationFrame(function () {
      scrollToCard(0);
      syncCarouselState();
    });
    return sec;
  }

  function enhanceHomepage() {
    if (!document.body) return;
    var slug = document.body.getAttribute("data-slug");
    var isHome = slug === "index";
    mountTopMenu(isHome);
    mountPalettePicker(isHome);

    if (!isHome) {
      document.body.classList.remove("alan-enhanced");
      return;
    }

    var center = document.querySelector(".center");
    var article = center ? center.querySelector("article") : null;
    var md = article ? article.querySelector(".markdown-rendered") || article : null;
    if (!center || !article || !md) return;

    if (!document.getElementById("alan-intro")) {
      var children = Array.from(md.children);
      for (var i = 0; i < children.length; i++) {
        if (children[i].tagName === "H2") break;
        if (children[i].tagName === "P" && children[i].textContent.trim().length > 0) {
          children[i].classList.add("alan-moved-intro");
          break;
        }
      }

      var intro = document.createElement("section");
      intro.id = "alan-intro";
      intro.setAttribute("aria-label", "Introduction");
      intro.innerHTML =
        '<div class="alan-intro-inner">' +
          '<div id="alan-intro-text">' +
            '<div id="alan-intro-salutation">Hi, I\\'m</div>' +
            '<h1 id="alan-intro-name">kaishaoshao</h1>' +
            '<div id="alan-intro-tag-line">I compile &amp; explore here</div>' +
          '</div>' +
          '<div class="alan-intro-visual" aria-hidden="true">' +
            '<div id="alan-intro-star">' +
              '<svg viewBox="0 0 240 240" fill="none" xmlns="http://www.w3.org/2000/svg">' +
                '<circle cx="120" cy="120" r="106" stroke="currentColor" stroke-width="1.2" stroke-dasharray="4 7" opacity="0.6"/>' +
                '<circle cx="120" cy="120" r="76" stroke="currentColor" stroke-width="1" opacity="0.4"/>' +
                '<path d="M120 8 L130 86 L184 30 L144 98 L226 76 L154 116 L232 120 L154 124 L226 164 L144 142 L184 210 L130 154 L120 232 L110 154 L56 210 L96 142 L14 164 L86 124 L8 120 L86 116 L14 76 L96 98 L56 30 L110 86 Z" fill="currentColor" fill-opacity="0.18" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>' +
              '</svg>' +
            '</div>' +
            '<div id="alan-intro-emblem">' +
              '<div class="alan-emblem-card">' +
                '<span class="alan-emblem-dot"></span>' +
                '<span class="alan-emblem-code">IR → Lowering → ASM</span>' +
              '</div>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '<a href="#alan-about" id="alan-scroll-cue" data-router-ignore="true">' +
          '<span>Scroll to explore</span>' +
          '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>' +
        '</a>';

      var cue = intro.querySelector("#alan-scroll-cue");
      if (cue) {
        cue.addEventListener("click", function (e) {
          e.preventDefault();
          var target = document.getElementById("alan-about");
          if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
        });
      }

      center.insertBefore(intro, article);
    }

    if (!document.getElementById("alan-about")) {
      var aboutSec = buildAboutSection();
      center.insertBefore(aboutSec, article);
    }

    if (!md.querySelector("#alan-directories")) {
      var headings = Array.from(md.querySelectorAll("h2"));
      var dirSection = document.createElement("section");
      dirSection.id = "alan-directories";
      dirSection.setAttribute("aria-label", "Directories");

      if (headings.length > 0) {
        headings[0].classList.add("alan-moved-intro");
      }

      var headerWrap = document.createElement("div");
      headerWrap.className = "alan-dir-header";
      headerWrap.innerHTML =
        '<h2 class="alan-section-title">Directories</h2>' +
        '<p class="alan-section-subtitle">按专题目录浏览体系结构、编译器、高性能计算、大模型笔记与实用指南</p>';
      dirSection.appendChild(headerWrap);

      function buildCardFromLi(li) {
        var anchor = li.querySelector("a");
        if (!anchor) return null;
        var href = anchor.getAttribute("href") || "./";
        var dirTitle = (anchor.textContent || "").trim();

        var fullExtra = "";
        Array.from(li.childNodes).forEach(function (node) {
          if (node.nodeType === 3) {
            var txt = (node.textContent || "").trim();
            if (txt) {
              fullExtra += txt.replace(/^[：:]\\s*/, "");
            }
          }
        });

        var countLabel = "";
        var descText = fullExtra;
        var countMatch = fullExtra.match(/（([^（）]+)）\\s*$/);
        if (countMatch) {
          countLabel = countMatch[1];
          descText = fullExtra.slice(0, countMatch.index).trim();
        }

        var meta = getDirCardMeta(dirTitle, href);
        var card = document.createElement("article");
        card.className = "alan-dir-card";

        var artDiv = document.createElement("div");
        artDiv.className = "alan-dir-art";
        artDiv.setAttribute("aria-hidden", "true");
        artDiv.innerHTML = meta.svg;

        var bodyDiv = document.createElement("div");
        bodyDiv.className = "alan-dir-body";

        var kicker = document.createElement("p");
        kicker.className = "alan-dir-kicker";
        kicker.textContent = meta.kicker;

        var hTitle = document.createElement("h3");
        hTitle.className = "alan-dir-title";
        var titleLink = document.createElement("a");
        titleLink.href = href;
        titleLink.textContent = dirTitle;
        hTitle.appendChild(titleLink);

        var pDesc = document.createElement("p");
        pDesc.className = "alan-dir-desc";
        pDesc.textContent = descText || "专题笔记目录";

        var tagList = document.createElement("ul");
        tagList.className = "alan-dir-tags";
        if (countLabel) {
          var countLi = document.createElement("li");
          countLi.className = "alan-dir-tag-primary";
          countLi.textContent = countLabel;
          tagList.appendChild(countLi);
        }
        meta.tags.forEach(function (t) {
          var tLi = document.createElement("li");
          tLi.textContent = t;
          tagList.appendChild(tLi);
        });

        var cta = document.createElement("a");
        cta.className = "alan-dir-cta";
        cta.href = href;
        cta.textContent = "浏览目录 →";

        bodyDiv.appendChild(kicker);
        bodyDiv.appendChild(hTitle);
        bodyDiv.appendChild(pDesc);
        bodyDiv.appendChild(tagList);
        bodyDiv.appendChild(cta);

        card.appendChild(artDiv);
        card.appendChild(bodyDiv);
        return card;
      }

      var h3s = Array.from(md.querySelectorAll("h3"));
      if (h3s.length > 0) {
        h3s.forEach(function (h3) {
          var next = h3.nextElementSibling;
          if (!next || next.tagName !== "UL") return;

          var secName = (h3.textContent || "").trim();
          var items = Array.from(next.querySelectorAll("li"));
          if (items.length === 0) return;

          var groupTitle = document.createElement("div");
          groupTitle.className = "alan-dir-group-label";
          groupTitle.textContent = secName;
          dirSection.appendChild(groupTitle);

          var grid = document.createElement("div");
          grid.className = items.length >= 3 ? "alan-dir-grid" : "alan-dir-grid alan-dir-grid-compact";
          items.forEach(function (li) {
            var card = buildCardFromLi(li);
            if (card) grid.appendChild(card);
          });

          dirSection.appendChild(grid);
          h3.classList.add("alan-moved-intro");
          next.classList.add("alan-moved-intro");
        });
      } else {
        var directLists = Array.from(md.querySelectorAll("ul"));
        directLists.forEach(function (ul) {
          var items = Array.from(ul.querySelectorAll("li"));
          if (items.length === 0) return;
          var grid = document.createElement("div");
          grid.className = items.length >= 3 ? "alan-dir-grid" : "alan-dir-grid alan-dir-grid-compact";
          items.forEach(function (li) {
            var card = buildCardFromLi(li);
            if (card) grid.appendChild(card);
          });
          dirSection.appendChild(grid);
          ul.classList.add("alan-moved-intro");
        });
      }

      md.appendChild(dirSection);
    }

    var pageFooter = center.querySelector(".page-footer");
    if (pageFooter && pageFooter.querySelector(".graph") && !pageFooter.querySelector(".alan-graph-heading")) {
      pageFooter.id = "alan-graph";
      var gTitle = document.createElement("h2");
      gTitle.className = "alan-section-title alan-graph-heading";
      gTitle.textContent = "Knowledge Graph";
      pageFooter.insertBefore(gTitle, pageFooter.firstChild);
    }

    document.body.classList.add("alan-enhanced");
    updateScrollEffects();
  }

  function dedupeArticleHeading() {
    if (!document.body) return;
    var slug = document.body.getAttribute("data-slug");
    if (slug === "index") return;

    var titleEl = document.querySelector(".page-header h1.article-title");
    var article = document.querySelector(".center article");
    var md = article ? article.querySelector(".markdown-rendered") || article : null;
    if (!titleEl || !md) return;

    var firstHeading = md.firstElementChild;
    if (!firstHeading || firstHeading.tagName !== "H1") return;

    var normalizeHeadingText = function (el) {
      var clone = el.cloneNode(true);
      clone.querySelectorAll('a[role="anchor"]').forEach(function (a) {
        a.remove();
      });
      return (clone.textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
    };

    var titleText = normalizeHeadingText(titleEl);
    var headingText = normalizeHeadingText(firstHeading);
    if (!titleText || titleText !== headingText) return;

    firstHeading.classList.add("alan-duplicate-h1");
    var headingId = firstHeading.getAttribute("id");
    document.querySelectorAll(".toc-content li").forEach(function (li) {
      var anchor = li.querySelector("a");
      if (!anchor) return;
      var dataFor = anchor.getAttribute("data-for");
      var tocText = (anchor.textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
      if ((headingId && dataFor === headingId) || tocText === headingText) {
        li.classList.add("alan-duplicate-toc-item");
      }
    });
  }

  function initAlan() {
    ensureReadingProgress();
    bindGlobalScroll();
    enhanceHomepage();
    dedupeArticleHeading();
  }

  window.__alanRunInit = initAlan;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAlan);
  } else {
    initAlan();
  }
  document.addEventListener("nav", initAlan);
})();
`;
export default (() => {
  const Head: QuartzComponent = ({
    cfg,
    fileData,
    externalResources,
    ctx,
  }: QuartzComponentProps) => {
    const titleSuffix = cfg.pageTitleSuffix ?? ""
    const title =
      (fileData.frontmatter?.title ?? i18n(cfg.locale).propertyDefaults.title) + titleSuffix
    const description =
      fileData.frontmatter?.socialDescription ??
      fileData.frontmatter?.description ??
      unescapeHTML(fileData.description?.trim() ?? i18n(cfg.locale).propertyDefaults.description)

    const { css, js, additionalHead } = externalResources

    const url = new URL(`https://${cfg.baseUrl ?? "example.com"}`)
    const path = url.pathname as FullSlug
    const baseDir = fileData.slug === "404" ? path : pathToRoot(fileData.slug!)
    const iconPath = joinSegments(baseDir, "static/icon.png")

    // Url of current page
    const socialUrl =
      fileData.slug === "404" ? url.toString() : joinSegments(url.toString(), fileData.slug!)

    const usesCustomOgImage = ctx.cfg.plugins.emitters.some(
      (e) => e.name === CustomOgImagesEmitterName,
    )
    const ogImageDefaultPath = `https://${cfg.baseUrl}/static/og-image.png`

    const coreStylesheet = css[0]?.content
    const coreScript = js.find(
      (r) => r.loadTime === "beforeDOMReady" && r.contentType === "external",
    )

    return (
      <head>
        <title>{title}</title>
        <meta charSet="utf-8" />
        {coreStylesheet && <link rel="preload" href={coreStylesheet} as="style" />}
        {/* Theme palette pre-initialization to avoid flash */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{const p=localStorage.getItem("theme-palette")||"alan";document.documentElement.setAttribute("theme-palette",p)}catch(e){}`,
          }}
        />
        {coreScript && coreScript.contentType === "external" && (
          <link rel="preload" href={coreScript.src} as="script" />
        )}
        {cfg.theme.cdnCaching && cfg.theme.fontOrigin === "googleFonts" && (
          <>
            <link rel="preconnect" href="https://fonts.googleapis.com" />
            <link rel="preconnect" href="https://fonts.gstatic.com" />
            <link rel="stylesheet" href={googleFontHref(cfg.theme)} />
            <link
              rel="stylesheet"
              href="https://fonts.googleapis.com/css2?family=Smythe&display=swap"
            />
            {cfg.theme.typography.title && (
              <link rel="stylesheet" href={googleFontSubsetHref(cfg.theme, cfg.pageTitle)} />
            )}
          </>
        )}
        <link rel="preconnect" href="https://cdnjs.cloudflare.com" crossOrigin="anonymous" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />

        <meta name="og:site_name" content={cfg.pageTitle}></meta>
        <meta property="og:title" content={title} />
        <meta property="og:type" content="website" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content={title} />
        <meta name="twitter:description" content={description} />
        <meta property="og:description" content={description} />
        <meta property="og:image:alt" content={description} />

        {!usesCustomOgImage && (
          <>
            <meta property="og:image" content={ogImageDefaultPath} />
            <meta property="og:image:url" content={ogImageDefaultPath} />
            <meta name="twitter:image" content={ogImageDefaultPath} />
            <meta
              property="og:image:type"
              content={`image/${getFileExtension(ogImageDefaultPath) ?? "png"}`}
            />
          </>
        )}

        {cfg.baseUrl && (
          <>
            <meta property="twitter:domain" content={cfg.baseUrl}></meta>
            <meta property="og:url" content={socialUrl}></meta>
            <meta property="twitter:url" content={socialUrl}></meta>
          </>
        )}

        <link rel="icon" href={iconPath} />
        <meta name="description" content={description} />
        <meta name="generator" content="Quartz" />

        {css.map((resource) => CSSResourceToStyleElement(resource, true))}
        {js
          .filter((resource) => resource.loadTime === "beforeDOMReady")
          .map((res) => JSResourceToScriptElement(res, true))}
        {additionalHead.map((resource) => {
          if (typeof resource === "function") {
            return resource(fileData)
          } else {
            return resource
          }
        })}
        {/* Theme Palette Switcher & Alan Editorial Enhancements */}
        <script
          dangerouslySetInnerHTML={{
            __html: ALAN_CLIENT_SCRIPT,
          }}
        />
      </head>
    )
  }

  return Head
}) satisfies QuartzComponentConstructor
