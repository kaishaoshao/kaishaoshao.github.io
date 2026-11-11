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

  var HOME_SLIDES = [
    { id: "alan-intro", label: "Intro", hash: "#alan-intro" },
    { id: "alan-about", label: "About", hash: "#alan-about" },
    { id: "alan-directories", label: "Directories", hash: "#alan-directories" },
    { id: "alan-graph", label: "Graph", hash: "#alan-graph" },
    { id: "alan-notes", label: "Notes", hash: "#alan-notes" }
  ];

  function resolveInitialHomeSlide() {
    var hash = (window.location.hash || "").toLowerCase();
    for (var i = 0; i < HOME_SLIDES.length; i++) {
      var h = HOME_SLIDES[i].hash.toLowerCase();
      var shortH = "#" + HOME_SLIDES[i].label.toLowerCase();
      if (hash === h || hash === shortH) return i;
    }
    return 0;
  }

  function syncHomeSlideUI(idx) {
    var total = HOME_SLIDES.length;
    var safeIdx = Math.max(0, Math.min(total - 1, idx));
    window.__alanHomeSlide = safeIdx;

    document.querySelectorAll("#alan-menu-items a[data-alan-slide]").forEach(function (a) {
      var sIdx = parseInt(a.getAttribute("data-alan-slide") || "0", 10);
      if (sIdx === safeIdx) {
        a.classList.add("active");
      } else {
        a.classList.remove("active");
      }
    });

    document.querySelectorAll("#alan-stage-dots button[data-alan-slide]").forEach(function (btn) {
      var sIdx = parseInt(btn.getAttribute("data-alan-slide") || "0", 10);
      if (sIdx === safeIdx) {
        btn.classList.add("is-active");
        btn.setAttribute("aria-selected", "true");
      } else {
        btn.classList.remove("is-active");
        btn.setAttribute("aria-selected", "false");
      }
    });

    var prevBtn = document.getElementById("alan-stage-prev");
    if (prevBtn) {
      prevBtn.disabled = safeIdx <= 0;
      var prevMeta = safeIdx > 0 ? HOME_SLIDES[safeIdx - 1] : null;
      prevBtn.setAttribute("title", prevMeta ? "向左：" + prevMeta.label : "已是第一屏");
      prevBtn.setAttribute("aria-label", prevMeta ? "上一屏：" + prevMeta.label : "已是第一屏");
    }

    var nextBtn = document.getElementById("alan-stage-next");
    if (nextBtn) {
      nextBtn.disabled = safeIdx >= total - 1;
      var nextMeta = safeIdx < total - 1 ? HOME_SLIDES[safeIdx + 1] : null;
      nextBtn.setAttribute("title", nextMeta ? "向右：" + nextMeta.label : "已是最后一屏");
      nextBtn.setAttribute("aria-label", nextMeta ? "下一屏：" + nextMeta.label : "已是最后一屏");
    }

    var fill = document.querySelector("#alan-reading-progress .alan-progress-fill");
    if (fill) {
      fill.style.width = (((safeIdx + 1) / total) * 100).toFixed(2) + "%";
    }

    var star = document.getElementById("alan-intro-star");
    if (star) {
      var deg = -(safeIdx * 45);
      star.style.transform = "rotate(" + deg + "deg)";
    }
  }

  function goToHomeSlide(idx, animate) {
    var total = HOME_SLIDES.length;
    var safeIdx = Math.max(0, Math.min(total - 1, idx));
    var stage = document.getElementById("alan-stage");
    syncHomeSlideUI(safeIdx);
    if (stage) {
      var targetLeft = safeIdx * stage.clientWidth;
      stage.scrollTo({ left: targetLeft, behavior: animate === false ? "auto" : "smooth" });
      if (safeIdx === 3) {
        window.requestAnimationFrame(function () {
          var gc = stage.querySelector("#alan-graph .graph-container");
          var cv = gc ? gc.querySelector("canvas") : null;
          if (gc && (!cv || cv.width === 0 || Math.abs(cv.getBoundingClientRect().width - gc.clientWidth) > 24)) {
            document.dispatchEvent(new CustomEvent("render"));
          }
        });
      }
    }
    var targetHash = safeIdx === 0 ? "" : HOME_SLIDES[safeIdx].hash;
    try {
      if (window.history && window.history.replaceState) {
        var nextUrl = targetHash
          ? window.location.pathname + window.location.search + targetHash
          : window.location.pathname + window.location.search;
        if (window.location.href !== window.location.origin + nextUrl) {
          window.history.replaceState(null, "", nextUrl);
        }
      }
    } catch (e) {}
  }

  function mountTopMenu(isHome) {
    var existing = document.getElementById("alan-top-menu");
    if (!isHome) {
      if (existing) existing.remove();
      return;
    }
    if (existing) {
      syncTopThemeBtn();
      syncHomeSlideUI(window.__alanHomeSlide || 0);
      return;
    }

    var nav = document.createElement("nav");
    nav.id = "alan-top-menu";
    nav.setAttribute("aria-label", "Primary navigation");
    nav.innerHTML =
      '<div class="alan-menu-inner">' +
        '<a href="#alan-intro" class="alan-menu-brand" data-router-ignore="true" data-alan-slide="0">kaishaoshao</a>' +
        '<ul id="alan-menu-items">' +
          '<li><a href="#alan-intro" data-router-ignore="true" data-alan-slide="0" class="active">Intro</a></li>' +
          '<li><a href="#alan-about" data-router-ignore="true" data-alan-slide="1">About</a></li>' +
          '<li><a href="#alan-directories" data-router-ignore="true" data-alan-slide="2">Directories</a></li>' +
          '<li><a href="#alan-graph" data-router-ignore="true" data-alan-slide="3">Graph</a></li>' +
          '<li><a href="#alan-notes" data-router-ignore="true" data-alan-slide="4">Notes</a></li>' +
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

    nav.querySelectorAll("[data-alan-slide]").forEach(function (link) {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        var sIdx = parseInt(link.getAttribute("data-alan-slide") || "0", 10);
        goToHomeSlide(sIdx, true);
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
    if (document.body && document.body.getAttribute("data-slug") === "index") {
      syncHomeSlideUI(window.__alanHomeSlide || 0);
      return;
    }
    var fill = document.querySelector("#alan-reading-progress .alan-progress-fill");
    var scrollTop = window.scrollY || document.documentElement.scrollTop || 0;
    var docHeight = document.documentElement.scrollHeight - window.innerHeight;
    if (fill) {
      var ratio = docHeight > 0 ? Math.min(1, Math.max(0, scrollTop / docHeight)) : 0;
      fill.style.width = (ratio * 100).toFixed(2) + "%";
    }
  }

  function bindGlobalScroll() {
    if (window.__alanScrollBound) return;
    window.__alanScrollBound = true;
    var ticking = false;
    window.addEventListener(
      "scroll",
      function () {
        if (document.body && document.body.getAttribute("data-slug") === "index") return;
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

    window.addEventListener("resize", function () {
      if (!document.body || document.body.getAttribute("data-slug") !== "index") return;
      var stage = document.getElementById("alan-stage");
      if (stage) {
        var idx = window.__alanHomeSlide || 0;
        stage.scrollTo({ left: idx * stage.clientWidth, behavior: "auto" });
      }
    });

    window.addEventListener("hashchange", function () {
      if (!document.body || document.body.getAttribute("data-slug") !== "index") return;
      goToHomeSlide(resolveInitialHomeSlide(), true);
    });

    window.addEventListener("keydown", function (e) {
      if (!document.body || document.body.getAttribute("data-slug") !== "index") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      var activeEl = document.activeElement;
      if (
        activeEl &&
        (activeEl.tagName === "INPUT" ||
          activeEl.tagName === "TEXTAREA" ||
          activeEl.tagName === "SELECT" ||
          activeEl.isContentEditable)
      ) {
        return;
      }
      var searchSpace = document.querySelector(".search-container.active");
      if (searchSpace) return;
      var globalGraphActive = document.querySelector(".global-graph-outer.active");
      if (globalGraphActive) return;

      var cur = window.__alanHomeSlide || 0;
      if (e.key === "ArrowLeft") {
        if (cur > 0) {
          e.preventDefault();
          goToHomeSlide(cur - 1, true);
        }
      } else if (e.key === "ArrowRight") {
        if (cur < HOME_SLIDES.length - 1) {
          e.preventDefault();
          goToHomeSlide(cur + 1, true);
        }
      }
    });
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
    var inner = document.createElement("div");
    inner.className = "alan-slide-inner alan-about-inner";
    inner.innerHTML =
      '<h2 class="alan-section-title">About</h2>' +
      '<p class="alan-section-subtitle">Keep it simple · 第一性原理拆解计算机系统与编译技术</p>' +
      '<div class="alan-about-grid">' +
        '<article class="alan-about-card">' +
          '<div class="alan-about-art" aria-hidden="true">' +
            '<svg viewBox="0 0 160 120" fill="none" xmlns="http://www.w3.org/2000/svg">' +
              '<circle cx="80" cy="60" r="44" stroke="currentColor" stroke-width="1.8" stroke-dasharray="4 5" opacity="0.65"/>' +
              '<circle cx="80" cy="60" r="30" stroke="var(--secondary)" stroke-width="2" fill="var(--secondary)" fill-opacity="0.1"/>' +
              '<path d="M80 22l9 29 29 9-29 9-9 29-9-29-29-9 29-9 9-29Z" stroke="var(--secondary)" stroke-width="1.8" fill="var(--secondary)" fill-opacity="0.18" stroke-linejoin="round"/>' +
              '<circle cx="80" cy="60" r="4.5" fill="var(--dark)"/>' +
            '</svg>' +
          '</div>' +
          '<div class="alan-about-content">' +
            '<h3 class="alan-about-title">Explorer</h3>' +
            '<p class="alan-about-text">保持好奇心的底层技术探索者，习惯用第一性原理把复杂的系统拆解清楚，持续记录对计算机体系结构、编译技术与系统性能的思考。</p>' +
          '</div>' +
        '</article>' +
        '<article class="alan-about-card">' +
          '<div class="alan-about-art" aria-hidden="true">' +
            '<svg viewBox="0 0 160 120" fill="none" xmlns="http://www.w3.org/2000/svg">' +
              '<rect x="20" y="20" width="120" height="80" rx="12" stroke="currentColor" stroke-width="1.8" fill="currentColor" fill-opacity="0.06"/>' +
              '<rect x="34" y="34" width="38" height="20" rx="5" stroke="var(--secondary)" stroke-width="1.8" fill="var(--secondary)" fill-opacity="0.18"/>' +
              '<rect x="88" y="34" width="38" height="20" rx="5" stroke="currentColor" stroke-width="1.8"/>' +
              '<rect x="34" y="64" width="92" height="20" rx="5" stroke="var(--tertiary)" stroke-width="1.8" fill="var(--tertiary)" fill-opacity="0.16"/>' +
              '<path d="M72 44h16M80 54v10" stroke="var(--secondary)" stroke-width="1.8" stroke-linecap="round"/>' +
            '</svg>' +
          '</div>' +
          '<div class="alan-about-content">' +
            '<h3 class="alan-about-title">Compilers &amp; Systems</h3>' +
            '<p class="alan-about-text">研究与实践围绕 LLVM / MLIR 多级中间表示、TableGen 与代码生成、程序性能优化（Cache 局部性与矩阵乘法调优）、RISC-V RVV 向量扩展与 LLM 底层系统展开。</p>' +
          '</div>' +
        '</article>' +
        '<article class="alan-about-card">' +
          '<div class="alan-about-art" aria-hidden="true">' +
            '<svg viewBox="0 0 160 120" fill="none" xmlns="http://www.w3.org/2000/svg">' +
              '<rect x="34" y="16" width="92" height="88" rx="12" stroke="currentColor" stroke-width="1.8" fill="currentColor" fill-opacity="0.06"/>' +
              '<circle cx="80" cy="28" r="4.5" fill="var(--light)" stroke="currentColor" stroke-width="1.6"/>' +
              '<path d="M50 48h60M50 64h52M50 80h40" stroke="var(--secondary)" stroke-width="2.2" stroke-linecap="round"/>' +
              '<path d="M104 84l14-14 5 5-14 14-7 2 2-7Z" stroke="currentColor" stroke-width="1.8" fill="var(--secondary)" fill-opacity="0.25" stroke-linejoin="round"/>' +
            '</svg>' +
          '</div>' +
          '<div class="alan-about-content">' +
            '<h3 class="alan-about-title">Why This Garden?</h3>' +
            '<p class="alan-about-text">看过的论文、读过的源码和踩过的坑若不系统梳理很快遗忘。这里按专题沉淀成可检索的数字花园，只求脉络清晰、随时可查，也给同路人提供参考。</p>' +
          '</div>' +
        '</article>' +
      '</div>' +
      '<div class="alan-about-footer-cta">' +
        '<a href="#alan-directories" class="alan-flat-btn" data-router-ignore="true" data-alan-slide="2">Explore Directories →</a>' +
      '</div>';

    var ctaBtn = inner.querySelector('[data-alan-slide="2"]');
    if (ctaBtn) {
      ctaBtn.addEventListener("click", function (e) {
        e.preventDefault();
        goToHomeSlide(2, true);
      });
    }
    return inner;
  }

  function buildNotesPortalSection() {
    var inner = document.createElement("div");
    inner.className = "alan-slide-inner alan-notes-inner";
    inner.innerHTML =
      '<h2 class="alan-section-title">Notes</h2>' +
      '<p class="alan-section-subtitle">体系结构、编译原理与高性能计算笔记库——点击下方入口直达完整专题目录</p>' +
      '<div class="alan-notes-portal-card">' +
        '<div class="alan-notes-portal-art" aria-hidden="true">' +
          '<svg viewBox="0 0 180 140" fill="none" xmlns="http://www.w3.org/2000/svg">' +
            '<rect x="26" y="22" width="44" height="96" rx="8" stroke="currentColor" stroke-width="1.9" fill="currentColor" fill-opacity="0.06"/>' +
            '<rect x="68" y="14" width="48" height="104" rx="8" stroke="var(--secondary)" stroke-width="2.2" fill="var(--secondary)" fill-opacity="0.14"/>' +
            '<rect x="114" y="24" width="42" height="94" rx="8" stroke="var(--tertiary)" stroke-width="1.9" fill="var(--tertiary)" fill-opacity="0.1"/>' +
            '<path d="M36 44h24M36 60h18M78 40h28M78 56h22M78 72h26M124 46h22M124 62h18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' +
            '<circle cx="92" cy="96" r="5" fill="var(--secondary)"/>' +
          '</svg>' +
        '</div>' +
        '<div class="alan-notes-portal-body">' +
          '<p class="alan-dir-kicker">NOTES · DIGITAL GARDEN</p>' +
          '<h3 class="alan-notes-portal-title">进入专题笔记目录</h3>' +
          '<p class="alan-notes-portal-desc">为保持主页简洁，各子专题与具体文章均统一收纳在目录页内：包含计算机体系结构（Arch）、LLVM / MLIR 编译器、程序性能优化（Opt）、RISC-V RVV 向量扩展与 LLM 底层实践，共 6 个子目录、10 篇技术笔记。</p>' +
          '<ul class="alan-dir-tags">' +
            '<li class="alan-dir-tag-primary">6 个子目录 · 共 10 篇</li>' +
            '<li>Arch · LLM</li>' +
            '<li>LLVM · MLIR</li>' +
            '<li>Opt · RISCV</li>' +
          '</ul>' +
          '<div class="alan-notes-portal-actions">' +
            '<a href="./notes/" class="alan-flat-btn">进入 Notes 详细目录 →</a>' +
            '<a href="./tutorials/" class="alan-outline-btn">Tutorials</a>' +
            '<a href="./skills/" class="alan-outline-btn">Skills</a>' +
          '</div>' +
        '</div>' +
      '</div>';
    return inner;
  }

  function bindStageSwipe(stage) {
    if (!stage || stage.__alanSwipeBound) return;
    stage.__alanSwipeBound = true;

    var touchStartX = 0;
    var touchStartY = 0;
    var touchIgnore = false;

    stage.addEventListener(
      "touchstart",
      function (e) {
        if (e.touches.length !== 1) return;
        var target = e.target;
        touchIgnore = Boolean(target && target.closest && target.closest(".graph-outer, .global-graph-outer"));
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
      },
      { passive: true }
    );

    stage.addEventListener(
      "touchend",
      function (e) {
        if (touchIgnore || !e.changedTouches || e.changedTouches.length === 0) return;
        var dx = e.changedTouches[0].clientX - touchStartX;
        var dy = e.changedTouches[0].clientY - touchStartY;
        if (Math.abs(dx) > 48 && Math.abs(dx) > Math.abs(dy) * 1.25) {
          var cur = window.__alanHomeSlide || 0;
          if (dx < 0 && cur < HOME_SLIDES.length - 1) {
            goToHomeSlide(cur + 1, true);
          } else if (dx > 0 && cur > 0) {
            goToHomeSlide(cur - 1, true);
          }
        }
      },
      { passive: true }
    );

    var wheelLockedUntil = 0;
    stage.addEventListener(
      "wheel",
      function (e) {
        var target = e.target;
        if (target && target.closest && target.closest(".graph-outer, .global-graph-outer")) return;
        if (Math.abs(e.deltaX) > Math.abs(e.deltaY) && Math.abs(e.deltaX) > 26) {
          e.preventDefault();
          var now = Date.now();
          if (now < wheelLockedUntil) return;
          wheelLockedUntil = now + 450;
          var cur = window.__alanHomeSlide || 0;
          if (e.deltaX > 0 && cur < HOME_SLIDES.length - 1) {
            goToHomeSlide(cur + 1, true);
          } else if (e.deltaX < 0 && cur > 0) {
            goToHomeSlide(cur - 1, true);
          }
        }
      },
      { passive: false }
    );
  }

  function enhanceHomepage() {
    if (!document.body) return;
    var slug = document.body.getAttribute("data-slug");
    var isHome = slug === "index";
    mountTopMenu(isHome);
    mountPalettePicker(isHome);

    if (!isHome) {
      document.body.classList.remove("alan-enhanced");
      updateScrollEffects();
      return;
    }

    var center = document.querySelector(".center");
    var article = center ? center.querySelector("article") : null;
    var md = article ? article.querySelector(".markdown-rendered") || article : null;
    if (!center || !article || !md) return;

    var stage = document.getElementById("alan-stage");
    if (!stage) {
      stage = document.createElement("section");
      stage.id = "alan-stage";
      stage.setAttribute("aria-label", "Homepage Horizontal Sections");

      var track = document.createElement("div");
      track.id = "alan-track";

      /* Slide 0: Intro */
      var slide0 = document.createElement("section");
      slide0.className = "alan-slide";
      slide0.id = "alan-intro";
      slide0.setAttribute("data-slide-idx", "0");
      slide0.setAttribute("aria-label", "Introduction");
      slide0.innerHTML =
        '<div class="alan-slide-inner alan-intro-slide">' +
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
          '<a href="#alan-about" id="alan-scroll-cue" data-router-ignore="true" data-alan-slide="1">' +
            '<span>Explore About</span>' +
            '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>' +
          '</a>' +
        '</div>';

      var cue = slide0.querySelector("#alan-scroll-cue");
      if (cue) {
        cue.addEventListener("click", function (e) {
          e.preventDefault();
          goToHomeSlide(1, true);
        });
      }
      track.appendChild(slide0);

      /* Slide 1: About */
      var slide1 = document.createElement("section");
      slide1.className = "alan-slide";
      slide1.id = "alan-about";
      slide1.setAttribute("data-slide-idx", "1");
      slide1.setAttribute("aria-label", "About");
      slide1.appendChild(buildAboutSection());
      track.appendChild(slide1);

      /* Slide 2: Directories */
      var slide2 = document.createElement("section");
      slide2.className = "alan-slide";
      slide2.id = "alan-directories";
      slide2.setAttribute("data-slide-idx", "2");
      slide2.setAttribute("aria-label", "Directories");

      var dirInner = document.createElement("div");
      dirInner.className = "alan-slide-inner alan-directories-inner";
      dirInner.innerHTML =
        '<div class="alan-dir-header">' +
          '<h2 class="alan-section-title">Directories</h2>' +
          '<p class="alan-section-subtitle">按专题目录浏览体系结构、编译器、高性能计算、大模型笔记与实用指南</p>' +
        '</div>';

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
        dirInner.appendChild(grid);
      });

      slide2.appendChild(dirInner);
      track.appendChild(slide2);

      /* Slide 3: Graph */
      var slide3 = document.createElement("section");
      slide3.className = "alan-slide";
      slide3.id = "alan-graph-slide";
      slide3.setAttribute("data-slide-idx", "3");
      slide3.setAttribute("aria-label", "Knowledge Graph");

      var graphInner = document.createElement("div");
      graphInner.className = "alan-slide-inner alan-graph-inner";

      var pageFooter = center.querySelector(".page-footer");
      if (pageFooter && pageFooter.querySelector(".graph")) {
        pageFooter.id = "alan-graph";
        if (!pageFooter.querySelector(".alan-graph-heading")) {
          var gHeader = document.createElement("div");
          gHeader.className = "alan-graph-header";
          gHeader.innerHTML =
            '<h2 class="alan-section-title alan-graph-heading">Knowledge Graph</h2>' +
            '<p class="alan-section-subtitle alan-graph-subtitle">全站目录、文章与标签关系网络（支持节点拖拽、滚轮缩放与全屏展开）</p>';
          pageFooter.insertBefore(gHeader, pageFooter.firstChild);
        }
        graphInner.appendChild(pageFooter);
      }
      slide3.appendChild(graphInner);
      track.appendChild(slide3);

      /* Slide 4: Notes Portal */
      var slide4 = document.createElement("section");
      slide4.className = "alan-slide";
      slide4.id = "alan-notes";
      slide4.setAttribute("data-slide-idx", "4");
      slide4.setAttribute("aria-label", "Notes");
      slide4.appendChild(buildNotesPortalSection());
      track.appendChild(slide4);

      stage.appendChild(track);

      /* Left / Right Stage Controls + Bottom Slide Pills */
      var prevCtrl = document.createElement("button");
      prevCtrl.type = "button";
      prevCtrl.id = "alan-stage-prev";
      prevCtrl.className = "alan-stage-arrow alan-stage-prev";
      prevCtrl.innerHTML =
        '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>';
      prevCtrl.addEventListener("click", function () {
        goToHomeSlide((window.__alanHomeSlide || 0) - 1, true);
      });

      var nextCtrl = document.createElement("button");
      nextCtrl.type = "button";
      nextCtrl.id = "alan-stage-next";
      nextCtrl.className = "alan-stage-arrow alan-stage-next";
      nextCtrl.innerHTML =
        '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>';
      nextCtrl.addEventListener("click", function () {
        goToHomeSlide((window.__alanHomeSlide || 0) + 1, true);
      });

      var dotsNav = document.createElement("div");
      dotsNav.id = "alan-stage-dots";
      dotsNav.setAttribute("role", "tablist");
      dotsNav.setAttribute("aria-label", "页面横向切换导航");
      HOME_SLIDES.forEach(function (s, idx) {
        var dotBtn = document.createElement("button");
        dotBtn.type = "button";
        dotBtn.className = "alan-stage-dot" + (idx === 0 ? " is-active" : "");
        dotBtn.setAttribute("role", "tab");
        dotBtn.setAttribute("data-alan-slide", String(idx));
        dotBtn.setAttribute("aria-selected", idx === 0 ? "true" : "false");
        dotBtn.innerHTML = '<span class="alan-dot-pip"></span><span class="alan-dot-label">' + s.label + '</span>';
        dotBtn.addEventListener("click", function () {
          goToHomeSlide(idx, true);
        });
        dotsNav.appendChild(dotBtn);
      });

      stage.appendChild(prevCtrl);
      stage.appendChild(nextCtrl);
      stage.appendChild(dotsNav);

      article.classList.add("alan-moved-article");
      center.insertBefore(stage, article);
      bindStageSwipe(stage);

      var initialSlide = resolveInitialHomeSlide();
      window.requestAnimationFrame(function () {
        goToHomeSlide(initialSlide, false);
      });
    }

    document.body.classList.add("alan-enhanced");
    syncHomeSlideUI(window.__alanHomeSlide || 0);
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
