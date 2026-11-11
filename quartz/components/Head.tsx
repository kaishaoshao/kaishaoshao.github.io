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

  function mountPalettePicker() {
    if (document.getElementById("theme-palette-wrapper")) {
      updatePaletteMenu();
      return;
    }
    var darkBtn = document.querySelector(".darkmode");
    if (!darkBtn || !darkBtn.parentElement || !darkBtn.parentElement.parentElement) return;

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
    darkBtn.parentElement.parentElement.insertBefore(wrapper, darkBtn.parentElement.nextSibling);
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
      var deg = -(scrollTop * 0.14);
      var scale = Math.max(0.75, 1 - scrollTop / 1800);
      star.style.transform = "rotate(" + deg.toFixed(1) + "deg) scale(" + scale.toFixed(3) + ")";
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

  function enhanceHomepage() {
    if (!document.body) return;
    var slug = document.body.getAttribute("data-slug");
    if (slug !== "index") {
      document.body.classList.remove("alan-enhanced");
      return;
    }

    var center = document.querySelector(".center");
    var article = center ? center.querySelector("article") : null;
    var md = article ? article.querySelector(".markdown-rendered") || article : null;
    if (!center || !article || !md) return;

    if (!document.getElementById("alan-intro-hero")) {
      var introBriefHtml =
        "这里主要记录我在计算机体系结构、编译器、高性能计算、机器学习底层以及 LLM 大模型方面的学习笔记与探索。";
      var children = Array.from(md.children);
      for (var i = 0; i < children.length; i++) {
        if (children[i].tagName === "H2") break;
        if (children[i].tagName === "P" && children[i].textContent.trim().length > 0) {
          introBriefHtml = children[i].innerHTML;
          children[i].classList.add("alan-moved-intro");
          break;
        }
      }

      var hero = document.createElement("section");
      hero.id = "alan-intro-hero";
      hero.setAttribute("aria-label", "Introduction");
      hero.innerHTML =
        '<div class="alan-intro-left">' +
          '<div class="alan-intro-salutation">Hi, I\\'m</div>' +
          '<h1 class="alan-intro-name">kaishaoshao</h1>' +
          '<div class="alan-intro-tagline">I compile &amp; explore here</div>' +
          '<p class="alan-intro-brief">' + introBriefHtml + '</p>' +
          '<div class="alan-intro-topics">' +
            '<span class="alan-topic-chip">MLIR / TableGen</span>' +
            '<span class="alan-topic-chip">LLVM</span>' +
            '<span class="alan-topic-chip">HPC / Matrix</span>' +
            '<span class="alan-topic-chip">RISC-V RVV</span>' +
            '<span class="alan-topic-chip">LLM Systems</span>' +
          '</div>' +
          '<div class="alan-intro-actions">' +
            '<a href="#alan-archive" class="alan-pill-btn alan-pill-primary" data-router-ignore="true" data-alan-scroll="archive">Explore Notes</a>' +
            '<a href="./skills/compiler" class="alan-pill-btn alan-pill-secondary">Compiler Toolchain</a>' +
          '</div>' +
        '</div>' +
        '<div class="alan-intro-visual" aria-hidden="true">' +
          '<div id="alan-intro-star">' +
            '<svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg">' +
              '<g opacity="0.9">' +
                '<circle cx="100" cy="100" r="88" stroke="currentColor" stroke-width="1.2" stroke-dasharray="4 6" />' +
                '<circle cx="100" cy="100" r="62" stroke="currentColor" stroke-width="1" opacity="0.55" />' +
                '<path d="M100 6 L108 72 L152 24 L120 82 L188 64 L128 96 L194 100 L128 104 L188 136 L120 118 L152 176 L108 128 L100 194 L92 128 L48 176 L80 118 L12 136 L72 104 L6 100 L72 96 L12 64 L80 82 L48 24 L92 72 Z" fill="currentColor" fill-opacity="0.16" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" />' +
              '</g>' +
            '</svg>' +
          '</div>' +
          '<div id="alan-intro-emblem">' +
            '<div class="alan-emblem-card">' +
              '<span class="alan-emblem-dot"></span>' +
              '<span class="alan-emblem-code">IR → Lowering → ASM</span>' +
            '</div>' +
          '</div>' +
        '</div>';

      var exploreBtn = hero.querySelector('[data-alan-scroll="archive"]');
      if (exploreBtn) {
        exploreBtn.addEventListener("click", function (e) {
          e.preventDefault();
          var target = document.getElementById("alan-archive") || document.querySelector(".alan-card-deck");
          if (target) {
            target.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        });
      }

      center.insertBefore(hero, article);
    }

    if (!md.querySelector(".alan-card-deck")) {
      var headings = Array.from(md.querySelectorAll("h2"));
      if (headings.length > 0) {
        headings[0].classList.add("alan-section-heading");
        headings[0].id = "alan-archive";
      }

      var deck = document.createElement("div");
      deck.className = "alan-card-deck";

      var h3s = Array.from(md.querySelectorAll("h3"));
      var cardIdx = 0;
      h3s.forEach(function (h3) {
        var next = h3.nextElementSibling;
        if (!next || next.tagName !== "UL") return;
        cardIdx += 1;

        var rawTitle = (h3.textContent || "").trim();
        var lowerTitle = rawTitle.toLowerCase();
        var card = document.createElement("section");
        card.className = "alan-card";

        var meta = document.createElement("div");
        meta.className = "alan-card-kicker";
        var count = next.querySelectorAll("li").length;
        var isDirCard = Array.from(next.querySelectorAll("li a")).every(function (a) {
          return (a.getAttribute("href") || "").endsWith("/");
        });
        var unit = isDirCard
          ? count === 1
            ? " DIR"
            : " DIRS"
          : count === 1
            ? " ENTRY"
            : " ENTRIES";
        meta.textContent = "SECTION · 0" + cardIdx + " · " + count + unit;
        if (count >= 4) {
          card.classList.add("alan-card-wide");
        }

        h3.classList.add("alan-card-title");
        next.classList.add("alan-card-list");

        Array.from(next.querySelectorAll("li")).forEach(function (li) {
          var anchor = li.querySelector("a");
          if (!anchor) return;
          var extraText = "";
          Array.from(li.childNodes).forEach(function (node) {
            if (node.nodeType === 3) {
              var txt = (node.textContent || "").trim();
              if (txt) {
                extraText += txt.replace(/^[：:]\\s*/, "");
                node.textContent = "";
              }
            }
          });
          if (extraText) {
            var badge = document.createElement("span");
            badge.className = "alan-item-path";
            badge.textContent = extraText;
            li.appendChild(badge);
          }
        });

        card.appendChild(meta);
        card.appendChild(h3);
        card.appendChild(next);

        if (lowerTitle === "tutorials" || lowerTitle === "notes" || lowerTitle === "skills") {
          var footer = document.createElement("div");
          footer.className = "alan-card-footer";
          var cta = document.createElement("a");
          cta.className = "alan-card-cta";
          cta.href = "./" + lowerTitle + "/";
          cta.textContent = "Browse " + rawTitle + " →";
          footer.appendChild(cta);
          card.appendChild(footer);
        }

        deck.appendChild(card);
      });

      if (deck.children.length > 0) {
        if (headings.length > 0) {
          headings[0].insertAdjacentElement("afterend", deck);
        } else {
          md.appendChild(deck);
        }
      }
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
    mountPalettePicker();
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
