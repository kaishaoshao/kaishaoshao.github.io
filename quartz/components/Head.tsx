import { i18n } from "../i18n"
import { FullSlug, getFileExtension, joinSegments, pathToRoot } from "../util/path"
import { CSSResourceToStyleElement, JSResourceToScriptElement } from "../util/resources"
import { googleFontHref, googleFontSubsetHref } from "../util/theme"
import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"
import { unescapeHTML } from "../util/escape"
// Fallback emitter name when og-image plugin is disabled
const CustomOgImagesEmitterName = "custom-og-image";
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
            __html: `try{const p=localStorage.getItem("theme-palette")||"blue";document.documentElement.setAttribute("theme-palette",p)}catch(e){}`,
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
        {/* Theme Palette Switcher Client Script */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){const P=[{id:"blue",name:"科技极简蓝",swatch:"swatch-blue"},{id:"green",name:"数字花园绿",swatch:"swatch-green"},{id:"purple",name:"赛博曜石紫",swatch:"swatch-purple"},{id:"catppuccin",name:"猫咪暖色 (Mocha)",swatch:"swatch-catppuccin"}];function getP(){try{return localStorage.getItem("theme-palette")||"blue"}catch(e){return"blue"}}function setP(id){document.documentElement.setAttribute("theme-palette",id);try{localStorage.setItem("theme-palette",id)}catch(e){}updateM();window.dispatchEvent(new CustomEvent("theme-palette-change",{detail:{palette:id}}))}function updateM(){const cur=getP();document.querySelectorAll(".palette-option-btn").forEach(b=>{if(b.getAttribute("data-palette")===cur){b.classList.add("active")}else{b.classList.remove("active")}})}function mount(){if(document.getElementById("theme-palette-wrapper")){updateM();return}const d=document.querySelector(".darkmode");if(!d||!d.parentElement||!d.parentElement.parentElement)return;const w=document.createElement("div");w.id="theme-palette-wrapper";w.className="palette-picker-wrapper";w.style.cssText="flex-grow:0;flex-shrink:1;flex-basis:auto;order:0;align-self:center;justify-self:center;";const btn=document.createElement("button");btn.className="palette-toggle-btn";btn.setAttribute("aria-label","切换主题配色 (Palette)");btn.setAttribute("title","切换主题配色");btn.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/></svg>';const m=document.createElement("div");m.className="palette-menu hidden";P.forEach(p=>{const opt=document.createElement("button");opt.type="button";opt.className="palette-option-btn";opt.setAttribute("data-palette",p.id);opt.innerHTML='<span class="palette-swatch '+p.swatch+'"></span><span class="palette-name">'+p.name+'</span><span class="palette-check">✓</span>';opt.addEventListener("click",function(e){e.stopPropagation();setP(p.id);m.classList.add("hidden")});m.appendChild(opt)});btn.addEventListener("click",function(e){e.stopPropagation();m.classList.toggle("hidden")});document.addEventListener("click",function(e){if(!w.contains(e.target)){m.classList.add("hidden")}});w.appendChild(btn);w.appendChild(m);d.parentElement.parentElement.insertBefore(w,d.parentElement.nextSibling);updateM()}if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",mount)}else{mount()}document.addEventListener("nav",mount)})();`,
          }}
        />
      </head>
    )
  }

  return Head
}) satisfies QuartzComponentConstructor
