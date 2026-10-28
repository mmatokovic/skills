---
name: hugo-tailwind
description: >-
  Build and maintain Hugo static sites styled with Tailwind CSS v4 — blogs, docs sites and landing pages. Use when creating a Hugo site, adding Tailwind to Hugo, writing or fixing layouts, partials, shortcodes or render hooks, organising content and page bundles, processing images, upgrading an older Hugo site, or debugging a build (missing styles, template not picked up, "exec not allowed", unstyled classes). Covers the post-v0.146 template system (`layouts/_partials`, `home.html`, `page.html`), `css.TailwindCSS` with `hugo_stats.json`, and bep's `myhugofixer` upgrade guides. Trigger phrases: "hugo site", "hugo + tailwind", "hugo layout", "hugo partial", "shortcode", "page bundle", "hugo server", "upgrade hugo", "tailwind classes not applied in hugo".
---

# Hugo + Tailwind CSS

Build Hugo sites the way current Hugo documents them: the template system introduced in v0.146, and Tailwind v4 through Hugo's built-in `css.TailwindCSS` — no PostCSS config and no `tailwind.config.js`.

## Before the first change

1. **Check versions.** `hugo version` — this skill targets **v0.161+** (Tailwind via npm CLI; the standalone binary is no longer supported). Hugo Modules additionally need `go`; Tailwind needs `node` + `npm`.
2. **Old site?** If there is a `layouts/_default/`, `layouts/partials/` or `layouts/index.html`, the site predates v0.146. Upgrade first (below) — don't mix old and new layout names.
3. **Theme or project layouts?** Templates in the project's `layouts/` override the theme's file by file. Change the project, never edit a third-party theme under `themes/` or the module cache. If the theme is the user's own (a git submodule they commit to), change it in the theme repo instead of overriding it in the project.

## New site

```sh
hugo new site mysite --format toml
cd mysite
git init
npm init -y
npm install --save-dev tailwindcss @tailwindcss/cli @tailwindcss/typography
```

Then wire up Tailwind (`references/tailwind.md` §1) and create the minimum layouts:

```text
layouts/
├── baseof.html          # <html>, <head> with the CSS partial, {{ block "main" . }}
├── home.html            # home page
├── page.html            # regular content page
├── section.html         # section listing (/blog/)
├── taxonomy.html        # /tags/
├── term.html            # /tags/hugo/
└── _partials/
    ├── css.html
    ├── header.html
    └── footer.html
```

`list.html` and `single.html` work as fallbacks for all list and single pages; `all.html` is a catch-all. Details and lookup rules: `references/templates.md`.

## Everyday commands

```sh
hugo server -D                       # dev server with drafts, live reload
hugo new content blog/my-post.md     # from archetypes/blog.md or archetypes/default.md
hugo build --gc --minify             # production build into public/
hugo config                          # effective configuration — check what Hugo actually sees
```

Add `public/`, `resources/_gen/`, `node_modules/` and `.hugo_build.lock` to `.gitignore`. Keep `package-lock.json` committed.

## Rules that prevent most bugs

- **Layout names:** `home.html` not `index.html`; `_partials/` and `_shortcodes/` with underscores; no `_default/`. Both `taxonomy.html` and `term.html` — `taxonomy.html` no longer covers terms.
- **Context:** inside `range` and `with`, `.` changes. Use `$` for the page, or pass a dict to partials: `{{ partial "card.html" (dict "page" . "size" "sm") }}`.
- **Use `with` instead of `if` + repeat:** `{{ with .Params.subtitle }}<p>{{ . }}</p>{{ end }}`.
- **Links:** `.RelPermalink` for pages and resources; `relURL`/`absURL` for static paths. Never hard-code the base URL.
- **Images:** keep them next to the content (page bundle) and process them — `Resize`, `Process "resize 800x webp"` — with width and height on the `<img>`.
- **Tailwind classes must appear in rendered HTML** to be generated. Classes only added by JavaScript need an `@source inline(...)` safelist (`references/tailwind.md`).
- **Escaping:** Hugo auto-escapes. Use `safeHTML` only on content you control.

## Upgrading an existing site

bep (Hugo's lead maintainer) publishes version-specific migration guides as a CLI:

```sh
go install github.com/bep/myhugofixer@latest
myhugofixer -low v0.120.0             # guides from the site's current version up to the latest
```

Read the output, apply it, then build until `hugo build` prints **no deprecation warnings** (`hugo build --logLevel info` shows them all). Commit in small steps — layout renames first, then deprecated functions, then config.

## Debugging

| Symptom | Likely cause | Check |
|---|---|---|
| Template not used | wrong name or folder for the new system; a more specific template wins | `hugo build --printPathWarnings`; `references/templates.md` lookup table |
| `access denied: "tailwindcss" is not whitelisted` | `security.exec.allow` missing `^tailwindcss$` | `references/tailwind.md` §1 config |
| Some classes have no styles | class not in rendered HTML (JS-added) or `hugo_stats.json` not sourced | `@source "hugo_stats.json"` in `main.css`; `@source inline(...)` |
| Styles stale after editing templates | cachebuster or mount missing for `hugo_stats.json` | compare config with §1; restart `hugo server` |
| Page missing from build | `draft: true`, future `date`, or `expiryDate` passed | `hugo server -D -F`; `hugo list drafts` / `hugo list future` |
| Partial output empty | wrong context passed to the partial | `{{ warnf "%#v" . }}` inside the partial |
| Shortcode markdown not rendered | `{{< >}}` used where `{{% %}}` needed | `references/templates.md` shortcodes |

## Reference files

| File | Read when |
|---|---|
| `references/tailwind.md` | setting up Tailwind, theming, dark mode, typography, unstyled classes |
| `references/templates.md` | writing layouts, partials, shortcodes, render hooks, menus, page bundles, images |

## Sources

- [Hugo: css.TailwindCSS](https://gohugo.io/functions/css/tailwindcss/)
- [Hugo: New template system (v0.146.0)](https://gohugo.io/templates/new-templatesystem-overview/)
- [Hugo: Image processing](https://gohugo.io/content-management/image-processing/)
- [bep/myhugofixer](https://github.com/bep/myhugofixer)
- [Tailwind CSS v4 documentation](https://tailwindcss.com/docs)
