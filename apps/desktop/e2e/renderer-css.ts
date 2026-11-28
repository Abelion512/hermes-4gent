import fs from 'node:fs'
import path from 'node:path'

const DEFAULT_DIST = path.resolve(import.meta.dirname, '..', 'dist')

// The renderer bundle names its stylesheets after the bundler's chunk names (today main-<hash>.css,
// earlier index-<hash>.css), so a filename pattern goes stale. The build records the entry stylesheet
// in two places: the <link rel="stylesheet"> tags of dist/index.html and the entry's `css` list in
// renderer-manifest.json. Read those, not a guessed filename.
function distRelative(distDir: string, href: string): string {
  return path.join(distDir, href.replace(/[?#].*$/, '').replace(/^(\.\/|\/)+/, ''))
}

export function entryStylesheets(distDir: string = DEFAULT_DIST): string[] {
  const found: string[] = []
  const add = (file: string): void => {
    if (!found.includes(file)) {
      found.push(file)
    }
  }

  const indexHtml = path.join(distDir, 'index.html')

  if (fs.existsSync(indexHtml)) {
    for (const tag of fs.readFileSync(indexHtml, 'utf8').match(/<link\b[^>]*>/gi) ?? []) {
      const href = /\bhref=["']?([^"'\s>]+)/i.exec(tag)?.[1]

      if (href && /\brel=["']?stylesheet/i.test(tag)) {
        add(distRelative(distDir, href))
      }
    }
  }

  const manifestPath = path.join(distDir, 'renderer-manifest.json')

  if (fs.existsSync(manifestPath)) {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8')) as Record<string, { css?: string[]; isEntry?: boolean }>

    for (const entry of Object.values(manifest)) {
      if (entry?.isEntry) {
        for (const css of entry.css ?? []) {
          add(distRelative(distDir, css))
        }
      }
    }
  }

  return found.filter(file => fs.existsSync(file))
}

export function rendererCss(distDir: string = DEFAULT_DIST): string {
  const files = entryStylesheets(distDir)

  if (files.length === 0) {
    const assets = path.join(distDir, 'assets')
    const present = fs.existsSync(assets) ? fs.readdirSync(assets).filter(file => file.endsWith('.css')) : []

    throw new Error(
      `Desktop renderer entry stylesheet not found: no existing <link rel="stylesheet"> in ${path.join(distDir, 'index.html')} ` +
        `and no entry css in renderer-manifest.json. CSS files present in dist/assets: ${present.join(', ') || 'none'}`
    )
  }

  return files.map(file => fs.readFileSync(file, 'utf8')).join('\n')
}
