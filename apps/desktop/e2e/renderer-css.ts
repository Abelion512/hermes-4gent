import fs from 'node:fs'
import path from 'node:path'

const DEFAULT_DIST = path.resolve(import.meta.dirname, '..', 'dist')

// The renderer bundle names its stylesheets after the bundler's chunk names (today main-<hash>.css,
// earlier index-<hash>.css), so a filename pattern goes stale. The build records the stylesheet
// graph in two places: the <link rel="stylesheet"> tags of dist/index.html and the chunk graph in
// renderer-manifest.json. Read those, not a guessed filename.
//
// Boot layout wrinkle: src/entry.ts deliberately keeps the whole app behind ONE dynamic import
// (`bootRenderer(() => import('./main'))`) so no store reads localStorage before this machine's
// shared preferences hydrate. A production dist therefore has NO stylesheet link in index.html and
// NO css on the manifest's isEntry chunk — the boot styles (styles.css and friends, emitted as
// main-<hash>.css) sit on the entry's isDynamicEntry chunk. So the entry stylesheet set is the css
// of the entry chunk's static import closure plus its direct dynamic imports' static closures —
// one dynamic edge, never two. Deeper dynamic chunks (secondary windows, lazy routes: tour,
// capabilities, wake-indicator, …) are NOT boot styles and must not be concatenated in.
function distRelative(distDir: string, href: string): string {
  return path.join(distDir, href.replace(/[?#].*$/, '').replace(/^(\.\/|\/)+/, ''))
}

interface ManifestChunk {
  file?: string
  isEntry?: boolean
  imports?: string[]
  dynamicImports?: string[]
  css?: string[]
}

// css of the entry chunk's graph: static closure, plus the static closures reachable across the
// single dynamic boot edge. imports/dynamicImports are manifest keys; css entries are file refs.
function manifestBootCss(manifest: Record<string, ManifestChunk>): string[] {
  const found: string[] = []

  const add = (file: string): void => {
    if (!found.includes(file)) {
      found.push(file)
    }
  }

  const seen = new Set<string>()

  const queue: Array<{ key: string; bootEdgeUsed: boolean }> = Object.keys(manifest)
    .filter(key => manifest[key]?.isEntry)
    .map(key => ({ key, bootEdgeUsed: false }))

  while (queue.length > 0) {
    const { key, bootEdgeUsed } = queue.shift()!

    if (seen.has(key)) {
      continue
    }

    seen.add(key)

    const chunk = manifest[key]

    if (!chunk || typeof chunk !== 'object') {
      continue
    }

    for (const css of chunk.css ?? []) {
      add(css)
    }

    for (const key of chunk.imports ?? []) {
      queue.push({ key, bootEdgeUsed })
    }

    if (!bootEdgeUsed) {
      for (const key of chunk.dynamicImports ?? []) {
        queue.push({ key, bootEdgeUsed: true })
      }
    }
  }

  return found
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
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8')) as Record<string, ManifestChunk>

    for (const css of manifestBootCss(manifest)) {
      add(distRelative(distDir, css))
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
